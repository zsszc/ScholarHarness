from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import sleep

import pytest

from scholar_harness.chat_persistence import SQLiteChatSessionRepository
from scholar_harness.evaluations.repository import SQLiteEvaluationRepository
from scholar_harness.memory.repository import SQLiteMemoryRepository
from scholar_harness.papers.repository import SQLitePaperRepository
from scholar_harness.storage.sqlite import (
    SQLITE_BUSY_TIMEOUT_MS,
    configure_sqlite_database,
    connect_sqlite,
)
from scholar_harness.traces.repository import SQLiteTraceRepository


@pytest.mark.parametrize(
    "repository_type",
    [
        SQLitePaperRepository,
        SQLiteMemoryRepository,
        SQLiteTraceRepository,
        SQLiteEvaluationRepository,
        SQLiteChatSessionRepository,
    ],
)
def test_repositories_share_sqlite_connection_policy(tmp_path, repository_type) -> None:
    repository = repository_type(tmp_path / f"{repository_type.__name__}.db")

    with repository.connect() as connection:
        row = connection.execute("SELECT 1 AS value").fetchone()
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]

    assert row["value"] == 1
    assert foreign_keys == 1
    assert busy_timeout == SQLITE_BUSY_TIMEOUT_MS
    assert journal_mode == "wal"
    assert synchronous == 1  # NORMAL


def test_in_memory_connection_policy_does_not_require_wal() -> None:
    connection = connect_sqlite(":memory:")
    try:
        journal_mode = configure_sqlite_database(connection, ":memory:")
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO sample DEFAULT VALUES")

        assert journal_mode == "memory"
        assert connection.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 1
    finally:
        connection.close()


def test_busy_timeout_allows_waiting_writer_to_complete(tmp_path) -> None:
    repository = SQLiteMemoryRepository(tmp_path / "contention.db")
    blocker = repository.connect()
    blocker.execute("BEGIN IMMEDIATE")
    started = Event()
    proceed = Event()

    def write_candidate():
        started.set()
        assert proceed.wait(timeout=1)
        return repository.create_candidate(
            content="concurrent memory",
            kind="semantic",
            scope="global",
            confidence=0.5,
            evidence=[],
        )

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(write_candidate)
            assert started.wait(timeout=1)
            proceed.set()
            sleep(0.05)
            assert not future.done()
            blocker.commit()
            saved = future.result(timeout=2)
    finally:
        blocker.close()

    assert saved.content == "concurrent memory"
    assert repository.get(saved.id) == saved
