from __future__ import annotations

import asyncio
import inspect
import os
import uuid
from collections.abc import AsyncIterator, Callable, Mapping
from datetime import UTC, datetime

from pydantic import BaseModel

from scholar_harness.core.events import AgentEvent
from scholar_harness.runtimes.context import TurnContextProvider
from scholar_harness.runtimes.mini_py import MiniPyRuntime
from scholar_harness.runtimes.model import ModelAdapter
from scholar_harness.runtimes.openai_compatible import OpenAICompatibleAdapter
from scholar_harness.tools.registry import ToolRegistry
from scholar_harness.traces.repository import SQLiteTraceRepository
from scholar_harness.traces.runtime import TracingRuntime

AdapterFactory = Callable[[], ModelAdapter]


class ChatConfigurationError(RuntimeError):
    """The server does not have enough provider configuration to create chats."""


class ChatSessionInfo(BaseModel):
    id: str
    created_at: datetime
    busy: bool
    connected: bool
    entry_count: int
    active_leaf_id: str | None
    last_run_id: str | None


class ChatSession:
    def __init__(
        self,
        *,
        session_id: str,
        adapter: ModelAdapter,
        tools: ToolRegistry,
        traces: SQLiteTraceRepository,
        context_provider: TurnContextProvider | None = None,
    ) -> None:
        self.id = session_id
        self.created_at = datetime.now(UTC)
        self._adapter = adapter
        self._mini = MiniPyRuntime(
            adapter,
            tools,
            session_id=session_id,
            context_provider=context_provider,
        )
        self._runtime = TracingRuntime(
            self._mini,
            traces,
            runtime_type="mini-py-browser-chat",
        )
        self._busy = False
        self._connected = False
        self._closed = False
        self._turn_done = asyncio.Event()
        self._turn_done.set()
        self._close_lock = asyncio.Lock()

    @property
    def busy(self) -> bool:
        return self._busy

    async def start(self) -> None:
        await self._runtime.start()

    def attach(self) -> bool:
        if self._closed or self._connected:
            return False
        self._connected = True
        return True

    def detach(self) -> None:
        self._connected = False

    async def stream(self, prompt: str) -> AsyncIterator[AgentEvent]:
        if self._closed:
            raise RuntimeError("Chat session is closed")
        if self._busy:
            raise RuntimeError("Chat session already has an active turn")
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        self._busy = True
        self._turn_done.clear()
        try:
            async for event in self._runtime.stream(prompt):
                yield event
        finally:
            self._busy = False
            self._turn_done.set()

    async def abort(self) -> None:
        await self._runtime.abort()

    async def compact(self, instructions: str | None = None) -> None:
        if self._busy:
            raise RuntimeError("Cannot compact during an active turn")
        await self._runtime.compact(instructions)

    async def fork(self, entry_id: str) -> None:
        if self._busy:
            raise RuntimeError("Cannot fork during an active turn")
        await self._runtime.fork(entry_id)

    async def entries(self, since: str | None = None) -> list[AgentEvent]:
        return await self._runtime.get_entries(since)

    async def info(self) -> ChatSessionInfo:
        entries = await self._mini.get_entries()
        return ChatSessionInfo(
            id=self.id,
            created_at=self.created_at,
            busy=self._busy,
            connected=self._connected,
            entry_count=len(entries),
            active_leaf_id=self._mini.active_leaf_id,
            last_run_id=self._runtime.last_run_id,
        )

    async def close(self) -> None:
        async with self._close_lock:
            if self._closed:
                return
            self._closed = True
            await self._runtime.abort()
            await self._turn_done.wait()
            try:
                await self._runtime.close()
            finally:
                close_adapter = getattr(self._adapter, "aclose", None)
                if close_adapter is not None:
                    result = close_adapter()
                    if inspect.isawaitable(result):
                        await result


class ChatSessionManager:
    def __init__(
        self,
        *,
        tools: ToolRegistry,
        traces: SQLiteTraceRepository,
        adapter_factory: AdapterFactory | None,
        unavailable_reason: str | None = None,
        context_provider: TurnContextProvider | None = None,
    ) -> None:
        self._tools = tools
        self._traces = traces
        self._adapter_factory = adapter_factory
        self._unavailable_reason = unavailable_reason
        self._context_provider = context_provider
        self._sessions: dict[str, ChatSession] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> ChatSession:
        if self._adapter_factory is None:
            raise ChatConfigurationError(
                self._unavailable_reason
                or "Browser chat is unavailable because provider configuration is missing"
            )
        adapter = self._adapter_factory()
        session = ChatSession(
            session_id=str(uuid.uuid4()),
            adapter=adapter,
            tools=self._tools,
            traces=self._traces,
            context_provider=self._context_provider,
        )
        try:
            await session.start()
        except Exception:
            await session.close()
            raise
        async with self._lock:
            self._sessions[session.id] = session
        return session

    async def get(self, session_id: str) -> ChatSession:
        async with self._lock:
            try:
                return self._sessions[session_id]
            except KeyError as exc:
                raise KeyError(f"Unknown chat session: {session_id}") from exc

    async def list(self) -> list[ChatSessionInfo]:
        async with self._lock:
            sessions = list(self._sessions.values())
        summaries = [await session.info() for session in sessions]
        return sorted(summaries, key=lambda item: (item.created_at, item.id), reverse=True)

    async def delete(self, session_id: str) -> bool:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        await session.close()
        return True

    async def close_all(self) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        await asyncio.gather(*(session.close() for session in sessions))


def create_default_chat_manager(
    *,
    tools: ToolRegistry,
    traces: SQLiteTraceRepository,
    environ: Mapping[str, str] | None = None,
    context_provider: TurnContextProvider | None = None,
) -> ChatSessionManager:
    values = os.environ if environ is None else environ
    model = values.get("OPENAI_MODEL", "").strip()
    if not model:
        return ChatSessionManager(
            tools=tools,
            traces=traces,
            adapter_factory=None,
            unavailable_reason="Set OPENAI_MODEL on the server to enable browser chat",
            context_provider=context_provider,
        )
    base_url = values.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
    if not base_url:
        return ChatSessionManager(
            tools=tools,
            traces=traces,
            adapter_factory=None,
            unavailable_reason="OPENAI_BASE_URL cannot be empty",
            context_provider=context_provider,
        )
    timeout_text = values.get("OPENAI_TIMEOUT_SECONDS", "60")
    try:
        timeout_seconds = float(timeout_text)
    except ValueError:
        timeout_seconds = 0
    if timeout_seconds <= 0:
        return ChatSessionManager(
            tools=tools,
            traces=traces,
            adapter_factory=None,
            unavailable_reason="OPENAI_TIMEOUT_SECONDS must be a positive number",
            context_provider=context_provider,
        )
    api_key = values.get("OPENAI_API_KEY") or None

    def adapter_factory() -> ModelAdapter:
        return OpenAICompatibleAdapter(
            model=model,
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )

    return ChatSessionManager(
        tools=tools,
        traces=traces,
        adapter_factory=adapter_factory,
        context_provider=context_provider,
    )
