from __future__ import annotations

import platform
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, Field

from scholar_harness.core.events import AgentEvent
from scholar_harness.papers.models import Paper, Passage
from scholar_harness.papers.repository import SQLitePaperRepository
from scholar_harness.traces.repository import SQLiteTraceRepository


class BenchmarkWorkload(BaseModel):
    papers: int = Field(ge=1)
    passages_per_paper: int = Field(ge=1)
    queries: int = Field(ge=1)
    trace_events: int = Field(ge=1)


class BenchmarkMetric(BaseModel):
    operations: int
    elapsed_seconds: float
    operations_per_second: float


class BenchmarkEnvironment(BaseModel):
    python: str
    sqlite: str
    platform: str
    git_commit: str | None = None


class BenchmarkChecks(BaseModel):
    retrieval_coordinates_valid: bool
    retrieval_result_count_valid: bool
    trace_event_count_valid: bool
    run_completed: bool


class BenchmarkReport(BaseModel):
    schema_version: Literal[1] = 1
    database_mode: Literal["temporary", "provided"]
    workload: BenchmarkWorkload
    environment: BenchmarkEnvironment
    ingestion: BenchmarkMetric
    hybrid_retrieval: BenchmarkMetric
    trace_persistence: BenchmarkMetric
    checks: BenchmarkChecks


def run_benchmark(
    *,
    papers: int = 100,
    passages_per_paper: int = 4,
    queries: int = 100,
    trace_events: int = 1_000,
    database: Path | None = None,
) -> BenchmarkReport:
    workload = BenchmarkWorkload(
        papers=papers,
        passages_per_paper=passages_per_paper,
        queries=queries,
        trace_events=trace_events,
    )
    if database is not None:
        return _run_on_database(database, workload, database_mode="provided")
    with TemporaryDirectory(prefix="scholar-harness-benchmark-") as directory:
        return _run_on_database(
            Path(directory) / "benchmark.db",
            workload,
            database_mode="temporary",
        )


def _run_on_database(
    database: Path,
    workload: BenchmarkWorkload,
    *,
    database_mode: Literal["temporary", "provided"],
) -> BenchmarkReport:
    prefix = f"benchmark-{uuid.uuid4()}"
    papers = SQLitePaperRepository(database)
    traces = SQLiteTraceRepository(database)

    started = perf_counter()
    for paper_index in range(workload.papers):
        paper_id = f"{prefix}-paper-{paper_index}"
        papers.add(
            Paper(
                id=paper_id,
                title=f"Agent Memory Study {paper_index}",
                passages=[
                    Passage(
                        id=f"passage-{passage_index}",
                        page=passage_index + 1,
                        text=(
                            "Agent memory requires evidence provenance and "
                            f"deterministic retrieval coordinate {paper_index} "
                            f"{passage_index}."
                        ),
                    )
                    for passage_index in range(workload.passages_per_paper)
                ],
            )
        )
    ingestion = _metric(workload.papers, perf_counter() - started)

    started = perf_counter()
    last_results: list[dict[str, object]] = []
    for _ in range(workload.queries):
        last_results = [
            dict(item)
            for item in papers.search(
                "agent memory evidence provenance", limit=5, mode="hybrid"
            )
        ]
    retrieval = _metric(workload.queries, perf_counter() - started)

    run = traces.create_run("portfolio-benchmark")
    started = perf_counter()
    for event_index in range(workload.trace_events):
        traces.append_event(
            run.id,
            AgentEvent(
                type="benchmark_event",
                session_id=prefix,
                entry_id=f"{prefix}-entry-{event_index}",
                data={"index": event_index, "kind": "benchmark"},
            ),
        )
    trace_persistence = _metric(workload.trace_events, perf_counter() - started)
    completed = traces.finish_run(run.id, "completed")
    stored_events = traces.list_events(run.id)

    expected_results = min(5, workload.papers * workload.passages_per_paper)
    checks = BenchmarkChecks(
        retrieval_coordinates_valid=bool(last_results)
        and all(
            str(item.get("paper_id", "")).startswith(prefix)
            and str(item.get("passage_id", "")).startswith("passage-")
            for item in last_results
        ),
        retrieval_result_count_valid=len(last_results) == expected_results,
        trace_event_count_valid=len(stored_events) == workload.trace_events,
        run_completed=completed.status == "completed",
    )
    return BenchmarkReport(
        database_mode=database_mode,
        workload=workload,
        environment=BenchmarkEnvironment(
            python=sys.version.split()[0],
            sqlite=sqlite3.sqlite_version,
            platform=platform.platform(),
            git_commit=_git_commit(),
        ),
        ingestion=ingestion,
        hybrid_retrieval=retrieval,
        trace_persistence=trace_persistence,
        checks=checks,
    )


def _metric(operations: int, elapsed: float) -> BenchmarkMetric:
    elapsed = max(elapsed, 1e-9)
    return BenchmarkMetric(
        operations=operations,
        elapsed_seconds=round(elapsed, 6),
        operations_per_second=round(operations / elapsed, 2),
    )


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None
