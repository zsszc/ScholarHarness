from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, Response

from scholar_harness.memory.models import Memory, MemoryStatus
from scholar_harness.memory.repository import SQLiteMemoryRepository
from scholar_harness.memory.tools import build_memory_tools
from scholar_harness.papers.models import Paper
from scholar_harness.papers.pdf import PdfIngestor
from scholar_harness.papers.repository import PaperRepository, SQLitePaperRepository
from scholar_harness.papers.tools import build_paper_tools
from scholar_harness.traces.models import AgentRun, ToolExecution, TraceEvent
from scholar_harness.traces.repository import SQLiteTraceRepository

MAX_PDF_BYTES = 50 * 1024 * 1024


def create_app(
    repository: PaperRepository | None = None,
    pdf_ingestor: PdfIngestor | None = None,
    memory_repository: SQLiteMemoryRepository | None = None,
    trace_repository: SQLiteTraceRepository | None = None,
) -> FastAPI:
    paper_repository = repository or SQLitePaperRepository("data/scholar_harness.db")
    memories = memory_repository or SQLiteMemoryRepository("data/scholar_harness.db")
    traces = trace_repository or SQLiteTraceRepository("data/scholar_harness.db")
    ingestor = pdf_ingestor or PdfIngestor()
    tools = build_paper_tools(paper_repository)
    tools.extend(build_memory_tools(memories, paper_repository))
    app = FastAPI(title="ScholarHarness", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return """
        <!doctype html>
        <html lang="zh-CN">
          <head><meta charset="utf-8"><title>ScholarHarness</title></head>
          <body style="font-family: system-ui; max-width: 760px; margin: 64px auto;">
            <h1>ScholarHarness</h1>
            <p>Python research-agent tool service is running.</p>
            <ul>
              <li><a href="/docs">OpenAPI tools</a></li>
              <li><a href="/health">Health check</a></li>
              <li><a href="/memories">Memory candidates</a></li>
              <li><a href="/runs">Agent runs</a></li>
            </ul>
          </body>
        </html>
        """

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/internal/tools")
    async def tool_schemas() -> dict[str, object]:
        return tools.schemas()

    @app.post("/papers", status_code=201)
    async def add_paper(paper: Paper) -> Paper:
        paper_repository.add(paper)
        return paper

    @app.post("/papers/import/pdf", status_code=201)
    async def import_pdf(
        file: Annotated[UploadFile, File()],
        paper_id: Annotated[str | None, Query()] = None,
        title: Annotated[str | None, Query()] = None,
    ) -> dict[str, object]:
        content = await file.read(MAX_PDF_BYTES + 1)
        if len(content) > MAX_PDF_BYTES:
            raise HTTPException(status_code=413, detail="PDF exceeds the 50 MiB limit")
        try:
            result = ingestor.ingest(
                content,
                filename=file.filename,
                paper_id=paper_id,
                title=title,
            )
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        paper_repository.add(result.paper)
        return {
            "paper_id": result.paper.id,
            "title": result.paper.title,
            "page_count": result.page_count,
            "passage_count": result.passage_count,
            "skipped_pages": result.skipped_pages,
        }

    @app.post("/internal/tools/{tool_name}")
    async def execute_tool(tool_name: str, arguments: dict[str, object]) -> object:
        try:
            return await tools.execute(tool_name, arguments)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/memories")
    async def list_memories(
        status: Annotated[MemoryStatus | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[Memory]:
        return memories.list(status=status, limit=limit)

    @app.post("/memories/{memory_id}/confirm")
    async def confirm_memory(memory_id: str) -> Memory:
        try:
            return memories.set_status(memory_id, "confirmed")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/memories/{memory_id}/reject")
    async def reject_memory(memory_id: str) -> Memory:
        try:
            return memories.set_status(memory_id, "rejected")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/runs")
    async def list_runs(
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[AgentRun]:
        return traces.list_runs(limit=limit)

    @app.get("/runs/{run_id}")
    async def get_run(run_id: str) -> AgentRun:
        try:
            return traces.get_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/runs/{run_id}/events")
    async def list_run_events(run_id: str) -> list[TraceEvent]:
        try:
            return traces.list_events(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/runs/{run_id}/tools")
    async def list_run_tools(run_id: str) -> list[ToolExecution]:
        try:
            return traces.list_tool_executions(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app
