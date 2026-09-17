from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from scholar_harness.chat_sessions import ChatConfigurationError
from scholar_harness.evaluations.models import EvaluationSuiteItem, EvaluationSuiteRun
from scholar_harness.evaluations.repository import SQLiteEvaluationRepository
from scholar_harness.evaluations.runner import EvaluationExecutionError, EvaluationRunner
from scholar_harness.evaluations.service import EvaluationConflictError


class EvaluationSuiteRunner:
    def __init__(
        self, repository: SQLiteEvaluationRepository, runner: EvaluationRunner
    ) -> None:
        self._repository = repository
        self._runner = runner

    async def execute(self, suite_id: str) -> EvaluationSuiteRun:
        suite = self._repository.get_suite(suite_id)
        cases = [self._repository.get_case(case_id) for case_id in suite.case_ids]
        started_at = datetime.now(UTC)
        items: list[EvaluationSuiteItem] = []
        for position, case in enumerate(cases):
            common = dict(
                position=position,
                case_id=case.id,
                case_name=case.name,
                case_prompt=case.prompt,
                expectations=case.expectations.model_copy(deep=True),
                pass_threshold=case.pass_threshold,
            )
            try:
                execution = await self._runner.execute(case.id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                items.append(
                    EvaluationSuiteItem(**common, error=self._public_error(exc))
                )
            else:
                items.append(
                    EvaluationSuiteItem(
                        **common,
                        result_id=execution.result.id,
                        run_id=execution.run_id,
                        event_count=execution.event_count,
                        runtime_error=execution.runtime_error,
                        score=execution.result.score,
                        passed=execution.result.passed,
                    )
                )
        passed_count = sum(item.passed for item in items)
        error_count = sum(item.error is not None for item in items)
        failed_count = len(items) - passed_count - error_count
        return self._repository.save_suite_run(
            EvaluationSuiteRun(
                id=str(uuid.uuid4()),
                suite_id=suite.id,
                suite_name=suite.name,
                case_ids=list(suite.case_ids),
                items=items,
                total_count=len(items),
                passed_count=passed_count,
                failed_count=failed_count,
                error_count=error_count,
                passed=passed_count == len(items),
                started_at=started_at,
                ended_at=datetime.now(UTC),
            )
        )

    @staticmethod
    def _public_error(exc: Exception) -> str:
        if isinstance(exc, ChatConfigurationError):
            return "configuration_error"
        if isinstance(exc, (EvaluationConflictError, EvaluationExecutionError)):
            return "evaluation_error"
        return "execution_error"
