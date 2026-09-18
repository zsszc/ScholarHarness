from __future__ import annotations

import sqlite3
from pathlib import Path

SQLITE_BUSY_TIMEOUT_MS = 5_000


def connect_sqlite(database: Path | str) -> sqlite3.Connection:
    connection = sqlite3.connect(
        database,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1_000,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def configure_sqlite_database(
    connection: sqlite3.Connection,
    database: Path | str,
) -> str:
    if str(database) != ":memory:":
        journal_mode = str(
            connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        ).lower()
    else:
        journal_mode = str(
            connection.execute("PRAGMA journal_mode").fetchone()[0]
        ).lower()
    connection.execute("PRAGMA synchronous = NORMAL")
    return journal_mode
