from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from scholar_harness.core.events import AgentEvent
from scholar_harness.memory.repository import SQLiteMemoryRepository
from scholar_harness.runtimes.base import AgentRuntime
from scholar_harness.traces.redaction import TraceSanitizer
from scholar_harness.traces.repository import SQLiteTraceRepository
from scholar_harness.traces.runtime import TracingRuntime


class FakeRuntime(AgentRuntime):
    def __init__(self, events: list[AgentEvent], entries: list[AgentEvent] | None = None) -> None:
        self.events = events
        self.entries = entries or []
        self.started = False

    async def start(self) -> None:
        self.started = True

    async def stream(self, prompt: str) -> AsyncIterator[AgentEvent]:
        assert prompt
        for event in self.events:
            yield event

    async def abort(self) -> None:
        return None

    async def compact(self, instructions: str | None = None) -> None:
        return None

    async def fork(self, entry_id: str) -> None:
        return None

    async def get_entries(self, since: str | None = None) -> list[AgentEvent]:
        return self.entries

    async def close(self) -> None:
        return None


def test_redacts_nested_secrets_without_losing_usage_and_bounds_payload() -> None:
    sanitizer = TraceSanitizer(max_payload_bytes=180, preview_bytes=60)
    prepared = sanitizer.prepare(
        {
            "authorization": "Bearer private",
            "nested": {"accessToken": "private", "totalTokens": 42},
            "large": "x" * 1_000,
        }
    )

    assert prepared["truncated"] is True
    assert prepared["original_bytes"] > 180
    assert "private" not in prepared["preview"]
    assert len(prepared["preview"].encode()) <= 60

    unbounded = TraceSanitizer().prepare(
        {"accessToken": "private", "usage": {"totalTokens": 42}}
    )
    assert unbounded["accessToken"] == "[REDACTED]"
    assert unbounded["usage"]["totalTokens"] == 42


def test_idempotent_entry_ingestion(tmp_path) -> None:
    repository = SQLiteTraceRepository(tmp_path / "trace.db")
    run = repository.create_run("pi")
    entry = AgentEvent(
        type="message",
        session_id="session-1",
        entry_id="entry-1",
        data={"message": {"role": "user", "content": "hello"}},
    )

    assert repository.ingest_entries(run.id, [entry]) == 1
    assert repository.ingest_entries(run.id, [entry]) == 0
    assert len(repository.list_events(run.id)) == 1
    assert repository.get_run(run.id).active_leaf_id == "entry-1"


def test_tool_events_are_correlated(tmp_path) -> None:
    repository = SQLiteTraceRepository(tmp_path / "trace.db")
    run = repository.create_run("pi")
    started = datetime(2026, 9, 17, tzinfo=UTC)
    repository.append_event(
        run.id,
        AgentEvent(
            type="tool_execution_start",
            session_id="session-1",
            timestamp=started,
            data={
                "type": "tool_execution_start",
                "toolCallId": "call-1",
                "toolName": "search_papers",
                "args": {"query": "memory", "api_key": "private"},
            },
        ),
    )
    repository.append_event(
        run.id,
        AgentEvent(
            type="tool_execution_end",
            session_id="session-1",
            timestamp=started + timedelta(milliseconds=125),
            data={
                "type": "tool_execution_end",
                "toolCallId": "call-1",
                "toolName": "search_papers",
                "result": {"items": []},
                "isError": False,
            },
        ),
    )

    tool = repository.list_tool_executions(run.id)[0]
    assert tool.tool_name == "search_papers"
    assert tool.arguments["api_key"] == "[REDACTED]"
    assert tool.result == {"items": []}
    assert tool.is_error is False
    assert tool.duration_ms == 125


def test_oversized_tool_result_keeps_correlation(tmp_path) -> None:
    repository = SQLiteTraceRepository(
        tmp_path / "trace.db",
        sanitizer=TraceSanitizer(max_payload_bytes=180, preview_bytes=60),
    )
    run = repository.create_run("pi")
    now = datetime.now(UTC)
    repository.append_event(
        run.id,
        AgentEvent(
            type="tool_execution_end",
            session_id="session-1",
            timestamp=now,
            data={
                "toolCallId": "large-call",
                "toolName": "read_passage",
                "result": {"text": "x" * 2_000},
                "isError": False,
            },
        ),
    )

    event = repository.list_events(run.id)[0]
    tool = repository.list_tool_executions(run.id)[0]
    assert event.payload["truncated"] is True
    assert tool.tool_call_id == "large-call"
    assert tool.result["truncated"] is True


async def test_tracing_runtime_completes_and_replays_in_order(tmp_path) -> None:
    repository = SQLiteTraceRepository(tmp_path / "trace.db")
    events = [
        AgentEvent(type="agent_start", session_id="session-1"),
        AgentEvent(type="message_update", session_id="session-1", data={"delta": "a"}),
        AgentEvent(type="message_update", session_id="session-1", data={"delta": "a"}),
        AgentEvent(type="agent_settled", session_id="session-1"),
    ]
    runtime = TracingRuntime(
        FakeRuntime(events), repository, runtime_type="fake"
    )

    await runtime.start()
    forwarded = [event async for event in runtime.stream("hello")]

    assert forwarded == events
    assert runtime.last_run_id is not None
    run = repository.get_run(runtime.last_run_id)
    replay = repository.list_events(run.id)
    assert run.status == "completed"
    assert run.external_session_id == "session-1"
    assert [event.sequence for event in replay] == [1, 2, 3, 4]
    assert [event.payload.get("delta") for event in replay[1:3]] == ["a", "a"]


def test_memory_repository_additively_migrates_provenance_columns(tmp_path) -> None:
    database = tmp_path / "old.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE memories (
                id TEXT PRIMARY KEY, content TEXT NOT NULL, kind TEXT NOT NULL,
                scope TEXT NOT NULL, status TEXT NOT NULL, confidence REAL NOT NULL,
                source_session_id TEXT, source_entry_id TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
            """
        )

    repository = SQLiteMemoryRepository(database)
    memory = repository.create_candidate(
        content="Traceable memory",
        kind="semantic",
        scope="global",
        confidence=0.7,
        evidence=[],
        trace_run_id="run-1",
        source_tool_call_id="call-1",
    )

    assert memory.trace_run_id == "run-1"
    assert memory.source_tool_call_id == "call-1"
