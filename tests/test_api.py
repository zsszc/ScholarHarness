from fastapi.testclient import TestClient

import scholar_harness.api as api_module
from scholar_harness.api import create_app
from scholar_harness.core.events import AgentEvent
from scholar_harness.memory.context import MemoryContextPolicy
from scholar_harness.memory.repository import SQLiteMemoryRepository
from scholar_harness.papers.models import Paper, Passage
from scholar_harness.papers.pdf import PdfImportResult
from scholar_harness.papers.repository import InMemoryPaperRepository
from scholar_harness.traces.repository import SQLiteTraceRepository


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


class StubChatManager:
    async def close_all(self) -> None:
        return None


def test_default_api_chat_uses_memory_context_policy(tmp_path, monkeypatch) -> None:
    memories = SQLiteMemoryRepository(tmp_path / "context.db")
    captured = {}

    def capture_manager(**kwargs):
        captured.update(kwargs)
        return StubChatManager()

    monkeypatch.setattr(api_module, "create_default_chat_manager", capture_manager)

    create_app(
        repository=InMemoryPaperRepository(),
        memory_repository=memories,
        trace_repository=SQLiteTraceRepository(tmp_path / "context.db"),
    )

    assert isinstance(captured["context_provider"], MemoryContextPolicy)


def test_health_and_tool_flow(tmp_path) -> None:
    client = TestClient(
        create_app(
            repository=InMemoryPaperRepository(),
            memory_repository=SQLiteMemoryRepository(tmp_path / "api.db"),
            trace_repository=SQLiteTraceRepository(tmp_path / "api.db"),
        )
    )
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
    papers = client.get("/papers")
    assert papers.status_code == 200
    assert papers.json() == [
        {
            "id": "paper-api",
            "title": "Tool Calling",
            "authors": [],
            "year": None,
            "passage_count": 1,
        }
    ]


def test_home_page_and_invalid_pdf() -> None:
    client = TestClient(create_app())

    assert client.get("/").status_code == 200
    assert 'href="/workbench"' in client.get("/").text
    workbench = client.get("/workbench")
    assert workbench.status_code == 200
    assert "ScholarHarness · Workbench" in workbench.text
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


def test_memory_supersession_api_reports_transition_conflicts(tmp_path) -> None:
    memories = SQLiteMemoryRepository(tmp_path / "supersede-api.db")
    old = memories.create_candidate(
        content="Old rule",
        kind="semantic",
        scope="global",
        confidence=0.5,
        evidence=[],
    )
    replacement = memories.create_candidate(
        content="New rule",
        kind="semantic",
        scope="global",
        confidence=0.9,
        evidence=[],
    )
    memories.set_status(old.id, "confirmed")
    memories.set_status(replacement.id, "confirmed")
    client = TestClient(create_app(memory_repository=memories))

    changed = client.post(
        f"/memories/{old.id}/supersede",
        json={"replacement_id": replacement.id},
    )
    missing = client.post(
        "/memories/missing/supersede",
        json={"replacement_id": replacement.id},
    )
    conflict = client.post(
        f"/memories/{replacement.id}/supersede",
        json={"replacement_id": replacement.id},
    )

    assert changed.status_code == 200
    assert changed.json()["superseded_by_id"] == replacement.id
    assert missing.status_code == 404
    assert conflict.status_code == 409


def test_http_tool_context_owns_memory_provenance(tmp_path) -> None:
    repository = InMemoryPaperRepository()
    repository.add(
        Paper(
            id="paper-context",
            title="Trusted Context",
            passages=[
                Passage(
                    id="passage-context",
                    page=5,
                    text="Trusted execution context prevents provenance spoofing.",
                )
            ],
        )
    )
    memories = SQLiteMemoryRepository(tmp_path / "http-context.db")
    client = TestClient(
        create_app(repository=repository, memory_repository=memories)
    )
    arguments = {
        "content": "Provenance must be runtime owned.",
        "scope": "session",
        "evidence": [
            {
                "paper_id": "paper-context",
                "passage_id": "passage-context",
                "quote": "Trusted execution context prevents provenance spoofing.",
            }
        ],
    }

    assert client.post("/internal/tools/save_memory", json=arguments).status_code == 400
    spoofed = client.post(
        "/internal/tools/save_memory",
        json={**arguments, "source_session_id": "spoofed"},
        headers={"X-Scholar-Session-Id": "trusted-session"},
    )
    assert spoofed.status_code == 400
    saved = client.post(
        "/internal/tools/save_memory",
        json=arguments,
        headers={
            "X-Scholar-Runtime-Type": "pi",
            "X-Scholar-Session-Id": "trusted-session",
            "X-Scholar-Entry-Id": "trusted-entry",
            "X-Scholar-Trace-Run-Id": "trusted-run",
            "X-Scholar-Tool-Call-Id": "trusted-call",
        },
    )

    assert saved.status_code == 200
    memory = memories.get(saved.json()["memory"]["id"])
    assert memory.source_session_id == "trusted-session"
    assert memory.source_entry_id == "trusted-entry"
    assert memory.trace_run_id == "trusted-run"
    assert memory.source_tool_call_id == "trusted-call"


def test_trace_read_apis(tmp_path) -> None:
    trace_repository = SQLiteTraceRepository(tmp_path / "trace.db")
    run = trace_repository.create_run("fake", external_session_id="session-api")
    trace_repository.append_event(
        run.id,
        AgentEvent(type="agent_start", session_id="session-api"),
    )
    trace_repository.finish_run(run.id, "completed")
    client = TestClient(create_app(trace_repository=trace_repository))

    runs = client.get("/runs")
    events = client.get(f"/runs/{run.id}/events")
    tools = client.get(f"/runs/{run.id}/tools")
    missing = client.get("/runs/missing")

    assert runs.status_code == 200
    assert runs.json()[0]["id"] == run.id
    assert events.json()[0]["event_type"] == "agent_start"
    assert tools.json() == []
    assert missing.status_code == 404
