from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from scholar_harness.api import create_app
from scholar_harness.chat_sessions import (
    ChatConfigurationError,
    ChatSessionManager,
    create_default_chat_manager,
)
from scholar_harness.cli import main, run_configured_evaluation
from scholar_harness.core.events import AgentEvent
from scholar_harness.evaluations.models import (
    EvaluationCaseInput,
    EvaluationExpectations,
)
from scholar_harness.evaluations.repository import SQLiteEvaluationRepository
from scholar_harness.evaluations.runner import EvaluationExecutionError, EvaluationRunner
from scholar_harness.evaluations.service import EvaluationConflictError, TraceEvaluator
from scholar_harness.runtimes.model import (
    ModelMessage,
    ModelResponse,
    ModelToolDefinition,
)
from scholar_harness.runtimes.openai_compatible import ModelAdapterError
from scholar_harness.tools.registry import ToolRegistry
from scholar_harness.traces.repository import SQLiteTraceRepository


def case_input(**expectations) -> EvaluationCaseInput:
    return EvaluationCaseInput(
        name="Evidence workflow",
        prompt="Find and cite evidence.",
        expectations=EvaluationExpectations(**expectations),
        pass_threshold=1.0,
    )


def completed_run(
    traces: SQLiteTraceRepository,
    *,
    answer: str = "Evidence found.",
    valid_citation: bool = True,
    failed_search: bool = False,
):
    run = traces.create_run("test-runtime", external_session_id="session-eval")
    traces.append_event(
        run.id,
        AgentEvent(type="agent_start", session_id="session-eval"),
    )
    traces.append_event(
        run.id,
        AgentEvent(
            type="message_update",
            session_id="session-eval",
            data={"delta": answer},
        ),
    )
    for call_id, name, result, is_error in (
        (
            "search-1",
            "search_papers",
            {"items": []},
            failed_search,
        ),
        (
            "citation-1",
            "validate_citation",
            {"valid": valid_citation},
            False,
        ),
    ):
        traces.append_event(
            run.id,
            AgentEvent(
                type="tool_execution_start",
                session_id="session-eval",
                data={"toolCallId": call_id, "toolName": name, "args": {}},
            ),
        )
        traces.append_event(
            run.id,
            AgentEvent(
                type="tool_execution_end",
                session_id="session-eval",
                data={
                    "toolCallId": call_id,
                    "toolName": name,
                    "result": result,
                    "isError": is_error,
                },
            ),
        )
    return traces.finish_run(run.id, "completed")


class ScriptedExecutionAdapter:
    def __init__(self, response: ModelResponse) -> None:
        self.response = response
        self.closed = 0
        self.prompts: list[str] = []

    async def complete(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition],
    ) -> ModelResponse:
        self.prompts.append(messages[-1].content)
        return self.response

    async def aclose(self) -> None:
        self.closed += 1


class FailingExecutionAdapter(ScriptedExecutionAdapter):
    async def complete(self, messages, tools) -> ModelResponse:
        raise ModelAdapterError("provider secret https://private.invalid/v1")


class BlockingExecutionAdapter(ScriptedExecutionAdapter):
    def __init__(self) -> None:
        super().__init__(ModelResponse())
        self.entered = asyncio.Event()
        self.cancelled = False

    async def complete(self, messages, tools) -> ModelResponse:
        self.entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("unreachable")


def execution_manager(database, adapters) -> ChatSessionManager:
    remaining = list(adapters)
    return ChatSessionManager(
        tools=ToolRegistry(),
        traces=SQLiteTraceRepository(database),
        adapter_factory=lambda: remaining.pop(0),
    )


def test_expectation_validation_rejects_empty_and_contradictory_cases() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        EvaluationExpectations()
    with pytest.raises(ValidationError, match="both required and forbidden"):
        EvaluationExpectations(required_tools=["search"], forbidden_tools=["search"])
    with pytest.raises(ValidationError, match="cannot be empty"):
        EvaluationExpectations(answer_contains=["  "])
    with pytest.raises(ValidationError, match="memories cannot be both"):
        EvaluationExpectations(
            required_memory_ids=["memory-1"],
            forbidden_memory_ids=["memory-1"],
        )

    normalized = EvaluationExpectations(
        required_memory_ids=[" memory-1 ", "memory-1"],
        max_context_items=2,
    )
    assert normalized.required_memory_ids == ["memory-1"]


