from __future__ import annotations

import asyncio
from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from scholar_harness.api import create_app
from scholar_harness.chat_sessions import (
    ChatConfigurationError,
    ChatSessionManager,
    create_default_chat_manager,
)
from scholar_harness.papers.repository import InMemoryPaperRepository
from scholar_harness.runtimes.model import (
    ModelMessage,
    ModelResponse,
    ModelToolCall,
    ModelToolDefinition,
)
from scholar_harness.tools.registry import Tool, ToolRegistry
from scholar_harness.traces.repository import SQLiteTraceRepository


class EchoInput(BaseModel):
    text: str


class ScriptedAdapter:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = responses
        self.closed = 0

    async def complete(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition],
    ) -> ModelResponse:
        return self.responses.pop(0)

    async def aclose(self) -> None:
        self.closed += 1


class BlockingAdapter:
    def __init__(self) -> None:
        self.cancelled = False
        self.closed = 0

    async def complete(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition],
    ) -> ModelResponse:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("unreachable")

    async def aclose(self) -> None:
        self.closed += 1


def echo_tools() -> ToolRegistry:
    tools = ToolRegistry()

    async def echo(arguments: EchoInput):
        return {"echo": arguments.text}

    tools.register(
        Tool(
            name="echo",
            description="Echo text.",
            input_model=EchoInput,
            handler=echo,
        )
    )
    return tools


def manager(tmp_path, adapters) -> ChatSessionManager:
    remaining = list(adapters)
    return ChatSessionManager(
        tools=echo_tools(),
        traces=SQLiteTraceRepository(tmp_path / "chat.db"),
        adapter_factory=lambda: remaining.pop(0),
    )


async def test_manager_lifecycle_and_metadata_are_secret_free(tmp_path) -> None:
    first = ScriptedAdapter([ModelResponse(content="first")])
    second = ScriptedAdapter([ModelResponse(content="second")])
    sessions = manager(tmp_path, [first, second])

    one = await sessions.create()
    two = await sessions.create()
    events = [event async for event in one.stream("hello")]
    listed = await sessions.list()

    assert events[-1].type == "agent_settled"
    assert {item.id for item in listed} == {one.id, two.id}
    assert (await one.info()).entry_count == 2
    assert (await one.info()).last_run_id is not None
    assert "api_key" not in listed[0].model_dump()
    assert "base_url" not in listed[0].model_dump()
    assert await sessions.delete(one.id) is True
    assert await sessions.delete(one.id) is False
    assert first.closed == 1
    await sessions.close_all()
    assert second.closed == 1


async def test_missing_server_configuration_is_explicit(tmp_path) -> None:
    sessions = create_default_chat_manager(
        tools=echo_tools(),
        traces=SQLiteTraceRepository(tmp_path / "missing.db"),
        environ={},
    )

    with pytest.raises(ChatConfigurationError, match="OPENAI_MODEL"):
        await sessions.create()


def test_chat_rest_and_scripted_websocket_tool_loop(tmp_path) -> None:
    adapter = ScriptedAdapter(
        [
            ModelResponse(
                content="Checking",
                tool_calls=[
                    ModelToolCall(id="call-1", name="echo", arguments={"text": "hi"})
                ],
            ),
            ModelResponse(content="Found hi"),
        ]
    )
    sessions = manager(tmp_path, [adapter])
    app = create_app(
        repository=InMemoryPaperRepository(),
        trace_repository=SQLiteTraceRepository(tmp_path / "api.db"),
        chat_session_manager=sessions,
    )

    with TestClient(app) as client:
        created = client.post("/chat/sessions")
        assert created.status_code == 201
        session_id = created.json()["id"]
        assert client.get("/chat/sessions").json()[0]["id"] == session_id
        assert client.get(f"/chat/sessions/{session_id}").status_code == 200

        with client.websocket_connect(f"/chat/sessions/{session_id}/stream") as socket:
            assert socket.receive_json()["type"] == "session_ready"
            socket.send_json({"type": "prompt", "content": "use echo"})
            messages = []
            while True:
                message = socket.receive_json()
                messages.append(message)
                if message["type"] == "turn_complete":
                    break
            event_types = [
                item["event"]["type"] for item in messages if item["type"] == "event"
            ]
            assert event_types == [
                "agent_start",
                "message_update",
                "tool_execution_start",
                "tool_execution_end",
                "message_update",
                "agent_end",
                "agent_settled",
            ]
            assert messages[-1]["session"]["last_run_id"] is not None

            socket.send_json({"type": "entries"})
            entries = socket.receive_json()
            assert entries["command"] == "entries"
            assert [entry["data"]["role"] for entry in entries["entries"]] == [
                "user",
                "assistant",
                "tool",
                "assistant",
            ]
            branch_point = entries["entries"][1]["entry_id"]
            socket.send_json({"type": "fork", "entry_id": branch_point})
            assert socket.receive_json()["command"] == "fork"
            socket.send_json(
                {"type": "compact", "instructions": "keep the cited result"}
            )
            assert socket.receive_json()["command"] == "compact"
            socket.send_json({"type": "unknown"})
            assert socket.receive_json()["code"] == "unknown_command"
            socket.send_json([])
            assert socket.receive_json()["code"] == "invalid_command"
            socket.send_json({"type": "prompt", "content": "  "})
            assert socket.receive_json()["code"] == "invalid_prompt"
            socket.send_json({"type": "compact", "instructions": 42})
            assert socket.receive_json()["code"] == "invalid_command"

        entries_response = client.get(f"/chat/sessions/{session_id}/entries")
        assert entries_response.status_code == 200
        assert any(item["type"] == "compaction" for item in entries_response.json())
        assert client.delete(f"/chat/sessions/{session_id}").status_code == 204
        assert client.delete(f"/chat/sessions/{session_id}").status_code == 204
        assert client.get(f"/chat/sessions/{session_id}").status_code == 404
    assert adapter.closed == 1


