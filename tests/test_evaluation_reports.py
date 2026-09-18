from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree

import pytest

from scholar_harness.chat_sessions import ChatConfigurationError
from scholar_harness.cli import main
from scholar_harness.evaluations.models import (
    EvaluationExpectations,
    EvaluationSuiteItem,
    EvaluationSuiteRun,
)
from scholar_harness.evaluations.reports import (
    suite_run_json,
    suite_run_junit,
    write_text_atomic,
)


def suite_run(*, passed: bool) -> EvaluationSuiteRun:
    started = datetime(2026, 9, 18, 3, 0, tzinfo=UTC)
    items = [
        EvaluationSuiteItem(
            position=0,
            case_id="case-pass",
            case_name="Pass <case>",
            case_prompt="answer safely",
            expectations=EvaluationExpectations(terminal_status="completed"),
            pass_threshold=1.0,
            result_id="result-pass",
            run_id="trace-pass",
            event_count=4,
            score=1.0,
            passed=True,
        )
    ]
    if not passed:
        items.extend(
            [
                EvaluationSuiteItem(
                    position=1,
                    case_id="case-fail",
                    case_name='Fail "case"',
                    case_prompt="miss expected answer",
                    expectations=EvaluationExpectations(answer_contains=["evidence"]),
                    pass_threshold=1.0,
                    result_id="result-fail",
                    run_id="trace-fail",
                    event_count=4,
                    score=0.5,
                    passed=False,
                ),
                EvaluationSuiteItem(
                    position=2,
                    case_id="case-error",
                    case_name="Error & case",
                    case_prompt="provider unavailable",
                    expectations=EvaluationExpectations(terminal_status="completed"),
                    pass_threshold=1.0,
                    error="configuration_error",
                ),
            ]
        )
    return EvaluationSuiteRun(
        id="suite-run-1",
        suite_id="suite-1",
        suite_name="Gate <main> & checks",
        case_ids=[item.case_id for item in items],
        items=items,
        total_count=len(items),
        passed_count=1,
        failed_count=0 if passed else 1,
        error_count=0 if passed else 1,
        passed=passed,
        started_at=started,
        ended_at=started + timedelta(seconds=1.25),
    )


def test_json_report_parity_and_atomic_replacement(tmp_path) -> None:
    run = suite_run(passed=True)
    target = tmp_path / "nested" / "gate.json"
    target.parent.mkdir()
    target.write_text("old partial content", encoding="utf-8")

    payload = suite_run_json(run)
    write_text_atomic(target, payload)

    assert target.read_text(encoding="utf-8") == payload
    assert json.loads(payload)["id"] == run.id
    assert not list(target.parent.glob(".gate.json.*.tmp"))


def test_atomic_writer_preserves_target_and_cleans_temp_on_failure(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "gate.json"
    target.write_text("previous", encoding="utf-8")

    def fail_replace(source, destination):
        raise OSError("replace unavailable")

    monkeypatch.setattr("scholar_harness.evaluations.reports.os.replace", fail_replace)
    with pytest.raises(OSError, match="replace unavailable"):
        write_text_atomic(target, "next")

    assert target.read_text(encoding="utf-8") == "previous"
    assert not list(tmp_path.glob(".gate.json.*.tmp"))


def test_junit_report_maps_order_failures_errors_and_escapes_xml() -> None:
    run = suite_run(passed=False)
    payload = suite_run_junit(run)
    root = ElementTree.fromstring(payload)
    suite = root.find("testsuite")
    assert suite is not None
    assert suite.attrib == {
        "name": run.suite_name,
        "tests": "3",
        "failures": "1",
        "errors": "1",
        "time": "1.250000",
        "timestamp": run.started_at.isoformat(),
    }
    cases = suite.findall("testcase")
    assert [case.attrib["name"] for case in cases] == [
        "Pass <case>",
        'Fail "case"',
        "Error & case",
    ]
    assert cases[0].find("failure") is None
    assert cases[0].find("error") is None
    assert cases[1].find("failure").attrib["type"] == "evaluation_failure"
    assert cases[2].find("error").attrib["type"] == "configuration_error"
    assert "&lt;main&gt;" in payload
    assert "Error &amp; case" in payload


def test_eval_gate_cli_exit_codes_and_artifacts(tmp_path, monkeypatch, capsys) -> None:
    database = tmp_path / "gate.db"
    json_path = tmp_path / "artifacts" / "gate.json"
    junit_path = tmp_path / "artifacts" / "gate.xml"
    current = suite_run(passed=True)

    async def fake_run(suite_id, path):
        assert suite_id == "suite-1"
        assert path == database
        return current

    monkeypatch.setattr(
        "scholar_harness.cli.run_configured_evaluation_suite", fake_run
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scholar-harness",
            "eval-gate",
            "--suite",
            "suite-1",
            "--database",
            str(database),
            "--json-output",
            str(json_path),
            "--junit-output",
            str(junit_path),
        ],
    )

    main()
    stdout = capsys.readouterr().out
    assert json.loads(stdout)["passed"] is True
    assert json_path.read_text(encoding="utf-8") == stdout
    assert ElementTree.parse(junit_path).getroot().tag == "testsuites"

    current = suite_run(passed=False)
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 1
    stdout = capsys.readouterr().out
    assert json.loads(stdout)["passed"] is False


def test_eval_gate_configuration_failure_is_exit_two_without_artifacts(
    tmp_path, monkeypatch, capsys
) -> None:
    json_path = tmp_path / "gate.json"
    junit_path = tmp_path / "gate.xml"

    async def missing_config(suite_id, path):
        raise ChatConfigurationError("OPENAI_MODEL is required")

    monkeypatch.setattr(
        "scholar_harness.cli.run_configured_evaluation_suite", missing_config
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scholar-harness",
            "eval-gate",
            "--suite",
            "suite-1",
            "--database",
            str(tmp_path / "gate.db"),
            "--json-output",
            str(json_path),
            "--junit-output",
            str(junit_path),
        ],
    )

    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "OPENAI_MODEL" in captured.err
    assert not json_path.exists()
    assert not junit_path.exists()

    async def missing_suite(suite_id, path):
        raise KeyError("Unknown evaluation suite: suite-1")

    monkeypatch.setattr(
        "scholar_harness.cli.run_configured_evaluation_suite", missing_suite
    )
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2
    assert "Unknown evaluation suite" in capsys.readouterr().err


def test_ci_documentation_preserves_artifacts_then_enforces_gate() -> None:
    documentation = (Path(__file__).parents[1] / "docs" / "ci.md").read_text(
        encoding="utf-8"
    )
    assert "eval-gate" in documentation
    assert "continue-on-error: true" in documentation
    assert "if: always()" in documentation
    assert "steps.gate.outcome == 'failure'" in documentation
    assert "--json-output" in documentation
    assert "--junit-output" in documentation
