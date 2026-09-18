from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from scholar_harness.api import create_app
from scholar_harness.chat_persistence import ChatSessionSnapshot, SQLiteChatSessionRepository
from scholar_harness.chat_sessions import (
    ChatConfigurationError,
    ChatSessionManager,
    ChatSessionRestoreError,
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
        self.calls: list[list[ModelMessage]] = []

    async def complete(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition],
    ) -> ModelResponse:
        self.calls.append(list(messages))
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


async def test_manager_restores_persisted_session_lazily_and_continues(tmp_path) -> None:
    database = tmp_path / "durable.db"
    store = SQLiteChatSessionRepository(database)
    first_adapter = ScriptedAdapter([ModelResponse(content="first answer")])
    first_manager = ChatSessionManager(
        tools=echo_tools(),
        traces=SQLiteTraceRepository(database),
        adapter_factory=lambda: first_adapter,
        session_repository=store,
    )
    original = await first_manager.create()
    _ = [event async for event in original.stream("first question")]
    original_entries = await original.entries()
    await original.fork(original_entries[0].entry_id)
    assert store.get(original.id).active_leaf_id == original_entries[0].entry_id
    await original.compact("retain the answer")
    original_info = await original.info()
    await first_manager.close_all()

    restored_adapter = ScriptedAdapter([ModelResponse(content="continued answer")])
    factory_calls = 0

    def adapter_factory():
        nonlocal factory_calls
        factory_calls += 1
        return restored_adapter

    second_manager = ChatSessionManager(
        tools=echo_tools(),
        traces=SQLiteTraceRepository(database),
        adapter_factory=adapter_factory,
        session_repository=SQLiteChatSessionRepository(database),
    )

    listed = await second_manager.list()
    assert factory_calls == 0
    assert listed[0].id == original.id
    assert listed[0].created_at == original_info.created_at
    assert listed[0].entry_count == original_info.entry_count
    assert listed[0].last_run_id == original_info.last_run_id

    restored = await second_manager.get(original.id)
    assert factory_calls == 1
    _ = [event async for event in restored.stream("continued question")]

    assert [message.role for message in restored_adapter.calls[0]] == [
        "system",
        "user",
    ]
    assert "retain the answer" in restored_adapter.calls[0][0].content
    assert restored_adapter.calls[0][1].content == "continued question"
    assert SQLiteChatSessionRepository(database).get(original.id).last_run_id == (
        await restored.info()
    ).last_run_id
    await second_manager.close_all()
    assert SQLiteChatSessionRepository(database).get(original.id).entries


async def test_persisted_sessions_list_without_provider_and_delete_without_hydration(
    tmp_path,
) -> None:
    database = tmp_path / "unavailable-durable.db"
    store = SQLiteChatSessionRepository(database)
    adapter = ScriptedAdapter([ModelResponse(content="answer")])
    available = ChatSessionManager(
        tools=echo_tools(),
        traces=SQLiteTraceRepository(database),
        adapter_factory=lambda: adapter,
        session_repository=store,
    )
    session = await available.create()
    _ = [event async for event in session.stream("question")]
    await available.close_all()

    unavailable = ChatSessionManager(
        tools=echo_tools(),
        traces=SQLiteTraceRepository(database),
        adapter_factory=None,
        unavailable_reason="provider unavailable",
        session_repository=SQLiteChatSessionRepository(database),
    )

    assert (await unavailable.list())[0].id == session.id
    with pytest.raises(ChatConfigurationError, match="provider unavailable"):
        await unavailable.get(session.id)
    assert await unavailable.delete(session.id) is True
    assert await unavailable.list() == []


