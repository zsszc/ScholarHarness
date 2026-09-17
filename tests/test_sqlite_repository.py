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
