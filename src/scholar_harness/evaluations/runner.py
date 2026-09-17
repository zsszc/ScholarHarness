from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from scholar_harness.chat_sessions import ChatSessionManager
from scholar_harness.evaluations.models import EvaluationExecution
from scholar_harness.evaluations.repository import SQLiteEvaluationRepository
from scholar_harness.evaluations.service import TraceEvaluator
from scholar_harness.runtimes.openai_compatible import ModelAdapterError


class EvaluationExecutionError(RuntimeError):
    pass


class EvaluationRunner:
    def __init__(
        self,
        sessions: ChatSessionManager,
        evaluations: SQLiteEvaluationRepository,
        evaluator: TraceEvaluator,
    ) -> None:
        self._sessions = sessions
        self._evaluations = evaluations
        self._evaluator = evaluator

    async def execute(self, case_id: str) -> EvaluationExecution:
        case = self._evaluations.get_case(case_id)
        started_at = datetime.now(UTC)
        session = await self._sessions.create()
        event_count = 0
        runtime_error: str | None = None
        try:
            try:
                async for _event in session.stream(case.prompt):
                    event_count += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                runtime_error = self._public_error(exc)

            info = await session.info()
            if info.last_run_id is None:
                raise EvaluationExecutionError(
                    "Evaluation execution did not create a trace run"
                )
            result = self._evaluator.evaluate(case.id, info.last_run_id)
            return EvaluationExecution(
                result=result,
                run_id=info.last_run_id,
                event_count=event_count,
                runtime_error=runtime_error,
                started_at=started_at,
                ended_at=datetime.now(UTC),
            )
        finally:
            await asyncio.shield(self._sessions.delete(session.id))

    @staticmethod
    def _public_error(exc: Exception) -> str:
        if isinstance(exc, ModelAdapterError):
            return "model_error"
        return "runtime_error"
