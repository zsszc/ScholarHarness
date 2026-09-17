from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from scholar_harness.api import create_app
from scholar_harness.chat_sessions import ChatConfigurationError, ChatSessionManager
from scholar_harness.cli import main, run_configured_evaluation_suite
from scholar_harness.evaluations.models import (
    EvaluationCaseInput,
    EvaluationExpectations,
    EvaluationSuiteInput,
)
from scholar_harness.evaluations.repository import SQLiteEvaluationRepository
from scholar_harness.evaluations.runner import EvaluationRunner
from scholar_harness.evaluations.service import TraceEvaluator
from scholar_harness.evaluations.suites import EvaluationSuiteRunner
from scholar_harness.runtimes.model import (
    ModelMessage,
    ModelResponse,
    ModelToolDefinition,
)
from scholar_harness.runtimes.openai_compatible import ModelAdapterError
from scholar_harness.tools.registry import ToolRegistry
from scholar_harness.traces.repository import SQLiteTraceRepository


class SuiteAdapter:
    def __init__(self, answer: str, *, fail: bool = False) -> None:
        self.answer = answer
        self.fail = fail
        self.closed = 0

    async def complete(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition],
    ) -> ModelResponse:
        if self.fail:
            raise ModelAdapterError("secret https://private.invalid/v1")
        return ModelResponse(content=self.answer)

    async def aclose(self) -> None:
        self.closed += 1


class BlockingSuiteAdapter(SuiteAdapter):
    def __init__(self) -> None:
        super().__init__("")
        self.entered = asyncio.Event()
        self.cancelled = False

    async def complete(self, messages, tools) -> ModelResponse:
        self.entered.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


def make_case(repository, name: str, expected: str):
    return repository.create_case(
        EvaluationCaseInput(
            name=name,
            prompt=f"answer with {expected}",
            expectations=EvaluationExpectations(
                answer_contains=[expected], terminal_status="completed"
            ),
        )
    )


def suite_manager(database, adapters):
    pending = iter(adapters)
    return ChatSessionManager(
        tools=ToolRegistry(),
        traces=SQLiteTraceRepository(database),
        adapter_factory=lambda: next(pending),
    )


def test_suite_repository_validates_order_and_preserves_run_snapshots(tmp_path) -> None:
    repository = SQLiteEvaluationRepository(tmp_path / "suites.db")
    first = make_case(repository, "First", "one")
    second = make_case(repository, "Second", "two")

    suite = repository.create_suite(
        EvaluationSuiteInput(name=" Regression ", case_ids=[second.id, first.id])
    )
    assert suite.name == "Regression"
    assert suite.case_ids == [second.id, first.id]
    assert repository.list_suites() == [suite]

    updated = repository.update_suite(
        suite.id, EvaluationSuiteInput(name="Updated", case_ids=[first.id])
    )
    assert updated.case_ids == [first.id]
    with pytest.raises(KeyError, match="Unknown evaluation case"):
        repository.update_suite(
            suite.id, EvaluationSuiteInput(name="Bad", case_ids=["missing"])
        )
    assert repository.get_suite(suite.id) == updated
    with pytest.raises(ValidationError, match="unique"):
        EvaluationSuiteInput(name="Bad", case_ids=[first.id, first.id])


async def test_suite_runner_aggregates_order_and_immutable_snapshots(tmp_path) -> None:
    database = tmp_path / "run-suite.db"
    repository = SQLiteEvaluationRepository(database)
    traces = SQLiteTraceRepository(database)
    first = make_case(repository, "First", "one")
    second = make_case(repository, "Second", "two")
    suite = repository.create_suite(
        EvaluationSuiteInput(name="Regression", case_ids=[first.id, second.id])
    )
    adapters = [SuiteAdapter("one"), SuiteAdapter("not expected")]
    sessions = suite_manager(database, adapters)

    result = await EvaluationSuiteRunner(
        repository,
        EvaluationRunner(sessions, repository, TraceEvaluator(traces, repository)),
    ).execute(suite.id)

    assert result.case_ids == [first.id, second.id]
    assert [item.case_name for item in result.items] == ["First", "Second"]
    assert (result.passed_count, result.failed_count, result.error_count) == (1, 1, 0)
    assert result.passed is False
    assert all(item.run_id and item.result_id for item in result.items)
    assert [adapter.closed for adapter in adapters] == [1, 1]
    repository.update_suite(
        suite.id, EvaluationSuiteInput(name="Changed", case_ids=[second.id])
    )
    persisted = repository.get_suite_run(result.id)
    assert persisted.suite_name == "Regression"
    assert persisted.case_ids == [first.id, second.id]


