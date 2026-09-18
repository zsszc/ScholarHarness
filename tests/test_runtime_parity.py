from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta

import pytest

from scholar_harness.cli import main
from scholar_harness.core.events import AgentEvent
from scholar_harness.traces.parity import RuntimeParityService
from scholar_harness.traces.repository import SQLiteTraceRepository


def add_run(
    repository: SQLiteTraceRepository,
    runtime_type: str,
    *,
    text_field: str,
    text: str,
    tool_name: str = "search_papers",
    text_chunks: list[str] | None = None,
) -> str:
    run = repository.create_run(runtime_type)
    base = datetime(2026, 9, 18, tzinfo=UTC)
    payloads = [
        ("agent_start", {"type": "agent_start", "provider": runtime_type}),
        ("context_injection", {"type": "context_injection", "status": "selected"}),
        *[
            ("message_update", {"type": "message_update", text_field: chunk})
            for chunk in (text_chunks or [text[:3], text[3:]])
        ],
        (
            "tool_execution_start",
            {
                "type": "tool_execution_start",
                "toolCallId": f"{runtime_type}-call",
                "toolName": tool_name,
                "args": {"volatile": runtime_type},
            },
        ),
        (
            "tool_execution_end",
            {
                "type": "tool_execution_end",
                "toolCallId": f"{runtime_type}-call",
                "toolName": tool_name,
                "result": {"provider": runtime_type},
                "isError": False,
            },
        ),
        ("agent_end", {"type": "agent_end", "status": "completed"}),
        ("agent_settled", {"type": "agent_settled", "status": "completed"}),
    ]
    parent_id = None
    for index, (event_type, payload) in enumerate(payloads):
        entry_id = f"{runtime_type}-entry-{index}"
        repository.append_event(
            run.id,
            AgentEvent(
                type=event_type,
                session_id=f"{runtime_type}-session",
                entry_id=entry_id,
                parent_id=parent_id,
                timestamp=base + timedelta(seconds=index),
                data=payload,
            ),
        )
        parent_id = entry_id
    repository.finish_run(run.id, "completed")
    return run.id


def test_pi_and_minipy_shapes_project_to_semantic_parity(tmp_path) -> None:
    repository = SQLiteTraceRepository(tmp_path / "parity.db")
    pi_run = add_run(
        repository, "pi", text_field="text", text="Pi response"
    )
    mini_run = add_run(
        repository,
        "mini-py",
        text_field="delta",
        text="Mini response",
        text_chunks=["Mini response"],
    )
    service = RuntimeParityService(repository)

    pi_snapshot = service.snapshot(pi_run)
    report = service.compare(pi_run, mini_run)
    strict = service.compare(pi_run, mini_run, strict_output=True)

    assert pi_snapshot.assistant_text == "Pi response"
    assert pi_snapshot.tools[0].model_dump() == {
        "tool_name": "search_papers",
        "is_error": False,
    }
    assert report.passed is True
    assert [check.name for check in report.checks] == [
        "terminal_status",
        "lifecycle",
        "tool_outcomes",
        "context_statuses",
        "assistant_output_present",
    ]
    assert "Pi response" not in report.model_dump_json()
    assert strict.passed is False
    assert strict.checks[-1].name == "assistant_output_exact"
    assert strict.checks[-1].left == "Pi response"


def test_parity_report_explains_tool_mismatch(tmp_path) -> None:
    repository = SQLiteTraceRepository(tmp_path / "mismatch.db")
    left = add_run(repository, "pi", text_field="text", text="same")
    right = add_run(
        repository,
        "mini-py",
        text_field="delta",
        text="same",
        tool_name="read_passage",
    )

    report = RuntimeParityService(repository).compare(left, right)
    tool_check = next(check for check in report.checks if check.name == "tool_outcomes")

    assert report.schema_version == 1
    assert report.passed is False
    assert tool_check.passed is False
    assert tool_check.left[0]["tool_name"] == "search_papers"
    assert tool_check.right[0]["tool_name"] == "read_passage"


def test_parity_cli_json_exit_codes_and_unknown_runs(
    tmp_path, monkeypatch, capsys
) -> None:
    database = tmp_path / "cli-parity.db"
    repository = SQLiteTraceRepository(database)
    left = add_run(repository, "pi", text_field="text", text="left")
    right = add_run(repository, "mini-py", text_field="delta", text="right")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scholar-harness",
            "parity",
            "--left-run",
            left,
            "--right-run",
            right,
            "--database",
            str(database),
        ],
    )
    main()
    output = json.loads(capsys.readouterr().out)
    assert output["passed"] is True
    assert output["schema_version"] == 1

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scholar-harness",
            "parity",
            "--left-run",
            left,
            "--right-run",
            right,
            "--database",
            str(database),
            "--strict-output",
        ],
    )
    with pytest.raises(SystemExit, match="1"):
        main()
    strict = json.loads(capsys.readouterr().out)
    assert strict["passed"] is False

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scholar-harness",
            "parity",
            "--left-run",
            "missing",
            "--right-run",
            right,
            "--database",
            str(database),
        ],
    )
    with pytest.raises(SystemExit, match="2"):
        main()
    assert "Unknown run: missing" in capsys.readouterr().err
