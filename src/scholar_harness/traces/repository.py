from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from scholar_harness.core.events import AgentEvent
from scholar_harness.traces.models import AgentRun, RunStatus, ToolExecution, TraceEvent
from scholar_harness.traces.redaction import TraceSanitizer


class SQLiteTraceRepository:
    def __init__(
        self,
        database: Path | str,
        *,
        sanitizer: TraceSanitizer | None = None,
    ) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.sanitizer = sanitizer or TraceSanitizer()
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id TEXT PRIMARY KEY,
                    runtime_type TEXT NOT NULL,
                    external_session_id TEXT,
                    status TEXT NOT NULL,
                    active_leaf_id TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS agent_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    entry_id TEXT,
                    parent_id TEXT,
                    event_timestamp TEXT NOT NULL,
                    idempotency_key TEXT,
                    raw_json TEXT NOT NULL,
                    UNIQUE (run_id, sequence)
                );

                CREATE UNIQUE INDEX IF NOT EXISTS agent_events_idempotency
                ON agent_events(run_id, idempotency_key)
                WHERE idempotency_key IS NOT NULL;

                CREATE TABLE IF NOT EXISTS tool_executions (
                    run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
                    tool_call_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT,
                    result_json TEXT,
                    is_error INTEGER,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    duration_ms REAL,
                    PRIMARY KEY (run_id, tool_call_id)
                );
                """
            )

    def create_run(
        self,
        runtime_type: str,
        *,
        external_session_id: str | None = None,
    ) -> AgentRun:
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_runs (
                    id, runtime_type, external_session_id, status, started_at
                ) VALUES (?, ?, ?, 'running', ?)
                """,
                (run_id, runtime_type, external_session_id, started_at.isoformat()),
            )
        return self.get_run(run_id)

    def update_run_context(
        self,
        run_id: str,
        *,
        external_session_id: str | None = None,
        active_leaf_id: str | None = None,
    ) -> AgentRun:
        updates = []
        parameters: list[object] = []
        if external_session_id is not None:
            updates.append("external_session_id = ?")
            parameters.append(external_session_id)
        if active_leaf_id is not None:
            updates.append("active_leaf_id = ?")
            parameters.append(active_leaf_id)
        if not updates:
            return self.get_run(run_id)
        parameters.append(run_id)
        with self.connect() as connection:
            cursor = connection.execute(
                f"UPDATE agent_runs SET {', '.join(updates)} WHERE id = ?", parameters
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown run: {run_id}")
        return self.get_run(run_id)

    def finish_run(
        self,
        run_id: str,
        status: RunStatus,
        *,
        error: str | None = None,
    ) -> AgentRun:
        if status == "running":
            raise ValueError("finish_run requires a terminal status")
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE agent_runs
                SET status = ?, ended_at = ?, error = ?
                WHERE id = ?
                """,
                (status, datetime.now(UTC).isoformat(), error, run_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown run: {run_id}")
        return self.get_run(run_id)

    def append_event(
        self,
        run_id: str,
        event: AgentEvent,
        *,
        idempotency_key: str | None = None,
    ) -> bool:
        payload = self.sanitizer.prepare(event.data)
        raw_json = self.sanitizer.dumps(payload)
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            if idempotency_key is not None:
                existing = connection.execute(
                    """
                    SELECT 1 FROM agent_events
                    WHERE run_id = ? AND idempotency_key = ?
                    """,
                    (run_id, idempotency_key),
                ).fetchone()
                if existing:
                    connection.rollback()
                    return False
            sequence = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1
                FROM agent_events WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO agent_events (
                    run_id, sequence, event_type, entry_id, parent_id,
                    event_timestamp, idempotency_key, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    sequence,
                    event.type,
                    event.entry_id,
                    event.parent_id,
                    event.timestamp.isoformat(),
                    idempotency_key,
                    raw_json,
                ),
            )
            self._project_tool_event(connection, run_id, event)
            connection.commit()
            return True
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def ingest_entries(self, run_id: str, entries: list[AgentEvent]) -> int:
        inserted = 0
        for entry in entries:
            if entry.entry_id is None:
                continue
            if self.append_event(
                run_id, entry, idempotency_key=f"entry:{entry.entry_id}"
            ):
                inserted += 1
                self.update_run_context(
                    run_id,
                    external_session_id=entry.session_id,
                    active_leaf_id=entry.entry_id,
                )
        return inserted

    def get_run(self, run_id: str) -> AgentRun:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown run: {run_id}")
        return AgentRun.model_validate(dict(row))

    def list_runs(self, limit: int = 100) -> list[AgentRun]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM agent_runs
                ORDER BY started_at DESC, id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [AgentRun.model_validate(dict(row)) for row in rows]

    def list_events(self, run_id: str) -> list[TraceEvent]:
        self.get_run(run_id)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, run_id, sequence, event_type, entry_id, parent_id,
                       event_timestamp, idempotency_key, raw_json
                FROM agent_events WHERE run_id = ? ORDER BY sequence
                """,
                (run_id,),
            ).fetchall()
        return [
            TraceEvent(
                id=row["id"],
                run_id=row["run_id"],
                sequence=row["sequence"],
                event_type=row["event_type"],
                entry_id=row["entry_id"],
                parent_id=row["parent_id"],
                event_timestamp=row["event_timestamp"],
                idempotency_key=row["idempotency_key"],
                payload=json.loads(row["raw_json"]),
            )
            for row in rows
        ]

    def list_tool_executions(self, run_id: str) -> list[ToolExecution]:
        self.get_run(run_id)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM tool_executions
                WHERE run_id = ? ORDER BY started_at, tool_call_id
                """,
                (run_id,),
            ).fetchall()
        return [self._to_tool_execution(row) for row in rows]

    def _project_tool_event(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        event: AgentEvent,
    ) -> None:
        payload = event.data
        tool_call_id = payload.get("toolCallId")
        if not tool_call_id:
            return
        tool_name = str(payload.get("toolName") or "unknown")
        if event.type == "tool_execution_start":
            arguments = self.sanitizer.prepare(payload.get("args", {}))
            connection.execute(
                """
                INSERT INTO tool_executions (
                    run_id, tool_call_id, tool_name, arguments_json, started_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id, tool_call_id) DO UPDATE SET
                    tool_name = excluded.tool_name,
                    arguments_json = excluded.arguments_json,
                    started_at = excluded.started_at
                """,
                (
                    run_id,
                    str(tool_call_id),
                    tool_name,
                    self.sanitizer.dumps(arguments),
                    event.timestamp.isoformat(),
                ),
            )
        elif event.type == "tool_execution_end":
            result = self.sanitizer.prepare(payload.get("result", {}))
            existing = connection.execute(
                """
                SELECT started_at FROM tool_executions
                WHERE run_id = ? AND tool_call_id = ?
                """,
                (run_id, str(tool_call_id)),
            ).fetchone()
            started_at = (
                datetime.fromisoformat(existing["started_at"])
                if existing
                else event.timestamp
            )
            duration_ms = max(
                0.0, (event.timestamp - started_at).total_seconds() * 1000
            )
            connection.execute(
                """
                INSERT INTO tool_executions (
                    run_id, tool_call_id, tool_name, result_json, is_error,
                    started_at, ended_at, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, tool_call_id) DO UPDATE SET
                    tool_name = excluded.tool_name,
                    result_json = excluded.result_json,
                    is_error = excluded.is_error,
                    ended_at = excluded.ended_at,
                    duration_ms = excluded.duration_ms
                """,
                (
                    run_id,
                    str(tool_call_id),
                    tool_name,
                    self.sanitizer.dumps(result),
                    int(bool(payload.get("isError"))),
                    started_at.isoformat(),
                    event.timestamp.isoformat(),
                    duration_ms,
                ),
            )

    @staticmethod
    def _to_tool_execution(row: sqlite3.Row) -> ToolExecution:
        return ToolExecution(
            run_id=row["run_id"],
            tool_call_id=row["tool_call_id"],
            tool_name=row["tool_name"],
            arguments=(
                json.loads(row["arguments_json"])
                if row["arguments_json"] is not None
                else None
            ),
            result=(
                json.loads(row["result_json"])
                if row["result_json"] is not None
                else None
            ),
            is_error=(bool(row["is_error"]) if row["is_error"] is not None else None),
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            duration_ms=row["duration_ms"],
        )