async def test_suite_runner_continues_after_safe_execution_error(tmp_path) -> None:
    database = tmp_path / "suite-errors.db"
    repository = SQLiteEvaluationRepository(database)
    traces = SQLiteTraceRepository(database)
    first = make_case(repository, "First", "one")
    second = make_case(repository, "Second", "two")
    suite = repository.create_suite(
        EvaluationSuiteInput(name="Errors", case_ids=[first.id, second.id])
    )
    adapters = [SuiteAdapter("", fail=True), SuiteAdapter("two")]
    sessions = suite_manager(database, adapters)
    runner = EvaluationSuiteRunner(
        repository,
        EvaluationRunner(sessions, repository, TraceEvaluator(traces, repository)),
    )

    result = await runner.execute(suite.id)

    assert result.items[0].runtime_error == "model_error"
    assert result.items[0].error is None
    assert result.items[1].passed is True
    assert result.error_count == 0
    assert "private.invalid" not in result.model_dump_json()
    assert await sessions.list() == []


async def test_suite_runner_continues_after_orchestration_error(tmp_path) -> None:
    database = tmp_path / "suite-orchestration.db"
    repository = SQLiteEvaluationRepository(database)
    traces = SQLiteTraceRepository(database)
    first = make_case(repository, "First", "one")
    second = make_case(repository, "Second", "two")
    suite = repository.create_suite(
        EvaluationSuiteInput(name="Continue", case_ids=[first.id, second.id])
    )
    adapter = SuiteAdapter("two")
    factories = iter([RuntimeError("raw provider detail"), adapter])

    def factory():
        value = next(factories)
        if isinstance(value, Exception):
            raise value
        return value

    sessions = ChatSessionManager(
        tools=ToolRegistry(), traces=traces, adapter_factory=factory
    )
    result = await EvaluationSuiteRunner(
        repository,
        EvaluationRunner(sessions, repository, TraceEvaluator(traces, repository)),
    ).execute(suite.id)

    assert result.items[0].error == "execution_error"
    assert result.items[1].passed is True
    assert (result.failed_count, result.error_count) == (0, 1)
    assert "raw provider detail" not in result.model_dump_json()


async def test_suite_runner_cancellation_cleans_active_session(tmp_path) -> None:
    database = tmp_path / "suite-cancel.db"
    repository = SQLiteEvaluationRepository(database)
    traces = SQLiteTraceRepository(database)
    case = make_case(repository, "Blocking", "done")
    suite = repository.create_suite(
        EvaluationSuiteInput(name="Cancel", case_ids=[case.id])
    )
    adapter = BlockingSuiteAdapter()
    sessions = suite_manager(database, [adapter])
    task = asyncio.create_task(
        EvaluationSuiteRunner(
            repository,
            EvaluationRunner(
                sessions, repository, TraceEvaluator(traces, repository)
            ),
        ).execute(suite.id)
    )
    await adapter.entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert adapter.cancelled is True
    assert adapter.closed == 1
    assert await sessions.list() == []
    assert repository.list_suite_runs() == []