def test_evaluator_checks_persisted_memory_context_without_content(tmp_path) -> None:
    database = tmp_path / "memory-eval.db"
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    case = evaluations.create_case(
        case_input(
            context_status="selected",
            required_memory_ids=["memory-1"],
            forbidden_memory_ids=["memory-secret"],
            max_context_items=2,
        )
    )
    run = completed_run(traces)
    traces.append_event(
        run.id,
        AgentEvent(
            type="context_injection",
            session_id="session-eval",
            data={
                "status": "selected",
                "selected_ids": ["memory-1", "memory-2", "memory-2"],
                "selected_count": 3,
                "content": "must never enter evaluation evidence",
            },
        ),
    )

    result = TraceEvaluator(traces, evaluations).evaluate(case.id, run.id)

    assert result.passed is True
    assert [check.id for check in result.checks] == [
        "context_status",
        "required_memory:memory-1",
        "forbidden_memory:memory-secret",
        "context_item_limit",
    ]
    assert all(check.passed for check in result.checks)
    assert "must never" not in result.model_dump_json()
    assert result.checks[0].observed["reported_selected_count"] == 3
    assert result.checks[0].observed["selected_ids"] == ["memory-1", "memory-2"]


@pytest.mark.parametrize("payload", [None, {"status": "selected", "selected_ids": [1]}])
def test_missing_or_malformed_context_fails_safely(tmp_path, payload) -> None:
    database = tmp_path / f"invalid-{payload is None}.db"
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    case = evaluations.create_case(case_input(required_memory_ids=["memory-1"]))
    run = completed_run(traces)
    if payload is not None:
        payload["selected_count"] = 1
        payload["content"] = "private memory body"
        traces.append_event(
            run.id,
            AgentEvent(
                type="context_injection", session_id="session-eval", data=payload
            ),
        )

    result = TraceEvaluator(traces, evaluations).evaluate(case.id, run.id)

    assert result.passed is False
    assert result.checks[0].observed["reason"] in {
        "missing_event",
        "invalid_payload",
    }
    assert "private memory body" not in result.model_dump_json()


def test_duplicate_context_events_are_invalid_evidence(tmp_path) -> None:
    database = tmp_path / "duplicate-context.db"
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    case = evaluations.create_case(case_input(context_status="selected"))
    run = completed_run(traces)
    for memory_id in ("memory-1", "memory-2"):
        traces.append_event(
            run.id,
            AgentEvent(
                type="context_injection",
                session_id="session-eval",
                data={
                    "status": "selected",
                    "selected_ids": [memory_id],
                    "selected_count": 1,
                },
            ),
        )

    result = TraceEvaluator(traces, evaluations).evaluate(case.id, run.id)

    assert result.passed is False
    assert result.checks[0].observed["reason"] == "duplicate_events"
    assert result.checks[0].observed["selected_ids"] == []


def test_case_repository_persists_updates_and_order(tmp_path) -> None:
    database = tmp_path / "eval.db"
    repository = SQLiteEvaluationRepository(database)
    first = repository.create_case(case_input(terminal_status="completed"))
    second = repository.create_case(case_input(answer_contains=["citation"]))

    updated = repository.update_case(
        first.id,
        EvaluationCaseInput(
            name="Updated workflow",
            prompt="Updated prompt",
            expectations=EvaluationExpectations(max_tool_calls=2),
            pass_threshold=0.5,
        ),
    )
    reopened = SQLiteEvaluationRepository(database)

    assert updated.created_at == first.created_at
    assert updated.updated_at >= first.updated_at
    assert reopened.get_case(first.id).name == "Updated workflow"
    assert {item.id for item in reopened.list_cases()} == {first.id, second.id}
    with pytest.raises(KeyError, match="Unknown evaluation case"):
        reopened.get_case("missing")


