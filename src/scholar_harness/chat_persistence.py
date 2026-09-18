from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from scholar_harness.core.events import AgentEvent
from scholar_harness.storage.sqlite import configure_sqlite_database, connect_sqlite


class ChatSessionSnapshot(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    active_leaf_id: str | None = None
    last_run_id: str | None = None
    entries: list[AgentEvent] = Field(default_factory=list)


class StoredChatSession(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    active_leaf_id: str | None
    last_run_id: str | None
    entry_count: int


class SQLiteChatSessionRepository:
    def __init__(self, database: Path | str) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        return connect_sqlite(self.database)

    def _initialize(self) -> None:
        with self.connect() as connection:
            configure_sqlite_database(connection, self.database)
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    active_leaf_id TEXT,
                    last_run_id TEXT
                );

                CREATE TABLE IF NOT EXISTS chat_session_entries (
                    session_id TEXT NOT NULL
                        REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    entry_id TEXT NOT NULL,
                    parent_id TEXT,
                    entry_type TEXT NOT NULL,
                    event_timestamp TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    PRIMARY KEY (session_id, position),
                    UNIQUE (session_id, entry_id)
                );
                """
            )

    def save(self, snapshot: ChatSessionSnapshot) -> ChatSessionSnapshot:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO chat_sessions (
                    id, created_at, updated_at, active_leaf_id, last_run_id
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    active_leaf_id = excluded.active_leaf_id,
                    last_run_id = excluded.last_run_id
                """,
                (
                    snapshot.id,
                    snapshot.created_at.isoformat(),
                    snapshot.updated_at.isoformat(),
                    snapshot.active_leaf_id,
                    snapshot.last_run_id,
                ),
            )
            connection.execute(
                "DELETE FROM chat_session_entries WHERE session_id = ?",
                (snapshot.id,),
            )
            connection.executemany(
                """
                INSERT INTO chat_session_entries (
                    session_id, position, entry_id, parent_id, entry_type,
                    event_timestamp, data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        snapshot.id,
                        position,
                        entry.entry_id,
                        entry.parent_id,
                        entry.type,
                        entry.timestamp.isoformat(),
                        json.dumps(
                            entry.data,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    )
                    for position, entry in enumerate(snapshot.entries)
                ],
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return self.get(snapshot.id)

    def get(self, session_id: str) -> ChatSessionSnapshot:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown stored chat session: {session_id}")
            entries = connection.execute(
                """
                SELECT * FROM chat_session_entries
                WHERE session_id = ? ORDER BY position
                """,
                (session_id,),
            ).fetchall()
        return ChatSessionSnapshot(
            id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            active_leaf_id=row["active_leaf_id"],
            last_run_id=row["last_run_id"],
            entries=[
                AgentEvent(
                    type=entry["entry_type"],
                    session_id=session_id,
                    entry_id=entry["entry_id"],
                    parent_id=entry["parent_id"],
                    timestamp=entry["event_timestamp"],
                    data=json.loads(entry["data_json"]),
                )
                for entry in entries
            ],
        )

    def list(self) -> list[StoredChatSession]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT s.*, COUNT(e.position) AS entry_count
                FROM chat_sessions s
                LEFT JOIN chat_session_entries e ON e.session_id = s.id
                GROUP BY s.id
                ORDER BY s.updated_at DESC, s.id DESC
                """
            ).fetchall()
        return [StoredChatSession.model_validate(dict(row)) for row in rows]

    def delete(self, session_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM chat_sessions WHERE id = ?", (session_id,)
            )
            return cursor.rowcount > 0