async def test_parallel_suite_runs_are_isolated(tmp_path) -> None:
    database = tmp_path / "suite-parallel.db"
    repository = SQLiteEvaluationRepository(database)
    traces = SQLiteTraceRepository(database)
    case = make_case(repository, "Parallel", "done")
    suite = repository.create_suite(
        EvaluationSuiteInput(name="Parallel", case_ids=[case.id])
    )
    adapters = [SuiteAdapter("done"), SuiteAdapter("done")]
    sessions = suite_manager(database, adapters)
    runner = EvaluationSuiteRunner(
        repository,
        EvaluationRunner(sessions, repository, TraceEvaluator(traces, repository)),
    )

    first, second = await asyncio.gather(
        runner.execute(suite.id), runner.execute(suite.id)
    )

    assert first.id != second.id
    assert first.items[0].run_id != second.items[0].run_id
    assert first.items[0].result_id != second.items[0].result_id
    session_ids = {
        traces.get_run(first.items[0].run_id).external_session_id,
        traces.get_run(second.items[0].run_id).external_session_id,
    }
    assert len(session_ids) == 2


def test_suite_api_definition_execution_and_history(tmp_path) -> None:
    database = tmp_path / "suite-api.db"
    repository = SQLiteEvaluationRepository(database)
    traces = SQLiteTraceRepository(database)
    case = make_case(repository, "API", "done")
    sessions = suite_manager(database, [SuiteAdapter("done")])
    with TestClient(
        create_app(
            trace_repository=traces,
            evaluation_repository=repository,
            chat_session_manager=sessions,
        )
    ) as client:
        created = client.post(
            "/evaluations/suites", json={"name": "API suite", "case_ids": [case.id]}
        )
        assert created.status_code == 201
        suite_id = created.json()["id"]
        assert client.get(f"/evaluations/suites/{suite_id}").status_code == 200
        executed = client.post(f"/evaluations/suites/{suite_id}/execute")
        assert executed.status_code == 201
        run = executed.json()
        assert run["passed"] is True
        assert client.get(f"/evaluations/suite-runs/{run['id']}").json() == run
        assert len(client.get("/evaluations/suite-runs").json()) == 1
        assert client.post("/evaluations/suites/missing/execute").status_code == 404
        unknown = client.post(
            "/evaluations/suites", json={"name": "Bad", "case_ids": ["missing"]}
        )
        assert unknown.status_code == 404

    unavailable = ChatSessionManager(
        tools=ToolRegistry(),
        traces=traces,
        adapter_factory=None,
        unavailable_reason="OPENAI_MODEL missing",
    )
    with TestClient(
        create_app(
            trace_repository=traces,
            evaluation_repository=repository,
            chat_session_manager=unavailable,
        )
    ) as client:
        response = client.post(f"/evaluations/suites/{suite_id}/execute")
        assert response.status_code == 201
        assert response.json()["items"][0]["error"] == "configuration_error"


async def test_suite_cli_helper_and_json_output(tmp_path, monkeypatch, capsys) -> None:
    database = tmp_path / "suite-cli.db"
    repository = SQLiteEvaluationRepository(database)
    case = make_case(repository, "CLI", "done")
    suite = repository.create_suite(
        EvaluationSuiteInput(name="CLI suite", case_ids=[case.id])
    )
    result = await run_configured_evaluation_suite(
        suite.id,
        database,
        chat_manager=suite_manager(database, [SuiteAdapter("done")]),
    )

    async def fake_run(suite_id, path):
        assert suite_id == suite.id
        assert path == database
        return result

    monkeypatch.setattr(
        "scholar_harness.cli.run_configured_evaluation_suite", fake_run
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scholar-harness",
            "eval-suite-run",
            "--suite",
            suite.id,
            "--database",
            str(database),
        ],
    )
    await asyncio.to_thread(main)
    output = json.loads(capsys.readouterr().out)
    assert output["id"] == result.id
    assert output["passed"] is True

    async def missing_config(suite_id, path):
        raise ChatConfigurationError("OPENAI_MODEL is required")

    monkeypatch.setattr(
        "scholar_harness.cli.run_configured_evaluation_suite", missing_config
    )
    with pytest.raises(SystemExit) as caught:
        await asyncio.to_thread(main)
    assert caught.value.code == 2
