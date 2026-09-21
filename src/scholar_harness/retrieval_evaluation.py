from __future__ import annotations

import hashlib
import json
import math
import platform
import sqlite3
import sys
from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter_ns
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from scholar_harness.benchmark import BenchmarkEnvironment
from scholar_harness.papers.models import Paper
from scholar_harness.papers.repository import SQLitePaperRepository


class PassageCoordinate(BaseModel):
    paper_id: str = Field(min_length=1)
    passage_id: str = Field(min_length=1)

    def key(self) -> tuple[str, str]:
        return self.paper_id, self.passage_id


class RetrievalEvaluationCase(BaseModel):
    id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    relevant: list[PassageCoordinate] = Field(min_length=1)
    category: str = Field(min_length=1)


class RetrievalEvaluationDataset(BaseModel):
    schema_version: Literal[1] = 1
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    papers: list[Paper] = Field(min_length=1)
    cases: list[RetrievalEvaluationCase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identity_and_relevance(self) -> RetrievalEvaluationDataset:
        paper_ids = [paper.id for paper in self.papers]
        if len(paper_ids) != len(set(paper_ids)):
            raise ValueError("Dataset paper ids must be unique")
        case_ids = [case.id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Dataset case ids must be unique")

        coordinates: set[tuple[str, str]] = set()
        for paper in self.papers:
            passage_ids = [passage.id for passage in paper.passages]
            if len(passage_ids) != len(set(passage_ids)):
                raise ValueError(f"Passage ids must be unique within paper {paper.id}")
            coordinates.update((paper.id, passage_id) for passage_id in passage_ids)
        for case in self.cases:
            relevant = [coordinate.key() for coordinate in case.relevant]
            if len(relevant) != len(set(relevant)):
                raise ValueError(f"Case {case.id} contains duplicate relevance coordinates")
            dangling = sorted(set(relevant) - coordinates)
            if dangling:
                raise ValueError(f"Case {case.id} references unknown passages: {dangling}")
        return self

    def sha256(self) -> str:
        canonical = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


class RankingMetrics(BaseModel):
    recall_at_k: float
    reciprocal_rank_at_k: float
    ndcg_at_k: float


class RankedCoordinate(PassageCoordinate):
    rank: int = Field(ge=1)


class RetrievalCaseResult(BaseModel):
    case_id: str
    query: str
    category: str
    relevant: list[PassageCoordinate]
    ranked: list[RankedCoordinate]
    metrics: RankingMetrics
    latency_ms: float


class RetrievalModeResult(BaseModel):
    mode: Literal["lexical", "vector", "hybrid"]
    recall_at_k: float
    mrr_at_k: float
    ndcg_at_k: float
    latency_ms_p50: float
    latency_ms_p95: float
    categories: dict[str, RetrievalCategoryResult]
    cases: list[RetrievalCaseResult]


class RetrievalCategoryResult(BaseModel):
    case_count: int
    recall_at_k: float
    mrr_at_k: float
    ndcg_at_k: float


class QualityDelta(BaseModel):
    recall_at_k: float
    mrr_at_k: float
    ndcg_at_k: float


class RetrievalEvaluationReport(BaseModel):
    schema_version: Literal[1] = 1
    dataset_name: str
    dataset_sha256: str
    dataset_description: str
    cutoff_k: int
    query_count: int
    passage_count: int
    environment: BenchmarkEnvironment
    modes: dict[Literal["lexical", "vector", "hybrid"], RetrievalModeResult]
    hybrid_delta_vs_lexical: QualityDelta
    hybrid_delta_vs_vector: QualityDelta


def load_retrieval_dataset(path: Path) -> RetrievalEvaluationDataset:
    return RetrievalEvaluationDataset.model_validate_json(path.read_text(encoding="utf-8"))


def ranking_metrics(
    ranked: list[tuple[str, str]],
    relevant: set[tuple[str, str]],
    *,
    k: int,
) -> RankingMetrics:
    if k < 1:
        raise ValueError("k must be at least 1")
    if not relevant:
        raise ValueError("relevant coordinates must not be empty")
    top = ranked[:k]
    matched = sum(coordinate in relevant for coordinate in top)
    recall = matched / len(relevant)
    reciprocal_rank = next(
        (1.0 / rank for rank, coordinate in enumerate(top, start=1) if coordinate in relevant),
        0.0,
    )
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, coordinate in enumerate(top, start=1)
        if coordinate in relevant
    )
    ideal_hits = min(len(relevant), k)
    ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return RankingMetrics(
        recall_at_k=round(recall, 6),
        reciprocal_rank_at_k=round(reciprocal_rank, 6),
        ndcg_at_k=round(dcg / ideal_dcg, 6),
    )


def run_retrieval_evaluation(
    dataset: RetrievalEvaluationDataset,
    *,
    k: int = 5,
) -> RetrievalEvaluationReport:
    if k < 1:
        raise ValueError("k must be at least 1")
    with TemporaryDirectory(prefix="scholar-harness-retrieval-eval-") as directory:
        repository = SQLitePaperRepository(Path(directory) / "evaluation.db")
        for paper in dataset.papers:
            repository.add(paper)
        modes = {
            mode: _evaluate_mode(repository, dataset, mode=mode, k=k)
            for mode in ("lexical", "vector", "hybrid")
        }

    lexical = modes["lexical"]
    vector = modes["vector"]
    hybrid = modes["hybrid"]
    return RetrievalEvaluationReport(
        dataset_name=dataset.name,
        dataset_sha256=dataset.sha256(),
        dataset_description=dataset.description,
        cutoff_k=k,
        query_count=len(dataset.cases),
        passage_count=sum(len(paper.passages) for paper in dataset.papers),
        environment=BenchmarkEnvironment(
            python=sys.version.split()[0],
            sqlite=sqlite3.sqlite_version,
            platform=platform.platform(),
            git_commit=_git_commit(),
        ),
        modes=modes,
        hybrid_delta_vs_lexical=_delta(hybrid, lexical),
        hybrid_delta_vs_vector=_delta(hybrid, vector),
    )


def _evaluate_mode(
    repository: SQLitePaperRepository,
    dataset: RetrievalEvaluationDataset,
    *,
    mode: Literal["lexical", "vector", "hybrid"],
    k: int,
) -> RetrievalModeResult:
    case_results: list[RetrievalCaseResult] = []
    for case in dataset.cases:
        started = perf_counter_ns()
        if mode == "hybrid":
            hits = repository.search(case.query, limit=k, mode="hybrid")
        else:
            hits = repository.component_search(case.query, limit=k, component=mode)
        latency_ms = (perf_counter_ns() - started) / 1_000_000
        ranked_keys = [
            (str(hit["paper_id"]), str(hit["passage_id"])) for hit in hits
        ]
        relevant = {coordinate.key() for coordinate in case.relevant}
        case_results.append(
            RetrievalCaseResult(
                case_id=case.id,
                query=case.query,
                category=case.category,
                relevant=case.relevant,
                ranked=[
                    RankedCoordinate(paper_id=paper_id, passage_id=passage_id, rank=rank)
                    for rank, (paper_id, passage_id) in enumerate(ranked_keys, start=1)
                ],
                metrics=ranking_metrics(ranked_keys, relevant, k=k),
                latency_ms=round(latency_ms, 6),
            )
        )

    latencies = sorted(result.latency_ms for result in case_results)
    categories: dict[str, RetrievalCategoryResult] = {}
    for category in sorted({result.category for result in case_results}):
        selected = [result for result in case_results if result.category == category]
        categories[category] = RetrievalCategoryResult(
            case_count=len(selected),
            recall_at_k=_mean(result.metrics.recall_at_k for result in selected),
            mrr_at_k=_mean(result.metrics.reciprocal_rank_at_k for result in selected),
            ndcg_at_k=_mean(result.metrics.ndcg_at_k for result in selected),
        )
    return RetrievalModeResult(
        mode=mode,
        recall_at_k=_mean(result.metrics.recall_at_k for result in case_results),
        mrr_at_k=_mean(result.metrics.reciprocal_rank_at_k for result in case_results),
        ndcg_at_k=_mean(result.metrics.ndcg_at_k for result in case_results),
        latency_ms_p50=_nearest_rank(latencies, 0.50),
        latency_ms_p95=_nearest_rank(latencies, 0.95),
        categories=categories,
        cases=case_results,
    )


def _mean(values: Iterable[float]) -> float:
    materialized = list(values)
    return round(sum(materialized) / len(materialized), 6)


def _nearest_rank(values: list[float], quantile: float) -> float:
    index = max(0, math.ceil(quantile * len(values)) - 1)
    return round(values[index], 6)


def _delta(left: RetrievalModeResult, right: RetrievalModeResult) -> QualityDelta:
    return QualityDelta(
        recall_at_k=round(left.recall_at_k - right.recall_at_k, 6),
        mrr_at_k=round(left.mrr_at_k - right.mrr_at_k, 6),
        ndcg_at_k=round(left.ndcg_at_k - right.ndcg_at_k, 6),
    )


def _git_commit() -> str | None:
    from scholar_harness.benchmark import _git_commit as benchmark_git_commit

    return benchmark_git_commit()