def test_evaluator_produces_explainable_checks_for_every_expectation(tmp_path) -> None:
    database = tmp_path / "all-checks.db"
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    case = evaluations.create_case(
        case_input(
            required_tools=["search_papers", "validate_citation"],
            forbidden_tools=["delete_paper"],
            max_tool_calls=3,
            max_duration_ms=10_000,
            require_citation_validation=True,
            answer_contains=["evidence", "FOUND"],
            terminal_status="completed",
        )
    )
    run = completed_run(traces)

    result = TraceEvaluator(traces, evaluations).evaluate(case.id, run.id)

    assert result.score == 1.0
    assert result.passed is True
    assert result.previous_score is None
    assert result.regression is False
    assert {check.id for check in result.checks} == {
        "run_status",
        "required_tool:search_papers",
        "required_tool:validate_citation",
        "forbidden_tool:delete_paper",
        "tool_call_limit",
        "duration_limit",
        "citation_validation",
        "answer_contains:evidence",
        "answer_contains:found",
    }
    required = next(
        check for check in result.checks if check.id == "required_tool:search_papers"
    )
    assert required.observed["tool_call_ids"] == ["search-1"]
    assert evaluations.get_result(result.id) == result


def test_failed_tools_and_missing_answer_reduce_score(tmp_path) -> None:
    database = tmp_path / "failures.db"
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    case = evaluations.create_case(
        case_input(
            required_tools=["search_papers"],
            require_citation_validation=True,
            answer_contains=["required phrase"],
        )
    )
    run = completed_run(
        traces,
        answer="Different answer",
        valid_citation=False,
        failed_search=True,
    )

    result = TraceEvaluator(traces, evaluations).evaluate(case.id, run.id)

    assert result.score == 0.0
    assert result.passed is False
    assert all(not check.passed for check in result.checks)
    required = result.checks[0]
    assert required.observed == {
        "executions": 1,
        "successful": 0,
        "tool_call_ids": ["search-1"],
    }


def test_results_are_idempotent_snapshot_cases_and_detect_regressions(tmp_path) -> None:
    database = tmp_path / "regression.db"
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    case = evaluations.create_case(
        case_input(answer_contains=["evidence"], terminal_status="completed")
    )
    evaluator = TraceEvaluator(traces, evaluations)
    baseline_run = completed_run(traces, answer="Evidence")
    regression_run = completed_run(traces, answer="No match")

    baseline = evaluator.evaluate(case.id, baseline_run.id)
    regression = evaluator.evaluate(case.id, regression_run.id)
    repeated = evaluator.evaluate(case.id, regression_run.id)
    evaluations.update_case(
        case.id,
        EvaluationCaseInput(
            name="Changed later",
            prompt="New prompt",
            expectations=EvaluationExpectations(max_tool_calls=10),
            pass_threshold=0.1,
        ),
    )

    assert baseline.score == 1.0
    assert regression.score == 0.5
    assert regression.previous_score == 1.0
    assert regression.score_delta == -0.5
    assert regression.regression is True
    assert repeated.id == regression.id
    assert len(evaluations.list_results(case_id=case.id)) == 2
    assert evaluations.get_result(baseline.id).case_name == "Evidence workflow"
    assert evaluations.get_result(baseline.id).expectations.answer_contains == [
        "evidence"
    ]


def test_running_trace_is_rejected_without_result(tmp_path) -> None:
    database = tmp_path / "running.db"
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    case = evaluations.create_case(case_input(terminal_status="completed"))
    run = traces.create_run("still-running")

    with pytest.raises(EvaluationConflictError, match="Running traces"):
        TraceEvaluator(traces, evaluations).evaluate(case.id, run.id)
    assert evaluations.list_results() == []


