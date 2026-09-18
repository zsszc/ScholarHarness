from __future__ import annotations

import json
import sys
from tempfile import TemporaryDirectory

import pytest

import scholar_harness.benchmark as benchmark_module
from scholar_harness.benchmark import BenchmarkReport, run_benchmark
from scholar_harness.cli import main


def test_offline_benchmark_is_correct_and_cleans_temporary_database(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        benchmark_module,
        "TemporaryDirectory",
        lambda **kwargs: TemporaryDirectory(dir=tmp_path, **kwargs),
    )

    report = run_benchmark(
        papers=3,
        passages_per_paper=2,
        queries=2,
        trace_events=4,
    )

    assert report.schema_version == 1
    assert report.database_mode == "temporary"
    assert report.workload.model_dump() == {
        "papers": 3,
        "passages_per_paper": 2,
        "queries": 2,
        "trace_events": 4,
    }
    assert all(report.checks.model_dump().values())
    assert report.ingestion.operations == 3
    assert report.hybrid_retrieval.operations == 2
    assert report.trace_persistence.operations == 4
    assert report.ingestion.operations_per_second > 0
    assert list(tmp_path.iterdir()) == []


def test_benchmark_cli_writes_matching_atomic_json(tmp_path, monkeypatch, capsys) -> None:
    output = tmp_path / "reports" / "benchmark.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scholar-harness",
            "benchmark",
            "--papers",
            "2",
            "--passages-per-paper",
            "2",
            "--queries",
            "2",
            "--trace-events",
            "3",
            "--json-output",
            str(output),
        ],
    )

    main()

    stdout = json.loads(capsys.readouterr().out)
    stored = json.loads(output.read_text())
    assert stdout == stored
    assert all(stdout["checks"].values())
    assert not list(output.parent.glob("*.tmp"))


def test_benchmark_cli_rejects_non_positive_workloads(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["scholar-harness", "benchmark", "--queries", "0"],
    )

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "value must be at least 1" in capsys.readouterr().err


def test_checked_in_portfolio_evidence_is_consistent() -> None:
    report = BenchmarkReport.model_validate_json(
        open("docs/benchmark.json", encoding="utf-8").read()
    )
    benchmark = open("docs/benchmark.md", encoding="utf-8").read()
    portfolio = open("docs/portfolio.md", encoding="utf-8").read()

    assert report.environment.git_commit == "3f2b576"
    assert all(report.checks.model_dump().values())
    assert f"{report.ingestion.operations_per_second:,.2f}" in benchmark
    assert f"{report.hybrid_retrieval.operations_per_second:,.2f}" in benchmark
    assert f"{report.trace_persistence.operations_per_second:,.2f}" in benchmark
    for evidence in (
        "三分钟验证路径",
        "面试讲解主线",
        "证据地图",
        "简历表述",
        "已知限制与下一步",
    ):
        assert evidence in portfolio
