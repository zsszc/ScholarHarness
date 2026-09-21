from __future__ import annotations

import re
import sqlite3
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Protocol

from scholar_harness.papers.embeddings import EmbeddingProvider, HashingEmbeddingProvider
from scholar_harness.papers.models import Paper, PaperSummary, Passage
from scholar_harness.storage.sqlite import configure_sqlite_database, connect_sqlite

_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
_MIN_VECTOR_SIMILARITY = 0.05


class PaperRepository(Protocol):
    def add(self, paper: Paper) -> None: ...

    def list(self, limit: int = 100) -> list[PaperSummary]: ...

    def search(
        self, query: str, limit: int = 5, mode: str = "hybrid"
    ) -> list[Mapping[str, object]]: ...

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

    def list(self, limit: int = 100) -> list[PaperSummary]:
        papers = sorted(
            self._papers.values(),
            key=lambda paper: (paper.title.casefold(), paper.id),
        )
        return [
            PaperSummary(
                id=paper.id,
                title=paper.title,
                authors=paper.authors,
                year=paper.year,
                passage_count=len(paper.passages),
            )
            for paper in papers[:limit]
        ]

    def search(
        self, query: str, limit: int = 5, mode: str = "hybrid"
    ) -> list[Mapping[str, object]]:
        if mode not in {"lexical", "hybrid"}:
            raise ValueError(f"Unknown retrieval mode: {mode}")
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
        results = []
        for rank, hit in enumerate(hits[:limit], start=1):
            results.append(
                {
                    **hit,
                    "retrieval_mode": mode,
                    "lexical_rank": rank,
                    "vector_rank": None,
                }
            )
        return results

    def read(self, paper_id: str, passage_id: str) -> Mapping[str, object]:
        paper = self._papers.get(paper_id)
        if paper is None:
            raise KeyError(f"Unknown paper: {paper_id}")
        for passage in paper.passages:
            if passage.id == passage_id:
                return self._hit(paper, passage, 1.0)
        raise KeyError(f"Unknown passage: {paper_id}/{passage_id}")



