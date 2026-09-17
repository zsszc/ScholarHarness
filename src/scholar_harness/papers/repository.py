from __future__ import annotations

import re
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from scholar_harness.papers.models import Paper, Passage

_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


class PaperRepository(Protocol):
    def add(self, paper: Paper) -> None: ...

    def search(self, query: str, limit: int = 5) -> list[Mapping[str, object]]: ...

    def read(self, paper_id: str, passage_id: str) -> Mapping[str, object]: ...


class PassageResultMixin:
    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [token.lower() for token in _TOKEN_PATTERN.findall(text)]

    @staticmethod
    def _hit(paper: Paper, passage: Passage, score: float) -> Mapping[str, object]:
        return {
            "paper_id": paper.id,
            "passage_id": passage.id,
            "title": paper.title,
            "page": passage.page,
            "section": passage.section,
            "text": passage.text,
            "score": score,
        }


class InMemoryPaperRepository(PassageResultMixin):
    """Deterministic baseline retrieval; replaced by SQLite FTS in milestone two."""

    def __init__(self) -> None:
        self._papers: dict[str, Paper] = {}

    def add(self, paper: Paper) -> None:
        self._papers[paper.id] = paper

    def search(self, query: str, limit: int = 5) -> list[Mapping[str, object]]:
        query_tokens = set(self._tokens(query))
        hits: list[Mapping[str, object]] = []
        for paper in self._papers.values():
            title_tokens = set(self._tokens(paper.title))
            for passage in paper.passages:
                text_tokens = set(self._tokens(passage.text))
                overlap = len(query_tokens & text_tokens)
                title_overlap = len(query_tokens & title_tokens)
                if overlap == 0 and title_overlap == 0:
                    continue
                score = overlap + (title_overlap * 2)
                hits.append(self._hit(paper, passage, float(score)))
        hits.sort(key=lambda item: (-float(item["score"]), str(item["paper_id"])))
        return hits[:limit]

    def read(self, paper_id: str, passage_id: str) -> Mapping[str, object]:
        paper = self._papers.get(paper_id)
        if paper is None:
            raise KeyError(f"Unknown paper: {paper_id}")
        for passage in paper.passages:
            if passage.id == passage_id:
                return self._hit(paper, passage, 1.0)
        raise KeyError(f"Unknown passage: {paper_id}/{passage_id}")



class SQLitePaperRepository(PassageResultMixin):
    """Persistent paper storage with a deterministic SQLite FTS5 baseline."""

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
                CREATE TABLE IF NOT EXISTS papers (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    authors_json TEXT NOT NULL DEFAULT '[]',
                    year INTEGER
                );

                CREATE TABLE IF NOT EXISTS passages (
                    id TEXT NOT NULL,
                    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                    text TEXT NOT NULL,
                    page INTEGER,
                    section TEXT,
                    PRIMARY KEY (paper_id, id)
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS passage_fts USING fts5(
                    passage_id UNINDEXED,
                    paper_id UNINDEXED,
                    title,
                    text,
                    page UNINDEXED,
                    section
                );
                """
            )

    def add(self, paper: Paper) -> None:
        import json

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO papers (id, title, authors_json, year)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    authors_json = excluded.authors_json,
                    year = excluded.year
                """,
                (paper.id, paper.title, json.dumps(paper.authors), paper.year),
            )
            connection.execute("DELETE FROM passages WHERE paper_id = ?", (paper.id,))
            connection.execute("DELETE FROM passage_fts WHERE paper_id = ?", (paper.id,))
            connection.executemany(
                """
                INSERT INTO passages (id, paper_id, text, page, section)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (passage.id, paper.id, passage.text, passage.page, passage.section)
                    for passage in paper.passages
                ],
            )
            connection.executemany(
                """
                INSERT INTO passage_fts (passage_id, paper_id, title, text, page, section)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        passage.id,
                        paper.id,
                        paper.title,
                        passage.text,
                        passage.page,
                        passage.section,
                    )
                    for passage in paper.passages
                ],
            )

    def search(self, query: str, limit: int = 5) -> list[Mapping[str, object]]:
        tokens = self._tokens(query)
        if not tokens:
            return []
        fts_query = " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    paper_id,
                    passage_id,
                    title,
                    text,
                    CAST(page AS INTEGER) AS page,
                    section,
                    bm25(passage_fts, 0.0, 0.0, 2.0, 1.0, 0.0, 0.5) AS rank
                FROM passage_fts
                WHERE passage_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()
        return [
            {
                "paper_id": row["paper_id"],
                "passage_id": row["passage_id"],
                "title": row["title"],
                "page": row["page"],
                "section": row["section"],
                "text": row["text"],
                "score": -float(row["rank"]),
            }
            for row in rows
        ]

    def read(self, paper_id: str, passage_id: str) -> Mapping[str, object]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT p.id AS paper_id, p.title, s.id AS passage_id,
                       s.text, s.page, s.section
                FROM passages s
                JOIN papers p ON p.id = s.paper_id
                WHERE s.paper_id = ? AND s.id = ?
                """,
                (paper_id, passage_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown passage: {paper_id}/{passage_id}")
        return {
            "paper_id": row["paper_id"],
            "passage_id": row["passage_id"],
            "title": row["title"],
            "page": row["page"],
            "section": row["section"],
            "text": row["text"],
            "score": 1.0,
        }
