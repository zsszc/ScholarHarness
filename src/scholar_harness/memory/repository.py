from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from scholar_harness.memory.models import (
    Memory,
    MemoryEvidence,
    MemoryKind,
    MemoryScope,
    MemoryStatus,
)

_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


class SQLiteMemoryRepository:
    def __init__(self, database: Path | str) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
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
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source_session_id TEXT,
                    source_entry_id TEXT,
                    trace_run_id TEXT,
                    source_tool_call_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memory_evidence (
                    memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    paper_id TEXT NOT NULL,
                    passage_id TEXT NOT NULL,
                    quote TEXT NOT NULL,
                    page INTEGER,
                    PRIMARY KEY (memory_id, position)
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    memory_id UNINDEXED,
                    content
                );
                """
            )
            self._ensure_column(connection, "memories", "trace_run_id", "TEXT")
            self._ensure_column(
                connection, "memories", "source_tool_call_id", "TEXT"
            )

    def create_candidate(
        self,
        *,
        content: str,
        kind: MemoryKind,
        scope: MemoryScope,
        confidence: float,
        evidence: list[MemoryEvidence],
        source_session_id: str | None = None,
        source_entry_id: str | None = None,
        trace_run_id: str | None = None,
        source_tool_call_id: str | None = None,
    ) -> Memory:
        memory_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (
                    id, content, kind, scope, status, confidence,
                    source_session_id, source_entry_id, trace_run_id,
                    source_tool_call_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'candidate', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    content,
                    kind,
                    scope,
                    confidence,
                    source_session_id,
                    source_entry_id,
                    trace_run_id,
                    source_tool_call_id,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            connection.executemany(
                """
                INSERT INTO memory_evidence (
                    memory_id, position, paper_id, passage_id, quote, page
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        memory_id,
                        position,
                        item.paper_id,
                        item.passage_id,
                        item.quote,
                        item.page,
                    )
                    for position, item in enumerate(evidence)
                ],
            )
            connection.execute(
                "INSERT INTO memory_fts (memory_id, content) VALUES (?, ?)",
                (memory_id, content),
            )
        return self.get(memory_id)

    def get(self, memory_id: str) -> Memory:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown memory: {memory_id}")
            evidence = self._load_evidence(connection, memory_id)
        return self._to_memory(row, evidence)

    def list(self, *, status: MemoryStatus | None = None, limit: int = 100) -> list[Memory]:
        sql = "SELECT * FROM memories"
        parameters: tuple[object, ...] = ()
        if status:
            sql += " WHERE status = ?"
            parameters = (status,)
        sql += " ORDER BY created_at DESC LIMIT ?"
        parameters += (limit,)
        with self.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
            return [
                self._to_memory(row, self._load_evidence(connection, row["id"]))
                for row in rows
            ]

    def set_status(self, memory_id: str, status: MemoryStatus) -> Memory:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE memories SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, memory_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown memory: {memory_id}")
        return self.get(memory_id)

    def search_confirmed(self, query: str, limit: int = 5) -> list[dict[str, object]]:
        tokens = [token.lower() for token in _TOKEN_PATTERN.findall(query)]
        if not tokens:
            return []
        fts_query = " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT m.*, bm25(memory_fts, 0.0, 1.0) AS rank
                FROM memory_fts
                JOIN memories m ON m.id = memory_fts.memory_id
                WHERE memory_fts MATCH ? AND m.status = 'confirmed'
                ORDER BY rank, m.created_at, m.id
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()
            return [
                {
                    **self._to_memory(
                        row, self._load_evidence(connection, row["id"])
                    ).model_dump(mode="json"),
                    "score": -float(row["rank"]),
                }
                for row in rows
            ]

    @staticmethod
    def _load_evidence(
        connection: sqlite3.Connection, memory_id: str
    ) -> list[MemoryEvidence]:
        rows = connection.execute(
            """
            SELECT paper_id, passage_id, quote, page
            FROM memory_evidence
            WHERE memory_id = ?
            ORDER BY position
            """,
            (memory_id,),
        ).fetchall()
        return [MemoryEvidence.model_validate(dict(row)) for row in rows]

    @staticmethod
    def _to_memory(row: sqlite3.Row, evidence: list[MemoryEvidence]) -> Memory:
        return Memory(
            id=row["id"],
            content=row["content"],
            kind=row["kind"],
            scope=row["scope"],
            status=row["status"],
            confidence=row["confidence"],
            evidence=evidence,
            source_session_id=row["source_session_id"],
            source_entry_id=row["source_entry_id"],
            trace_run_id=row["trace_run_id"],
            source_tool_call_id=row["source_tool_call_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _ensure_column(
        connection: sqlite3.Connection,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