class SQLitePaperRepository(PassageResultMixin):
    """Persistent paper storage with FTS5 and exact local vector retrieval."""

    def __init__(
        self,
        database: Path | str,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.database = Path(database)
        self.embedding_provider = embedding_provider or HashingEmbeddingProvider()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        return connect_sqlite(self.database)

    def _initialize(self) -> None:
        with self.connect() as connection:
            configure_sqlite_database(connection, self.database)
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

                CREATE TABLE IF NOT EXISTS passage_embeddings (
                    paper_id TEXT NOT NULL,
                    passage_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    dimensions INTEGER NOT NULL,
                    vector BLOB NOT NULL,
                    PRIMARY KEY (paper_id, passage_id, provider),
                    FOREIGN KEY (paper_id, passage_id)
                        REFERENCES passages(paper_id, id) ON DELETE CASCADE
                );
                """
            )

    def add(self, paper: Paper) -> None:
        import json

        embedding_texts = [f"{paper.title}\n{passage.text}" for passage in paper.passages]
        vectors = self.embedding_provider.embed(embedding_texts)
        if len(vectors) != len(paper.passages):
            raise ValueError("Embedding provider returned an unexpected vector count")
        for vector in vectors:
            if len(vector) != self.embedding_provider.dimensions:
                raise ValueError("Embedding provider returned an unexpected dimension")

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
            connection.executemany(
                """
                INSERT INTO passage_embeddings
                    (paper_id, passage_id, provider, dimensions, vector)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        paper.id,
                        passage.id,
                        self.embedding_provider.provider_id,
                        self.embedding_provider.dimensions,
                        self._pack_vector(vector),
                    )
                    for passage, vector in zip(paper.passages, vectors, strict=True)
                ],
            )

    def list(self, limit: int = 100) -> list[PaperSummary]:
        import json

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT p.id, p.title, p.authors_json, p.year,
                       COUNT(s.id) AS passage_count
                FROM papers p
                LEFT JOIN passages s ON s.paper_id = p.id
                GROUP BY p.id, p.title, p.authors_json, p.year
                ORDER BY lower(p.title), p.id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            PaperSummary(
                id=row["id"],
                title=row["title"],
                authors=json.loads(row["authors_json"]),
                year=row["year"],
                passage_count=row["passage_count"],
            )
            for row in rows
        ]

    @staticmethod
    def _pack_vector(vector: list[float]) -> bytes:
        return struct.pack(f"<{len(vector)}f", *vector)

    @staticmethod
    def _unpack_vector(data: bytes, dimensions: int) -> tuple[float, ...]:
        expected_bytes = dimensions * 4
        if len(data) != expected_bytes:
            raise ValueError("Stored embedding has an invalid byte length")
        return struct.unpack(f"<{dimensions}f", data)

    def _lexical_search(self, query: str, limit: int) -> list[dict[str, object]]:
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

    def _vector_search(self, query: str, limit: int) -> list[dict[str, object]]:
        query_vector = self.embedding_provider.embed([query])[0]
        if not any(query_vector):
            return []
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT p.id AS paper_id, s.id AS passage_id, p.title, s.text,
                       s.page, s.section, e.dimensions, e.vector
                FROM passage_embeddings e
                JOIN passages s ON s.paper_id = e.paper_id AND s.id = e.passage_id
                JOIN papers p ON p.id = s.paper_id
                WHERE e.provider = ? AND e.dimensions = ?
                """,
                (self.embedding_provider.provider_id, self.embedding_provider.dimensions),
            ).fetchall()

        hits: list[dict[str, object]] = []
        for row in rows:
            vector = self._unpack_vector(row["vector"], row["dimensions"])
            similarity = sum(
                left * right for left, right in zip(query_vector, vector, strict=True)
            )
            if similarity >= _MIN_VECTOR_SIMILARITY:
                hits.append(
                    {
                        "paper_id": row["paper_id"],
                        "passage_id": row["passage_id"],
                        "title": row["title"],
                        "page": row["page"],
                        "section": row["section"],
                        "text": row["text"],
                        "score": float(similarity),
                    }
                )
        hits.sort(
            key=lambda item: (
                -float(item["score"]),
                str(item["paper_id"]),
                str(item["passage_id"]),
            )
        )
        return hits[:limit]

    def component_search(
        self,
        query: str,
        limit: int = 5,
        component: Literal["lexical", "vector"] = "lexical",
    ) -> list[Mapping[str, object]]:
        """Return one inspectable retrieval component for offline evaluation."""
        if limit < 1:
            raise ValueError("Search limit must be at least 1")
        if component not in {"lexical", "vector"}:
            raise ValueError(f"Unknown retrieval component: {component}")
        hits = (
            self._lexical_search(query, limit)
            if component == "lexical"
            else self._vector_search(query, limit)
        )
        rank_name = "lexical_rank" if component == "lexical" else "vector_rank"
        other_rank = "vector_rank" if component == "lexical" else "lexical_rank"
        return [
            {
                **hit,
                "retrieval_mode": component,
                rank_name: rank,
                other_rank: None,
            }
            for rank, hit in enumerate(hits, start=1)
        ]

    def search(
        self, query: str, limit: int = 5, mode: str = "hybrid"
    ) -> list[Mapping[str, object]]:
        if mode not in {"lexical", "hybrid"}:
            raise ValueError(f"Unknown retrieval mode: {mode}")
        candidate_limit = max(limit * 4, 50)
        lexical = self._lexical_search(query, candidate_limit)
        if mode == "lexical":
            return [
                {
                    **hit,
                    "retrieval_mode": "lexical",
                    "lexical_rank": rank,
                    "vector_rank": None,
                }
                for rank, hit in enumerate(lexical[:limit], start=1)
            ]

        vector = self._vector_search(query, candidate_limit)
        fused: dict[tuple[str, str], dict[str, object]] = {}
        for component, rank_name in ((lexical, "lexical_rank"), (vector, "vector_rank")):
            for rank, hit in enumerate(component, start=1):
                key = (str(hit["paper_id"]), str(hit["passage_id"]))
                result = fused.setdefault(
                    key,
                    {
                        **hit,
                        "score": 0.0,
                        "retrieval_mode": "hybrid",
                        "lexical_rank": None,
                        "vector_rank": None,
                    },
                )
                result[rank_name] = rank
                result["score"] = float(result["score"]) + (1.0 / (60 + rank))

        results = list(fused.values())
        results.sort(
            key=lambda item: (
                -float(item["score"]),
                str(item["paper_id"]),
                str(item["passage_id"]),
            )
        )
        return results[:limit]

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
