from __future__ import annotations

import asyncio
from collections.abc import Sequence

import pytest
from pydantic import BaseModel

from scholar_harness.runtimes.mini_py import MiniPyRuntime
from scholar_harness.runtimes.model import (
    ModelMessage,
    ModelResponse,
    ModelToolCall,
    ModelToolDefinition,
)
from scholar_harness.tools.registry import Tool, ToolRegistry


class EchoInput(BaseModel):
    text: str


class ScriptedModel:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = responses
        self.calls: list[list[ModelMessage]] = []
        self.tool_definitions: list[list[ModelToolDefinition]] = []

    async def complete(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition],
    ) -> ModelResponse:
        self.calls.append([message.model_copy(deep=True) for message in messages])
        self.tool_definitions.append([tool.model_copy(deep=True) for tool in tools])
        return self.responses.pop(0)


class BlockingModel:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.cancelled = False

    async def complete(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition],
    ) -> ModelResponse:
        self.entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("unreachable")


def echo_tools() -> ToolRegistry:
    registry = ToolRegistry()

    async def echo(arguments: EchoInput):
        return {"echo": arguments.text}

    registry.register(
        Tool(
            name="echo",
            description="Echo validated text.",
            input_model=EchoInput,
            handler=echo,
        )
    )

    async def fail(arguments: EchoInput):
        raise RuntimeError(f"cannot echo {arguments.text}")

    registry.register(
        Tool(
            name="fail",
            description="Raise a test handler failure.",
            input_model=EchoInput,
            handler=fail,
        )
    )
    return registry


async def collect(runtime: MiniPyRuntime, prompt: str):
    return [event async for event in runtime.stream(prompt)]


async def test_executes_tool_loop_and_appends_replayable_entries() -> None:
    model = ScriptedModel(
        [
            ModelResponse(
                content="Checking.",
                tool_calls=[
                    ModelToolCall(id="call-1", name="echo", arguments={"text": "hi"})
                ],
            ),
            ModelResponse(content="The tool returned hi."),
        ]
    )
    runtime = MiniPyRuntime(model, echo_tools(), session_id="mini-session")
    await runtime.start()

    events = await collect(runtime, "use the tool")
    entries = await runtime.get_entries()

    assert [event.type for event in events] == [
        "agent_start",
        "message_update",
        "tool_execution_start",
        "tool_execution_end",
        "message_update",
        "agent_end",
        "agent_settled",
    ]
    assert events[2].data["toolCallId"] == "call-1"
    assert events[3].data["result"] == {"echo": "hi"}
    assert [entry.data["role"] for entry in entries] == [
        "user",
        "assistant",
        "tool",
        "assistant",
    ]
    assert entries[2].parent_id == entries[1].entry_id
    assert model.calls[1][-1].role == "tool"
    assert model.calls[1][-1].content == '{"echo": "hi"}'
    assert model.tool_definitions[0][0].name == "echo"
    assert model.tool_definitions[0][0].parameters["required"] == ["text"]


async def test_tool_failures_become_model_observations() -> None:
    model = ScriptedModel(
        [
            ModelResponse(
                tool_calls=[
                    ModelToolCall(id="unknown", name="missing", arguments={}),
                    ModelToolCall(id="invalid", name="echo", arguments={}),
                    ModelToolCall(
                        id="handler", name="fail", arguments={"text": "boom"}
                    ),
                ]
            ),
            ModelResponse(content="I handled both failures."),
        ]
    )
    runtime = MiniPyRuntime(model, echo_tools())
    await runtime.start()

    events = await collect(runtime, "recover")

    ended = [event for event in events if event.type == "tool_execution_end"]
    assert [event.data["isError"] for event in ended] == [True, True, True]
    assert ended[0].data["result"]["error"]["type"] == "KeyError"
    assert ended[1].data["result"]["error"]["type"] == "ValidationError"
    assert ended[2].data["result"]["error"] == {
        "type": "RuntimeError",
        "message": "cannot echo boom",
    }
    tool_messages = [message for message in model.calls[1] if message.role == "tool"]
    assert len(tool_messages) == 3
    assert all('"error"' in message.content for message in tool_messages)
    assert events[-2].data["status"] == "completed"


async def test_stops_repeating_model_at_tool_round_limit() -> None:
    repeated_call = ModelResponse(
        tool_calls=[ModelToolCall(id="repeat", name="echo", arguments={"text": "x"})]
    )
    model = ScriptedModel([repeated_call, repeated_call.model_copy(deep=True)])
    runtime = MiniPyRuntime(model, echo_tools(), max_tool_rounds=1)
    await runtime.start()

    events = await collect(runtime, "loop")

    assert len([event for event in events if event.type == "tool_execution_start"]) == 1
    assert events[-2].data == {
        "type": "agent_end",
        "status": "failed",
        "error": "max_tool_rounds",
    }
    assert events[-1].data["status"] == "failed"


