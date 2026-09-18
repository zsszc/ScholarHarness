from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Awaitable
from typing import Any, TypeVar

from scholar_harness.core.events import AgentEvent
from scholar_harness.runtimes.base import AgentRuntime
from scholar_harness.runtimes.context import PreparedContext, TurnContextProvider
from scholar_harness.runtimes.model import (
    ModelAdapter,
    ModelMessage,
    ModelResponse,
    ModelToolCall,
    ModelToolDefinition,
)
from scholar_harness.tools.context import ToolExecutionContext, current_trace_binding
from scholar_harness.tools.registry import ToolRegistry

_T = TypeVar("_T")


class _TurnAborted(Exception):
    pass


class MiniPyRuntime(AgentRuntime):
    """Inspectable Python agent loop for learning, testing, and comparison with Pi."""

    def __init__(
        self,
        model: ModelAdapter,
        tools: ToolRegistry,
        *,
        max_tool_rounds: int = 8,
        compaction_char_limit: int = 4_000,
        session_id: str | None = None,
        context_provider: TurnContextProvider | None = None,
    ) -> None:
        if max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be at least 1")
        if compaction_char_limit < 100:
            raise ValueError("compaction_char_limit must be at least 100")
        self._model = model
        self._tools = tools
        self._max_tool_rounds = max_tool_rounds
        self._compaction_char_limit = compaction_char_limit
        self._session_id = session_id or str(uuid.uuid4())
        self._context_provider = context_provider
        self._entries: list[AgentEvent] = []
        self._entry_positions: dict[str, int] = {}
        self._active_leaf_id: str | None = None
        self._started = False
        self._closed = False
        self._turn_active = False
        self._abort_event: asyncio.Event | None = None

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def active_leaf_id(self) -> str | None:
        return self._active_leaf_id

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("MiniPyRuntime is closed")
        self._started = True

    async def stream(self, prompt: str) -> AsyncIterator[AgentEvent]:
        self._ensure_available()
        if self._turn_active:
            raise RuntimeError("MiniPyRuntime already has an active turn")
        if not prompt:
            raise ValueError("Prompt cannot be empty")

        self._turn_active = True
        self._abort_event = asyncio.Event()
        status = "completed"
        error: str | None = None
        yield self._live_event("agent_start", {"type": "agent_start"})

        try:
            try:
                if self._context_provider is not None:
                    try:
                        prepared = PreparedContext.model_validate(
                            await self._interruptible(
                                self._context_provider.prepare(prompt, self._session_id)
                            )
                        )
                    except _TurnAborted:
                        raise
                    except Exception:
                        yield self._live_event(
                            "context_injection",
                            self._context_event_data(
                                {},
                                content="",
                                status="error",
                                error="retrieval_error",
                            ),
                        )
                    else:
                        context_entry = None
                        if prepared.content:
                            context_entry = self._append_entry(
                                "context",
                                {
                                    "role": "system",
                                    "content": prepared.content,
                                    "context": prepared.metadata,
                                },
                            )
                        yield self._live_event(
                            "context_injection",
                            self._context_event_data(
                                prepared.metadata,
                                content=prepared.content,
                            ),
                            entry=context_entry,
                        )
                self._append_entry("message", {"role": "user", "content": prompt})
                tool_rounds = 0
                while True:
                    response = await self._interruptible(
                        self._model.complete(
                            self._model_messages(), self._tool_definitions()
                        )
                    )
                    response = ModelResponse.model_validate(response)
                    assistant = self._append_entry(
                        "message",
                        {
                            "role": "assistant",
                            "content": response.content,
                            "toolCalls": [
                                call.model_dump() for call in response.tool_calls
                            ],
                            "usage": response.usage,
                        },
                    )
                    if response.content:
                        yield self._live_event(
                            "message_update",
                            {"type": "message_update", "delta": response.content},
                            entry=assistant,
                        )

                    if not response.tool_calls:
                        break
                    if tool_rounds >= self._max_tool_rounds:
                        status = "failed"
                        error = "max_tool_rounds"
                        self._append_entry(
                            "message",
                            {
                                "role": "assistant",
                                "content": "Runtime stopped: maximum tool rounds reached.",
                                "error": error,
                            },
                        )
                        break
                    tool_rounds += 1

                    for call in response.tool_calls:
                        yield self._tool_start_event(call)
                        try:
                            binding = current_trace_binding()
                            result = await self._interruptible(
                                self._tools.execute(
                                    call.name,
                                    call.arguments,
                                    context=ToolExecutionContext(
                                        runtime_type=(
                                            binding.runtime_type
                                            if binding
                                            else "mini-py"
                                        ),
                                        session_id=self._session_id,
                                        entry_id=assistant.entry_id,
                                        trace_run_id=(
                                            binding.run_id if binding else None
                                        ),
                                        tool_call_id=call.id,
                                    ),
                                )
                            )
                            is_error = False
                        except _TurnAborted:
                            result = self._tool_error(
                                "aborted", "Tool execution was aborted"
                            )
                            yield self._tool_end_event(call, result, is_error=True)
                            self._append_tool_result(call, result, is_error=True)
                            raise
                        except Exception as exc:
                            result = self._tool_error(type(exc).__name__, str(exc))
                            is_error = True

                        yield self._tool_end_event(call, result, is_error=is_error)
                        self._append_tool_result(call, result, is_error=is_error)
            except _TurnAborted:
                status = "aborted"
                error = "aborted"

            end_data: dict[str, Any] = {"type": "agent_end", "status": status}
            if error is not None:
                end_data["error"] = error
            yield self._live_event("agent_end", end_data)
            yield self._live_event(
                "agent_settled",
                {"type": "agent_settled", "status": status},
            )
        finally:
            self._abort_event = None
            self._turn_active = False

    async def abort(self) -> None:
        if self._abort_event is not None:
            self._abort_event.set()

    async def compact(self, instructions: str | None = None) -> None:
        self._ensure_mutable()
        path = self._active_path()
        lines = []
        for entry in path:
            role = str(entry.data.get("role") or entry.type)
            content = str(entry.data.get("content") or "").strip()
            if content:
                lines.append(f"{role}: {content}")
        summary = "\n".join(lines)
        if len(summary) > self._compaction_char_limit:
            summary = summary[-self._compaction_char_limit :]
        if instructions:
            summary = f"Compaction instructions: {instructions}\n{summary}".strip()
        self._append_entry(
            "compaction",
            {
                "role": "system",
                "content": summary or "No prior textual context.",
                "instructions": instructions,
            },
        )

    async def fork(self, entry_id: str) -> None:
        self._ensure_mutable()
        if entry_id not in self._entry_positions:
            raise KeyError(f"Unknown entry: {entry_id}")
        self._active_leaf_id = entry_id

    async def get_entries(self, since: str | None = None) -> list[AgentEvent]:
        self._ensure_available()
        if since is None:
            return list(self._entries)
        try:
            position = self._entry_positions[since]
        except KeyError as exc:
            raise KeyError(f"Unknown entry: {since}") from exc
        return list(self._entries[position + 1 :])

    async def close(self) -> None:
        if self._closed:
            return
        await self.abort()
        self._closed = True

    def _ensure_available(self) -> None:
        if self._closed:
            raise RuntimeError("MiniPyRuntime is closed")
        if not self._started:
            raise RuntimeError("MiniPyRuntime has not been started")

    def _ensure_mutable(self) -> None:
        self._ensure_available()
        if self._turn_active:
            raise RuntimeError("Cannot mutate session during an active turn")

    def _append_entry(self, entry_type: str, data: dict[str, Any]) -> AgentEvent:
        entry_id = str(uuid.uuid4())
        parent_id = self._active_leaf_id
        payload = {
            "id": entry_id,
            "parentId": parent_id,
            "type": entry_type,
            **data,
        }
        entry = AgentEvent(
            type=entry_type,
            session_id=self._session_id,
            entry_id=entry_id,
            parent_id=parent_id,
            data=payload,
        )
        self._entry_positions[entry_id] = len(self._entries)
        self._entries.append(entry)
        self._active_leaf_id = entry_id
        return entry

    def _active_path(self) -> list[AgentEvent]:
        if self._active_leaf_id is None:
            return []
        path: list[AgentEvent] = []
        current_id: str | None = self._active_leaf_id
        while current_id is not None:
            entry = self._entries[self._entry_positions[current_id]]
            path.append(entry)
            current_id = entry.parent_id
        return list(reversed(path))

    def _model_messages(self) -> list[ModelMessage]:
        path = self._active_path()
        compact_positions = [
            index for index, entry in enumerate(path) if entry.type == "compaction"
        ]
        if compact_positions:
            path = path[compact_positions[-1] :]

        messages: list[ModelMessage] = []
        for entry in path:
            if entry.type in {"compaction", "context"}:
                messages.append(
                    ModelMessage(role="system", content=str(entry.data["content"]))
                )
                continue
            if entry.type != "message":
                continue
            role = entry.data.get("role")
            if role not in {"user", "assistant", "tool"}:
                continue
            tool_calls = [
                ModelToolCall.model_validate(call)
                for call in entry.data.get("toolCalls", [])
            ]
            messages.append(
                ModelMessage(
                    role=role,
                    content=str(entry.data.get("content") or ""),
                    name=entry.data.get("name"),
                    tool_call_id=entry.data.get("toolCallId"),
                    tool_calls=tool_calls,
                )
            )
        return messages

    def _tool_definitions(self) -> list[ModelToolDefinition]:
        return [
            ModelToolDefinition.model_validate(definition)
            for definition in self._tools.definitions()
        ]

    @staticmethod
    def _context_event_data(
        metadata: dict[str, Any],
        *,
        content: str,
        **overrides: Any,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": "context_injection",
            "status": "selected" if content else "empty",
            "retrieved_count": 0,
            "eligible_count": 0,
            "selected_count": 0,
            "omitted_count": 0,
            "truncated_count": 0,
            "excluded_scope_count": 0,
            "selected_ids": [],
            "item_limit": None,
            "char_limit": None,
            "content": content,
        }
        data.update(metadata)
        data.update(overrides)
        data["type"] = "context_injection"
        return data

    async def _interruptible(self, awaitable: Awaitable[_T]) -> _T:
        assert self._abort_event is not None
        operation = asyncio.create_task(awaitable)
        abort_waiter = asyncio.create_task(self._abort_event.wait())
        try:
            done, _ = await asyncio.wait(
                {operation, abort_waiter}, return_when=asyncio.FIRST_COMPLETED
            )
            if operation in done:
                return await operation
            raise _TurnAborted
        finally:
            for task in (operation, abort_waiter):
                if not task.done():
                    task.cancel()
            await asyncio.gather(operation, abort_waiter, return_exceptions=True)

    def _append_tool_result(
        self,
        call: ModelToolCall,
        result: Any,
        *,
        is_error: bool,
    ) -> AgentEvent:
        return self._append_entry(
            "message",
            {
                "role": "tool",
                "name": call.name,
                "toolCallId": call.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
                "result": result,
                "isError": is_error,
            },
        )

    def _live_event(
        self,
        event_type: str,
        data: dict[str, Any],
        *,
        entry: AgentEvent | None = None,
    ) -> AgentEvent:
        return AgentEvent(
            type=event_type,
            session_id=self._session_id,
            entry_id=entry.entry_id if entry else self._active_leaf_id,
            parent_id=entry.parent_id if entry else None,
            data=data,
        )

    def _tool_start_event(self, call: ModelToolCall) -> AgentEvent:
        return self._live_event(
            "tool_execution_start",
            {
                "type": "tool_execution_start",
                "toolCallId": call.id,
                "toolName": call.name,
                "args": call.arguments,
            },
        )

    def _tool_end_event(
        self,
        call: ModelToolCall,
        result: Any,
        *,
        is_error: bool,
    ) -> AgentEvent:
        return self._live_event(
            "tool_execution_end",
            {
                "type": "tool_execution_end",
                "toolCallId": call.id,
                "toolName": call.name,
                "result": result,
                "isError": is_error,
            },
        )

    @staticmethod
    def _tool_error(error_type: str, message: str) -> dict[str, object]:
        return {"error": {"type": error_type, "message": message}}