def test_evaluation_api_workflow_and_errors(tmp_path) -> None:
    database = tmp_path / "api-eval.db"
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    run = completed_run(traces)
    running = traces.create_run("running")
    app = create_app(
        trace_repository=traces,
        evaluation_repository=evaluations,
    )
    payload = case_input(
        required_tools=["search_papers"],
        terminal_status="completed",
        context_status="selected",
        required_memory_ids=["memory-api"],
        forbidden_memory_ids=["memory-private"],
        max_context_items=2,
    ).model_dump(mode="json")

    with TestClient(app) as client:
        created = client.post("/evaluations/cases", json=payload)
        assert created.status_code == 201
        case_id = created.json()["id"]
        assert created.json()["expectations"]["required_memory_ids"] == [
            "memory-api"
        ]
        assert client.get("/evaluations/cases").json()[0]["id"] == case_id
        assert client.get(f"/evaluations/cases/{case_id}").status_code == 200

        updated_payload = {**payload, "name": "API updated"}
        updated = client.put(
            f"/evaluations/cases/{case_id}", json=updated_payload
        )
        assert updated.json()["name"] == "API updated"
        evaluated = client.post(f"/evaluations/cases/{case_id}/runs/{run.id}")
        assert evaluated.status_code == 201
        result_id = evaluated.json()["id"]
        assert client.get(f"/evaluations/results/{result_id}").status_code == 200
        assert client.get(
            "/evaluations/results", params={"case_id": case_id}
        ).json()[0]["run_id"] == run.id

        assert client.get("/evaluations/cases/missing").status_code == 404
        assert client.post(
            f"/evaluations/cases/{case_id}/runs/missing"
        ).status_code == 404
        assert client.post(
            f"/evaluations/cases/{case_id}/runs/{running.id}"
        ).status_code == 409


def test_eval_cli_prints_json_and_rejects_unknown_ids(tmp_path, monkeypatch, capsys) -> None:
    database = tmp_path / "cli-eval.db"
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    case = evaluations.create_case(case_input(terminal_status="completed"))
    run = completed_run(traces)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scholar-harness",
            "eval",
            "--case",
            case.id,
            "--run",
            run.id,
            "--database",
            str(database),
        ],
    )

    main()
    output = json.loads(capsys.readouterr().out)
    assert output["case_id"] == case.id
    assert output["run_id"] == run.id
    assert output["passed"] is True

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scholar-harness",
            "eval",
            "--case",
            "missing",
            "--run",
            run.id,
            "--database",
            str(database),
        ],
    )
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2


async def test_runner_executes_stored_prompt_evaluates_and_cleans_session(
    tmp_path,
) -> None:
    database = tmp_path / "runner.db"
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    case = evaluations.create_case(
        case_input(answer_contains=["evidence"], terminal_status="completed")
    )
    adapter = ScriptedExecutionAdapter(ModelResponse(content="Evidence found."))
    sessions = execution_manager(database, [adapter])

    execution = await EvaluationRunner(
        sessions, evaluations, TraceEvaluator(traces, evaluations)
    ).execute(case.id)

    assert execution.result.passed is True
    assert execution.run_id == execution.result.run_id
    assert execution.event_count == 4
    assert execution.runtime_error is None
    assert adapter.prompts == [case.prompt]
    assert adapter.closed == 1
    assert await sessions.list() == []
    assert traces.get_run(execution.run_id).status == "completed"


async def test_runner_evaluates_failed_trace_and_redacts_runtime_error(tmp_path) -> None:
    database = tmp_path / "failed-runner.db"
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    case = evaluations.create_case(case_input(terminal_status="failed"))
    adapter = FailingExecutionAdapter(ModelResponse())
    sessions = execution_manager(database, [adapter])

    execution = await EvaluationRunner(
        sessions, evaluations, TraceEvaluator(traces, evaluations)
    ).execute(case.id)

    assert execution.result.passed is True
    assert execution.result.run_status == "failed"
    assert execution.event_count == 1
    assert execution.runtime_error == "model_error"
    assert "private.invalid" not in execution.model_dump_json()
    assert adapter.closed == 1
    assert await sessions.list() == []


async def test_runner_cleans_session_on_evaluation_failure_and_cancellation(
    tmp_path,
) -> None:
    database = tmp_path / "cleanup.db"
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    case = evaluations.create_case(case_input(terminal_status="completed"))
    first = ScriptedExecutionAdapter(ModelResponse(content="done"))
    sessions = execution_manager(database, [first])

    class BrokenEvaluator:
        def evaluate(self, case_id, run_id):
            raise EvaluationExecutionError("evaluation failed")

    with pytest.raises(EvaluationExecutionError, match="evaluation failed"):
        await EvaluationRunner(sessions, evaluations, BrokenEvaluator()).execute(case.id)
    assert first.closed == 1
    assert await sessions.list() == []

    blocking = BlockingExecutionAdapter()
    blocking_sessions = execution_manager(database, [blocking])
    task = asyncio.create_task(
        EvaluationRunner(
            blocking_sessions,
            evaluations,
            TraceEvaluator(traces, evaluations),
        ).execute(case.id)
    )
    await blocking.entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert blocking.cancelled is True
    assert blocking.closed == 1
    assert await blocking_sessions.list() == []