async def test_abort_cancels_blocked_model_and_settles_turn() -> None:
    model = BlockingModel()
    runtime = MiniPyRuntime(model, echo_tools())
    await runtime.start()
    turn = asyncio.create_task(collect(runtime, "wait"))
    await model.entered.wait()

    await runtime.abort()
    events = await asyncio.wait_for(turn, timeout=1)

    assert model.cancelled is True
    assert [event.type for event in events] == [
        "agent_start",
        "agent_end",
        "agent_settled",
    ]
    assert events[-2].data["status"] == "aborted"


async def test_abort_cancels_blocked_tool_and_closes_trace_event() -> None:
    entered = asyncio.Event()
    cancelled = False
    registry = ToolRegistry()

    async def slow(arguments: EchoInput):
        nonlocal cancelled
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled = True
            raise
        return {"echo": arguments.text}

    registry.register(
        Tool(
            name="slow",
            description="Block until aborted.",
            input_model=EchoInput,
            handler=slow,
        )
    )
    model = ScriptedModel(
        [
            ModelResponse(
                tool_calls=[
                    ModelToolCall(
                        id="slow-call", name="slow", arguments={"text": "wait"}
                    )
                ]
            )
        ]
    )
    runtime = MiniPyRuntime(model, registry)
    await runtime.start()
    turn = asyncio.create_task(collect(runtime, "run slow tool"))
    await entered.wait()

    await runtime.abort()
    events = await asyncio.wait_for(turn, timeout=1)

    assert cancelled is True
    assert [event.type for event in events] == [
        "agent_start",
        "tool_execution_start",
        "tool_execution_end",
        "agent_end",
        "agent_settled",
    ]
    assert events[2].data["toolCallId"] == "slow-call"
    assert events[2].data["isError"] is True
    assert events[2].data["result"]["error"]["type"] == "aborted"


async def test_fork_preserves_sibling_branches_and_scopes_context() -> None:
    model = ScriptedModel(
        [
            ModelResponse(content="root answer"),
            ModelResponse(content="branch A answer"),
            ModelResponse(content="branch B answer"),
        ]
    )
    runtime = MiniPyRuntime(model, echo_tools())
    await runtime.start()
    await collect(runtime, "root question")
    root_entries = await runtime.get_entries()
    branch_point = root_entries[-1].entry_id
    assert branch_point is not None

    await collect(runtime, "branch A question")
    await runtime.fork(branch_point)
    await collect(runtime, "branch B question")
    entries = await runtime.get_entries()

    children = [entry for entry in entries if entry.parent_id == branch_point]
    assert [entry.data["content"] for entry in children] == [
        "branch A question",
        "branch B question",
    ]
    third_context = [message.content for message in model.calls[2]]
    assert third_context == ["root question", "root answer", "branch B question"]
    incremental = await runtime.get_entries(since=branch_point)
    assert incremental == entries[2:]


async def test_compaction_replaces_active_model_context_but_preserves_entries() -> None:
    model = ScriptedModel(
        [ModelResponse(content="old answer"), ModelResponse(content="new answer")]
    )
    runtime = MiniPyRuntime(model, echo_tools(), compaction_char_limit=200)
    await runtime.start()
    await collect(runtime, "old detailed question")
    before = await runtime.get_entries()

    await runtime.compact("Keep research conclusions")
    compacted = await runtime.get_entries()
    await collect(runtime, "new question")

    assert len(compacted) == len(before) + 1
    assert compacted[-1].type == "compaction"
    assert compacted[: len(before)] == before
    assert [message.role for message in model.calls[1]] == ["system", "user"]
    assert "Compaction instructions" in model.calls[1][0].content
    assert model.calls[1][1].content == "new question"


async def test_lifecycle_and_unknown_entries_are_rejected() -> None:
    runtime = MiniPyRuntime(ScriptedModel([ModelResponse(content="unused")]), echo_tools())

    with pytest.raises(RuntimeError, match="not been started"):
        await collect(runtime, "too early")
    await runtime.start()
    with pytest.raises(KeyError, match="Unknown entry"):
        await runtime.fork("missing")
    with pytest.raises(KeyError, match="Unknown entry"):
        await runtime.get_entries(since="missing")
    await runtime.close()
    with pytest.raises(RuntimeError, match="closed"):
        await collect(runtime, "too late")


async def test_concurrent_turn_is_rejected() -> None:
    model = BlockingModel()
    runtime = MiniPyRuntime(model, echo_tools())
    await runtime.start()
    first = asyncio.create_task(collect(runtime, "first"))
    await model.entered.wait()

    with pytest.raises(RuntimeError, match="active turn"):
        await collect(runtime, "second")

    await runtime.abort()
    await first
