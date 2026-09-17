from fastapi.testclient import TestClient

from scholar_harness.api import create_app
from scholar_harness.memory.repository import SQLiteMemoryRepository
from scholar_harness.papers.models import Paper, Passage
from scholar_harness.papers.pdf import PdfImportResult
from scholar_harness.papers.repository import InMemoryPaperRepository


class FakePdfIngestor:
    def ingest(self, content, **_kwargs) -> PdfImportResult:
        assert content.startswith(b"%PDF-")
        return PdfImportResult(
            paper=Paper(
                id="uploaded-paper",
                title="Uploaded Paper",
                passages=[Passage(id="p0001-c0001", page=1, text="retrievable evidence")],
            ),
            page_count=1,
            skipped_pages=0,
        )


def test_health_and_tool_flow() -> None:
    client = TestClient(create_app())
    assert client.get("/health").json() == {"status": "ok"}

    paper = {
        "id": "paper-api",
        "title": "Tool Calling",
        "passages": [{"id": "passage-api", "text": "Tools require schemas.", "page": 2}],
    }
    assert client.post("/papers", json=paper).status_code == 201

    response = client.post(
        "/internal/tools/search_papers",
        json={"query": "tools schemas", "limit": 5},
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["paper_id"] == "paper-api"


def test_home_page_and_invalid_pdf() -> None:
    client = TestClient(create_app())

    assert client.get("/").status_code == 200
    assert client.get("/favicon.ico").status_code == 204
    response = client.post(
        "/papers/import/pdf",
        files={"file": ("notes.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded file is not a PDF"


def test_pdf_upload_is_added_to_tool_repository() -> None:
    repository = InMemoryPaperRepository()
    client = TestClient(create_app(repository, FakePdfIngestor()))

    imported = client.post(
        "/papers/import/pdf",
        files={"file": ("paper.pdf", b"%PDF-fake", "application/pdf")},
    )
    searched = client.post(
        "/internal/tools/search_papers",
        json={"query": "retrievable evidence", "limit": 5},
    )

    assert imported.status_code == 201
    assert imported.json()["passage_count"] == 1
    assert searched.json()["items"][0]["paper_id"] == "uploaded-paper"


def test_memory_confirmation_api(tmp_path) -> None:
    repository = InMemoryPaperRepository()
    memory_repository = SQLiteMemoryRepository(tmp_path / "memory.db")
    memory = memory_repository.create_candidate(
        content="Candidate memory",
        kind="semantic",
        scope="global",
        confidence=0.5,
        evidence=[],
    )
    client = TestClient(
        create_app(repository=repository, memory_repository=memory_repository)
    )

    listed = client.get("/memories", params={"status": "candidate"})
    confirmed = client.post(f"/memories/{memory.id}/confirm")

    assert listed.status_code == 200
    assert listed.json()[0]["id"] == memory.id
    assert confirmed.json()["status"] == "confirmed"