def test_websocket_rejects_second_prompt_and_aborts_on_command(tmp_path) -> None:
    adapter = BlockingAdapter()
    sessions = manager(tmp_path, [adapter])
    app = create_app(chat_session_manager=sessions)

    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["id"]
        with client.websocket_connect(f"/chat/sessions/{session_id}/stream") as socket:
            socket.receive_json()
            socket.send_json({"type": "prompt", "content": "wait"})
            started = socket.receive_json()
            assert started["event"]["type"] == "agent_start"
            socket.send_json({"type": "prompt", "content": "second"})
            assert socket.receive_json()["code"] == "turn_active"
            socket.send_json({"type": "abort"})
            assert socket.receive_json()["command"] == "abort"
            terminal = []
            while True:
                message = socket.receive_json()
                terminal.append(message)
                if message["type"] == "turn_complete":
                    break
            statuses = [
                item["event"]["data"].get("status")
                for item in terminal
                if item["type"] == "event"
            ]
            assert statuses == ["aborted", "aborted"]
        assert adapter.cancelled is True

        with client.websocket_connect(f"/chat/sessions/{session_id}/stream") as socket:
            ready = socket.receive_json()
            assert ready["type"] == "session_ready"
            assert ready["session"]["busy"] is False


def test_websocket_disconnect_aborts_turn_and_preserves_session(tmp_path) -> None:
    adapter = BlockingAdapter()
    sessions = manager(tmp_path, [adapter])
    app = create_app(chat_session_manager=sessions)

    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["id"]
        with client.websocket_connect(f"/chat/sessions/{session_id}/stream") as socket:
            socket.receive_json()
            socket.send_json({"type": "prompt", "content": "disconnect me"})
            assert socket.receive_json()["event"]["type"] == "agent_start"

        assert adapter.cancelled is True
        info = client.get(f"/chat/sessions/{session_id}")
        assert info.status_code == 200
        assert info.json()["busy"] is False
        with client.websocket_connect(f"/chat/sessions/{session_id}/stream") as socket:
            assert socket.receive_json()["type"] == "session_ready"


def test_missing_configuration_returns_503_without_breaking_service(tmp_path) -> None:
    unavailable = create_default_chat_manager(
        tools=echo_tools(),
        traces=SQLiteTraceRepository(tmp_path / "unavailable.db"),
        environ={},
    )
    with TestClient(create_app(chat_session_manager=unavailable)) as client:
        response = client.post("/chat/sessions", json={"base_url": "bad", "api_key": "x"})
        assert response.status_code == 503
        assert "OPENAI_MODEL" in response.json()["detail"]
        assert client.get("/health").json() == {"status": "ok"}


def test_turn_failure_is_preserved_in_completion_message(tmp_path) -> None:
    class FailingAdapter(ScriptedAdapter):
        async def complete(self, messages, tools) -> ModelResponse:
            raise RuntimeError("provider unavailable")

    sessions = manager(tmp_path, [FailingAdapter([])])
    with TestClient(create_app(chat_session_manager=sessions)) as client:
        session_id = client.post("/chat/sessions").json()["id"]
        with client.websocket_connect(f"/chat/sessions/{session_id}/stream") as socket:
            socket.receive_json()
            socket.send_json({"type": "prompt", "content": "fail"})
            messages = []
            while True:
                message = socket.receive_json()
                messages.append(message)
                if message["type"] == "turn_complete":
                    break
            assert messages[-2] == {
                "type": "error",
                "code": "turn_failed",
                "message": "provider unavailable",
            }
            assert messages[-1]["error"] == "provider unavailable"
