from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import Annotated, Any

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, Response

from scholar_harness.chat_sessions import (
    ChatConfigurationError,
    ChatSession,
    ChatSessionInfo,
    ChatSessionManager,
    create_default_chat_manager,
)
from scholar_harness.evaluations.models import (
    EvaluationCase,
    EvaluationCaseInput,
    EvaluationExecution,
    EvaluationResult,
)
from scholar_harness.evaluations.repository import SQLiteEvaluationRepository
from scholar_harness.evaluations.runner import EvaluationExecutionError, EvaluationRunner
from scholar_harness.evaluations.service import EvaluationConflictError, TraceEvaluator
from scholar_harness.memory.models import Memory, MemoryStatus
from scholar_harness.memory.repository import SQLiteMemoryRepository
from scholar_harness.memory.tools import build_memory_tools
from scholar_harness.papers.models import Paper, PaperSummary
from scholar_harness.papers.pdf import PdfIngestor
from scholar_harness.papers.repository import PaperRepository, SQLitePaperRepository
from scholar_harness.papers.tools import build_paper_tools
from scholar_harness.traces.models import AgentRun, ToolExecution, TraceEvent
from scholar_harness.traces.repository import SQLiteTraceRepository
from scholar_harness.workbench import WORKBENCH_HTML

MAX_PDF_BYTES = 50 * 1024 * 1024


