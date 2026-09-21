from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from pydantic import ValidationError

import scholar_harness.retrieval_evaluation as evaluation_module
from scholar_harness.cli import main
from scholar_harness.retrieval_evaluation import (
    RetrievalEvaluationDataset,
    RetrievalEvaluationReport,
    load_retrieval_dataset,
    ranking_metrics,
    run_retrieval_evaluation,
)

DATASET_PATH = "benchmarks/retrieval-ablation-v1.json"


def test_ranking_metrics_cover_hits_misses_and_multiple_relevant_items() -> None:
    relevant = {("paper-a", "p1"), ("paper-b", "p1")}
    metrics = ranking_metrics(
        [("noise", "p1"), ("paper-b", "p1"), ("paper-a", "p1")],
        relevant,
        k=2,
    )

    assert metrics.recall_at_k == 0.5
    assert metrics.reciprocal_rank_at_k == 0.5
    assert metrics.ndcg_at_k == pytest.approx(0.386853, abs=1e-6)
    missed = ranking_metrics([("noise", "p1")], relevant, k=1)
    assert missed.model_dump() == {
        "recall_at_k": 0.0,
        "reciprocal_rank_at_k": 0.0,
        "ndcg_at_k": 0.0,
    }


def test_dataset_rejects_dangling_relevance_coordinate() -> None:
    dataset = load_retrieval_dataset(Path(DATASET_PATH))
    invalid = dataset.model_dump()
    invalid["cases"][0]["relevant"] = [
        {"paper_id": "missing", "passage_id": "missing"}
    ]

    with pytest.raises(ValidationError, match="references unknown passages"):
        RetrievalEvaluationDataset.model_validate(invalid)


def test_evaluation_runs_three_modes_and_cleans_temporary_database(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        evaluation_module,
        "TemporaryDirectory",
        lambda **kwargs: TemporaryDirectory(dir=tmp_path, **kwargs),
    )
    dataset = load_retrieval_dataset(Path(DATASET_PATH))

    report = run_retrieval_evaluation(dataset, k=5)

    assert report.schema_version == 1
    assert report.dataset_sha256 == dataset.sha256()
    assert report.query_count == 20
    assert report.passage_count == 15
    assert set(report.modes) == {"lexical", "vector", "hybrid"}
    assert all(len(mode.cases) == 20 for mode in report.modes.values())
    assert report.modes["hybrid"].recall_at_k >= report.modes["lexical"].recall_at_k
    assert list(tmp_path.iterdir()) == []


def test_retrieval_eval_cli_writes_matching_atomic_json(
    tmp_path, monkeypatch, capsys
) -> None:
    output = tmp_path / "reports" / "retrieval.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scholar-harness",
            "retrieval-eval",
            "--dataset",
            DATASET_PATH,
            "--k",
            "5",
            "--json-output",
            str(output),
        ],
    )

    main()

    stdout = json.loads(capsys.readouterr().out)
    stored = json.loads(output.read_text())
    assert stdout == stored
    assert RetrievalEvaluationReport.model_validate(stored).query_count == 20
    assert not list(output.parent.glob("*.tmp"))


def test_retrieval_eval_cli_rejects_non_positive_k(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["scholar-harness", "retrieval-eval", "--dataset", DATASET_PATH, "--k", "0"],
    )

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "value must be at least 1" in capsys.readouterr().err


def test_checked_in_retrieval_evidence_is_consistent() -> None:
    dataset = load_retrieval_dataset(Path(DATASET_PATH))
    report = RetrievalEvaluationReport.model_validate_json(
        open("docs/retrieval-evaluation.json", encoding="utf-8").read()
    )
    narrative = open("docs/retrieval-evaluation.md", encoding="utf-8").read()

    assert report.dataset_sha256 == dataset.sha256()
    assert report.query_count == len(dataset.cases)
    assert "controlled offline" in report.dataset_description.lower()
    assert "受控离线" in narrative
    assert "不是公开学术检索基准" in narrative
    for mode in report.modes.values():
        assert f"{mode.recall_at_k:.1%}" in narrative
        assert f"{mode.mrr_at_k:.1%}" in narrative
        assert f"{mode.ndcg_at_k:.1%}" in narrative