async def test_parallel_runner_executions_have_distinct_runs(tmp_path) -> None:
    database = tmp_path / "parallel.db"
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    case = evaluations.create_case(case_input(terminal_status="completed"))
    adapters = [
        ScriptedExecutionAdapter(ModelResponse(content="one")),
        ScriptedExecutionAdapter(ModelResponse(content="two")),
    ]
    sessions = execution_manager(database, adapters)
    runner = EvaluationRunner(sessions, evaluations, TraceEvaluator(traces, evaluations))

    first, second = await asyncio.gather(runner.execute(case.id), runner.execute(case.id))

    assert first.run_id != second.run_id
    assert first.result.id != second.result.id
    session_ids = {
        traces.get_run(first.run_id).external_session_id,
        traces.get_run(second.run_id).external_session_id,
    }
    assert len(session_ids) == 2
    assert [adapter.closed for adapter in adapters] == [1, 1]
    assert await sessions.list() == []


def test_evaluation_execution_api_success_and_errors(tmp_path) -> None:
    database = tmp_path / "execute-api.db"
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    case = evaluations.create_case(case_input(terminal_status="completed"))
    adapter = ScriptedExecutionAdapter(ModelResponse(content="done"))
    sessions = execution_manager(database, [adapter])
    app = create_app(
        trace_repository=traces,
        evaluation_repository=evaluations,
        chat_session_manager=sessions,
    )

    with TestClient(app) as client:
        response = client.post(
            f"/evaluations/cases/{case.id}/execute",
            json={"prompt": "ignored", "api_key": "ignored", "base_url": "ignored"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["result"]["case_id"] == case.id
        assert body["run_id"] == body["result"]["run_id"]
        assert "api_key" not in body
        assert "base_url" not in body
        assert client.post("/evaluations/cases/missing/execute").status_code == 404

    unavailable = create_default_chat_manager(
        tools=ToolRegistry(), traces=traces, environ={}
    )
    with TestClient(
        create_app(
            trace_repository=traces,
            evaluation_repository=evaluations,
            chat_session_manager=unavailable,
        )
    ) as client:
        assert client.post(f"/evaluations/cases/{case.id}/execute").status_code == 503


async def test_eval_run_helper_and_cli_json_output(
    tmp_path, monkeypatch, capsys
) -> None:
    database = tmp_path / "eval-run-cli.db"
    evaluations = SQLiteEvaluationRepository(database)
    case = evaluations.create_case(case_input(terminal_status="completed"))
    sessions = execution_manager(
        database, [ScriptedExecutionAdapter(ModelResponse(content="done"))]
    )
    execution = await run_configured_evaluation(
        case.id, database, chat_manager=sessions
    )
    assert execution.result.passed is True

    async def fake_run(case_id, path):
        assert case_id == case.id
        assert path == database
        return execution

    monkeypatch.setattr(
        "scholar_harness.cli.run_configured_evaluation", fake_run
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scholar-harness",
            "eval-run",
            "--case",
            case.id,
            "--database",
            str(database),
        ],
    )
    await asyncio.to_thread(main)
    output = json.loads(capsys.readouterr().out)
    assert output["run_id"] == execution.run_id
    assert output["result"]["passed"] is True

    with pytest.raises(ChatConfigurationError, match="OPENAI_MODEL"):
        await run_configured_evaluation(case.id, database, environ={})

    async def missing_config(case_id, path):
        raise ChatConfigurationError("OPENAI_MODEL is required")

    monkeypatch.setattr(
        "scholar_harness.cli.run_configured_evaluation", missing_config
    )
    with pytest.raises(SystemExit) as caught:
        await asyncio.to_thread(main)
    assert caught.value.code == 2