def create_app(
    repository: PaperRepository | None = None,
    pdf_ingestor: PdfIngestor | None = None,
    memory_repository: SQLiteMemoryRepository | None = None,
    trace_repository: SQLiteTraceRepository | None = None,
    chat_session_manager: ChatSessionManager | None = None,
    evaluation_repository: SQLiteEvaluationRepository | None = None,
) -> FastAPI:
    paper_repository = repository or SQLitePaperRepository("data/scholar_harness.db")
    memories = memory_repository or SQLiteMemoryRepository("data/scholar_harness.db")
    traces = trace_repository or SQLiteTraceRepository("data/scholar_harness.db")
    evaluations = evaluation_repository or SQLiteEvaluationRepository(traces.database)
    evaluator = TraceEvaluator(traces, evaluations)
    ingestor = pdf_ingestor or PdfIngestor()
    tools = build_paper_tools(paper_repository)
    tools.extend(build_memory_tools(memories, paper_repository))
    chats = chat_session_manager or create_default_chat_manager(tools=tools, traces=traces)
    evaluation_runner = EvaluationRunner(chats, evaluations, evaluator)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        await chats.close_all()

    app = FastAPI(title="ScholarHarness", version="0.1.0", lifespan=lifespan)

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
              <li><a href="/workbench">Open Workbench</a></li>
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

    @app.get("/workbench", response_class=HTMLResponse)
    async def workbench() -> str:
        return WORKBENCH_HTML

    @app.get("/internal/tools")
    async def tool_schemas() -> dict[str, object]:
        return tools.schemas()

    @app.post("/chat/sessions", status_code=201)
    async def create_chat_session() -> ChatSessionInfo:
        try:
            session = await chats.create()
        except ChatConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return await session.info()

    @app.get("/chat/sessions")
    async def list_chat_sessions() -> list[ChatSessionInfo]:
        return await chats.list()

    @app.get("/chat/sessions/{session_id}")
    async def get_chat_session(session_id: str) -> ChatSessionInfo:
        session = await _get_chat_session(chats, session_id)
        return await session.info()

    @app.get("/chat/sessions/{session_id}/entries")
    async def get_chat_entries(session_id: str) -> list[dict[str, Any]]:
        session = await _get_chat_session(chats, session_id)
        entries = await session.entries()
        return [entry.model_dump(mode="json") for entry in entries]

    @app.delete("/chat/sessions/{session_id}", status_code=204)
    async def delete_chat_session(session_id: str) -> Response:
        await chats.delete(session_id)
        return Response(status_code=204)

    @app.websocket("/chat/sessions/{session_id}/stream")
    async def chat_stream(websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        try:
            session = await chats.get(session_id)
        except KeyError:
            await websocket.send_json(
                _socket_error("session_not_found", f"Unknown chat session: {session_id}")
            )
            await websocket.close(code=4404)
            return
        if not session.attach():
            await websocket.send_json(
                _socket_error("session_connected", "Chat session already has a connection")
            )
            await websocket.close(code=4409)
            return

        outgoing: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        sender = asyncio.create_task(_send_chat_messages(websocket, outgoing))
        turn: asyncio.Task[None] | None = None
        await outgoing.put(
            {"type": "session_ready", "session": (await session.info()).model_dump(mode="json")}
        )
        try:
            while True:
                try:
                    command = await websocket.receive_json()
                except ValueError:
                    await outgoing.put(
                        _socket_error("invalid_json", "WebSocket message must be JSON")
                    )
                    continue
                if not isinstance(command, dict):
                    await outgoing.put(
                        _socket_error("invalid_command", "Command must be a JSON object")
                    )
                    continue
                command_type = command.get("type")
                if command_type == "prompt":
                    content = command.get("content")
                    if not isinstance(content, str) or not content.strip():
                        await outgoing.put(
                            _socket_error("invalid_prompt", "Prompt content cannot be empty")
                        )
                    elif turn is not None and not turn.done():
                        await outgoing.put(
                            _socket_error("turn_active", "A turn is already active")
                        )
                    else:
                        turn = asyncio.create_task(
                            _produce_chat_turn(session, content, outgoing)
                        )
                elif command_type == "abort":
                    await session.abort()
                    await outgoing.put({"type": "command_result", "command": "abort"})
                elif command_type == "compact":
                    instruction = command.get("instructions")
                    if instruction is not None and not isinstance(instruction, str):
                        await outgoing.put(
                            _socket_error(
                                "invalid_command", "Compact instructions must be text"
                            )
                        )
                        continue
                    await _run_chat_command(
                        outgoing,
                        "compact",
                        session.compact(instruction.strip() or None if instruction else None),
                        session,
                    )
                elif command_type == "fork":
                    entry_id = command.get("entry_id")
                    if not isinstance(entry_id, str) or not entry_id:
                        await outgoing.put(
                            _socket_error("invalid_command", "Fork requires entry_id")
                        )
                        continue
                    await _run_chat_command(
                        outgoing, "fork", session.fork(entry_id), session
                    )
                elif command_type == "entries":
                    try:
                        entries = await session.entries()
                    except Exception as exc:
                        await outgoing.put(_socket_error("command_failed", str(exc)))
                    else:
                        await outgoing.put(
                            {
                                "type": "command_result",
                                "command": "entries",
                                "entries": [
                                    entry.model_dump(mode="json") for entry in entries
                                ],
                                "session": (await session.info()).model_dump(mode="json"),
                            }
                        )
                else:
                    await outgoing.put(
                        _socket_error("unknown_command", f"Unknown command: {command_type}")
                    )
        except WebSocketDisconnect:
            pass
        finally:
            session.detach()
            if turn is not None and not turn.done():
                await session.abort()
                await asyncio.gather(turn, return_exceptions=True)
            await outgoing.put(None)
            with suppress(Exception):
                await sender

    @app.post("/papers", status_code=201)
    async def add_paper(paper: Paper) -> Paper:
        paper_repository.add(paper)
        return paper

    @app.get("/papers")
    async def list_papers(
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[PaperSummary]:
        return paper_repository.list(limit=limit)

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

    @app.post("/evaluations/cases", status_code=201)
    async def create_evaluation_case(value: EvaluationCaseInput) -> EvaluationCase:
        return evaluations.create_case(value)

    @app.put("/evaluations/cases/{case_id}")
    async def update_evaluation_case(
        case_id: str, value: EvaluationCaseInput
    ) -> EvaluationCase:
        try:
            return evaluations.update_case(case_id, value)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/evaluations/cases")
    async def list_evaluation_cases(
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[EvaluationCase]:
        return evaluations.list_cases(limit=limit)

    @app.get("/evaluations/cases/{case_id}")
    async def get_evaluation_case(case_id: str) -> EvaluationCase:
        try:
            return evaluations.get_case(case_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/evaluations/cases/{case_id}/runs/{run_id}", status_code=201)
    async def evaluate_trace_run(case_id: str, run_id: str) -> EvaluationResult:
        try:
            return evaluator.evaluate(case_id, run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except EvaluationConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/evaluations/cases/{case_id}/execute", status_code=201)
    async def execute_evaluation_case(case_id: str) -> EvaluationExecution:
        try:
            return await evaluation_runner.execute(case_id)
        except ChatConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (EvaluationConflictError, EvaluationExecutionError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/evaluations/results")
    async def list_evaluation_results(
        case_id: Annotated[str | None, Query()] = None,
        run_id: Annotated[str | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[EvaluationResult]:
        return evaluations.list_results(
            case_id=case_id, run_id=run_id, limit=limit
        )

    @app.get("/evaluations/results/{result_id}")
    async def get_evaluation_result(result_id: str) -> EvaluationResult:
        try:
            return evaluations.get_result(result_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


async def _get_chat_session(
    manager: ChatSessionManager, session_id: str
) -> ChatSession:
    try:
        return await manager.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def _send_chat_messages(
    websocket: WebSocket,
    outgoing: asyncio.Queue[dict[str, Any] | None],
) -> None:
    while True:
        message = await outgoing.get()
        if message is None:
            return
        await websocket.send_json(message)


async def _produce_chat_turn(
    session: ChatSession,
    prompt: str,
    outgoing: asyncio.Queue[dict[str, Any] | None],
) -> None:
    error_message: str | None = None
    try:
        async for event in session.stream(prompt):
            await outgoing.put({"type": "event", "event": event.model_dump(mode="json")})
    except Exception as exc:
        error_message = str(exc)
        await outgoing.put(_socket_error("turn_failed", error_message))
    finally:
        result = {
            "type": "turn_complete",
            "session": (await session.info()).model_dump(mode="json"),
        }
        if error_message is not None:
            result["error"] = error_message
        await outgoing.put(result)


async def _run_chat_command(
    outgoing: asyncio.Queue[dict[str, Any] | None],
    command: str,
    operation: Any,
    session: ChatSession,
) -> None:
    try:
        await operation
    except (KeyError, RuntimeError, ValueError) as exc:
        await outgoing.put(_socket_error("command_failed", str(exc)))
    else:
        await outgoing.put(
            {
                "type": "command_result",
                "command": command,
                "session": (await session.info()).model_dump(mode="json"),
            }
        )


def _socket_error(code: str, message: str) -> dict[str, str]:
    return {"type": "error", "code": code, "message": message}
