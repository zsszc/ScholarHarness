from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from scholar_harness.evaluations.models import (
    EvaluationCase,
    EvaluationCaseInput,
    EvaluationCheck,
    EvaluationExpectations,
    EvaluationResult,
)


class SQLiteEvaluationRepository:
    def __init__(self, database: Path | str) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS evaluation_cases (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    expectations_json TEXT NOT NULL,
                    pass_threshold REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evaluation_results (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL REFERENCES evaluation_cases(id) ON DELETE CASCADE,
                    run_id TEXT NOT NULL,
                    case_name TEXT NOT NULL,
                    case_prompt TEXT NOT NULL,
                    expectations_json TEXT NOT NULL,
                    pass_threshold REAL NOT NULL,
                    runtime_type TEXT NOT NULL,
                    run_status TEXT NOT NULL,
                    checks_json TEXT NOT NULL,
                    score REAL NOT NULL,
                    passed INTEGER NOT NULL,
                    previous_score REAL,
                    score_delta REAL,
                    regression INTEGER NOT NULL,
                    evaluated_at TEXT NOT NULL,
                    UNIQUE(case_id, run_id)
                );

                CREATE INDEX IF NOT EXISTS evaluation_results_case_time
                ON evaluation_results(case_id, evaluated_at DESC, id DESC);
                """
            )

    def create_case(self, value: EvaluationCaseInput) -> EvaluationCase:
        now = datetime.now(UTC)
        case_id = str(uuid.uuid4())
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO evaluation_cases (
                    id, name, prompt, expectations_json, pass_threshold,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    value.name,
                    value.prompt,
                    value.expectations.model_dump_json(),
                    value.pass_threshold,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        return self.get_case(case_id)

    def update_case(self, case_id: str, value: EvaluationCaseInput) -> EvaluationCase:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE evaluation_cases
                SET name = ?, prompt = ?, expectations_json = ?,
                    pass_threshold = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    value.name,
                    value.prompt,
                    value.expectations.model_dump_json(),
                    value.pass_threshold,
                    datetime.now(UTC).isoformat(),
                    case_id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown evaluation case: {case_id}")
        return self.get_case(case_id)

    def get_case(self, case_id: str) -> EvaluationCase:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM evaluation_cases WHERE id = ?", (case_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown evaluation case: {case_id}")
        return self._to_case(row)

    def list_cases(self, limit: int = 100) -> list[EvaluationCase]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM evaluation_cases
                ORDER BY updated_at DESC, id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._to_case(row) for row in rows]

    def get_pair_result(self, case_id: str, run_id: str) -> EvaluationResult | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM evaluation_results
                WHERE case_id = ? AND run_id = ?
                """,
                (case_id, run_id),
            ).fetchone()
        return self._to_result(row) if row is not None else None

    def previous_result(
        self, case_id: str, *, exclude_run_id: str
    ) -> EvaluationResult | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM evaluation_results
                WHERE case_id = ? AND run_id != ?
                ORDER BY evaluated_at DESC, id DESC LIMIT 1
                """,
                (case_id, exclude_run_id),
            ).fetchone()
        return self._to_result(row) if row is not None else None

    def save_result(self, result: EvaluationResult) -> EvaluationResult:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO evaluation_results (
                    id, case_id, run_id, case_name, case_prompt,
                    expectations_json, pass_threshold, runtime_type, run_status,
                    checks_json, score, passed, previous_score, score_delta,
                    regression, evaluated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id, run_id) DO UPDATE SET
                    case_name = excluded.case_name,
                    case_prompt = excluded.case_prompt,
                    expectations_json = excluded.expectations_json,
                    pass_threshold = excluded.pass_threshold,
                    runtime_type = excluded.runtime_type,
                    run_status = excluded.run_status,
                    checks_json = excluded.checks_json,
                    score = excluded.score,
                    passed = excluded.passed,
                    previous_score = excluded.previous_score,
                    score_delta = excluded.score_delta,
                    regression = excluded.regression,
                    evaluated_at = excluded.evaluated_at
                """,
                (
                    result.id,
                    result.case_id,
                    result.run_id,
                    result.case_name,
                    result.case_prompt,
                    result.expectations.model_dump_json(),
                    result.pass_threshold,
                    result.runtime_type,
                    result.run_status,
                    json.dumps(
                        [check.model_dump(mode="json") for check in result.checks],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    result.score,
                    int(result.passed),
                    result.previous_score,
                    result.score_delta,
                    int(result.regression),
                    result.evaluated_at.isoformat(),
                ),
            )
        saved = self.get_pair_result(result.case_id, result.run_id)
        if saved is None:
            raise RuntimeError("Evaluation result was not persisted")
        return saved

    def get_result(self, result_id: str) -> EvaluationResult:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM evaluation_results WHERE id = ?", (result_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown evaluation result: {result_id}")
        return self._to_result(row)

    def list_results(
        self,
        *,
        case_id: str | None = None,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[EvaluationResult]:
        filters: list[str] = []
        parameters: list[object] = []
        if case_id is not None:
            filters.append("case_id = ?")
            parameters.append(case_id)
        if run_id is not None:
            filters.append("run_id = ?")
            parameters.append(run_id)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        parameters.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM evaluation_results {where}
                ORDER BY evaluated_at DESC, id DESC LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [self._to_result(row) for row in rows]

    @staticmethod
    def _to_case(row: sqlite3.Row) -> EvaluationCase:
        return EvaluationCase(
            id=row["id"],
            name=row["name"],
            prompt=row["prompt"],
            expectations=EvaluationExpectations.model_validate_json(
                row["expectations_json"]
            ),
            pass_threshold=row["pass_threshold"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _to_result(row: sqlite3.Row) -> EvaluationResult:
        return EvaluationResult(
            id=row["id"],
            case_id=row["case_id"],
            run_id=row["run_id"],
            case_name=row["case_name"],
            case_prompt=row["case_prompt"],
            expectations=EvaluationExpectations.model_validate_json(
                row["expectations_json"]
            ),
            pass_threshold=row["pass_threshold"],
            runtime_type=row["runtime_type"],
            run_status=row["run_status"],
            checks=[
                EvaluationCheck.model_validate(check)
                for check in json.loads(row["checks_json"])
            ],
            score=row["score"],
            passed=bool(row["passed"]),
            previous_score=row["previous_score"],
            score_delta=row["score_delta"],
            regression=bool(row["regression"]),
            evaluated_at=row["evaluated_at"],
        )