def test_persisted_session_is_listable_but_not_activated_without_provider(
    tmp_path,
) -> None:
    database = tmp_path / "unavailable-api.db"
    store = SQLiteChatSessionRepository(database)
    store.save(
        ChatSessionSnapshot(
            id="stored-session",
            created_at=datetime.now(UTC),
        )
    )
    unavailable = ChatSessionManager(
        tools=echo_tools(),
        traces=SQLiteTraceRepository(database),
        adapter_factory=None,
        unavailable_reason="provider unavailable",
        session_repository=store,
    )

    with TestClient(create_app(chat_session_manager=unavailable)) as client:
        assert client.get("/chat/sessions").json()[0]["id"] == "stored-session"
        response = client.get("/chat/sessions/stored-session")
        assert response.status_code == 503
        assert response.json()["detail"] == "provider unavailable"
        with client.websocket_connect("/chat/sessions/stored-session/stream") as socket:
            assert socket.receive_json() == {
                "type": "error",
                "code": "configuration_error",
                "message": "provider unavailable",
            }


async def test_corrupt_persisted_session_fails_without_deleting_snapshot(tmp_path) -> None:
    database = tmp_path / "corrupt-durable.db"
    store = SQLiteChatSessionRepository(database)
    adapter = ScriptedAdapter([ModelResponse(content="answer")])
    source = ChatSessionManager(
        tools=echo_tools(),
        traces=SQLiteTraceRepository(database),
        adapter_factory=lambda: adapter,
        session_repository=store,
    )
    session = await source.create()
    _ = [event async for event in session.stream("question")]
    await source.close_all()
    with store.connect() as connection:
        connection.execute(
            "UPDATE chat_sessions SET active_leaf_id = 'missing' WHERE id = ?",
            (session.id,),
        )

    restore_adapter = ScriptedAdapter([])
    restored = ChatSessionManager(
        tools=echo_tools(),
        traces=SQLiteTraceRepository(database),
        adapter_factory=lambda: restore_adapter,
        session_repository=store,
    )

    with pytest.raises(ChatSessionRestoreError, match="corrupt"):
        await restored.get(session.id)
    assert restore_adapter.closed == 1
    assert (await restored.list())[0].id == session.id


def test_websocket_session_survives_application_restart_and_deletion(tmp_path) -> None:
    database = tmp_path / "api-restart.db"
    store = SQLiteChatSessionRepository(database)
    first_adapter = ScriptedAdapter([ModelResponse(content="first answer")])
    first_manager = ChatSessionManager(
        tools=echo_tools(),
        traces=SQLiteTraceRepository(database),
        adapter_factory=lambda: first_adapter,
        session_repository=store,
    )
    with TestClient(create_app(chat_session_manager=first_manager)) as client:
        session_id = client.post("/chat/sessions").json()["id"]
        with client.websocket_connect(f"/chat/sessions/{session_id}/stream") as socket:
            socket.receive_json()
            socket.send_json({"type": "prompt", "content": "first question"})
            while socket.receive_json()["type"] != "turn_complete":
                pass

    second_adapter = ScriptedAdapter([ModelResponse(content="continued answer")])
    second_manager = ChatSessionManager(
        tools=echo_tools(),
        traces=SQLiteTraceRepository(database),
        adapter_factory=lambda: second_adapter,
        session_repository=SQLiteChatSessionRepository(database),
    )
    with TestClient(create_app(chat_session_manager=second_manager)) as client:
        listed = client.get("/chat/sessions").json()
        assert listed[0]["id"] == session_id
        assert listed[0]["connected"] is False
        with client.websocket_connect(f"/chat/sessions/{session_id}/stream") as socket:
            assert socket.receive_json()["session"]["id"] == session_id
            socket.send_json({"type": "entries"})
            restored_entries = socket.receive_json()["entries"]
            assert [item["data"]["content"] for item in restored_entries] == [
                "first question",
                "first answer",
            ]
            socket.send_json({"type": "prompt", "content": "continued question"})
            while socket.receive_json()["type"] != "turn_complete":
                pass
        assert [message.content for message in second_adapter.calls[0]] == [
            "first question",
            "first answer",
            "continued question",
        ]
        assert client.delete(f"/chat/sessions/{session_id}").status_code == 204

    assert SQLiteChatSessionRepository(database).list() == []


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
