from __future__ import annotations

import json
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from scholar_harness.api import create_app
from scholar_harness.cli import main
from scholar_harness.core.events import AgentEvent
from scholar_harness.evaluations.models import (
    EvaluationCaseInput,
    EvaluationExpectations,
)
from scholar_harness.evaluations.repository import SQLiteEvaluationRepository
from scholar_harness.evaluations.service import EvaluationConflictError, TraceEvaluator
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


def test_expectation_validation_rejects_empty_and_contradictory_cases() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        EvaluationExpectations()
    with pytest.raises(ValidationError, match="both required and forbidden"):
        EvaluationExpectations(required_tools=["search"], forbidden_tools=["search"])
    with pytest.raises(ValidationError, match="cannot be empty"):
        EvaluationExpectations(answer_contains=["  "])


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
        required_tools=["search_papers"], terminal_status="completed"
    ).model_dump(mode="json")

    with TestClient(app) as client:
        created = client.post("/evaluations/cases", json=payload)
        assert created.status_code == 201
        case_id = created.json()["id"]
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
