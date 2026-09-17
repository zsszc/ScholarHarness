from scholar_harness.papers.models import Paper, Passage
from scholar_harness.papers.repository import SQLitePaperRepository


def test_sqlite_repository_persists_and_searches(tmp_path) -> None:
    database = tmp_path / "papers.db"
    repository = SQLitePaperRepository(database)
    repository.add(
        Paper(
            id="persistent-paper",
            title="Reliable Agent Memory",
            authors=["Ada Example"],
            year=2026,
            passages=[
                Passage(
                    id="method-1",
                    page=11,
                    section="Method",
                    text="Evidence provenance prevents unsupported memories.",
                )
            ],
        )
    )

    reopened = SQLitePaperRepository(database)
    hits = reopened.search("evidence memory")
    passage = reopened.read("persistent-paper", "method-1")

    assert hits[0]["paper_id"] == "persistent-paper"
    assert hits[0]["page"] == 11
    assert passage["text"].startswith("Evidence provenance")


def test_reimport_replaces_old_passages(tmp_path) -> None:
    repository = SQLitePaperRepository(tmp_path / "papers.db")
    repository.add(
        Paper(
            id="paper",
            title="First version",
            passages=[Passage(id="old", text="obsolete passage")],
        )
    )
    repository.add(
        Paper(
            id="paper",
            title="Second version",
            passages=[Passage(id="new", text="current evidence")],
        )
    )

    assert repository.search("obsolete") == []
    assert repository.search("current")[0]["passage_id"] == "new"

    with repository.connect() as connection:
        embedded_passages = connection.execute(
            "SELECT passage_id FROM passage_embeddings ORDER BY passage_id"
        ).fetchall()
    assert [row["passage_id"] for row in embedded_passages] == ["new"]


def test_hybrid_search_finds_related_word_form_and_explains_ranking(tmp_path) -> None:
    database = tmp_path / "hybrid.db"
    repository = SQLitePaperRepository(database)
    repository.add(
        Paper(
            id="memory-paper",
            title="Memory Systems",
            passages=[Passage(id="p1", text="Memory storage supports durable recall.")],
        )
    )
    repository.add(
        Paper(
            id="tools-paper",
            title="Tool Protocols",
            passages=[Passage(id="p1", text="JSON schemas validate tool arguments.")],
        )
    )

    assert repository.search("memorization", mode="lexical") == []

    reopened = SQLitePaperRepository(database)
    hits = reopened.search("memorization", mode="hybrid")

    assert hits[0]["paper_id"] == "memory-paper"
    assert hits[0]["retrieval_mode"] == "hybrid"
    assert hits[0]["lexical_rank"] is None
    assert hits[0]["vector_rank"] == 1


def test_hybrid_search_fuses_lexical_and_vector_ranks(tmp_path) -> None:
    repository = SQLitePaperRepository(tmp_path / "fusion.db")
    repository.add(
        Paper(
            id="paper",
            title="Evidence Memory",
            passages=[Passage(id="p1", text="Evidence anchors reliable memory.")],
        )
    )

    hit = repository.search("evidence memory")[0]

    assert hit["lexical_rank"] == 1
    assert hit["vector_rank"] == 1
    assert hit["score"] == 2 / 61
