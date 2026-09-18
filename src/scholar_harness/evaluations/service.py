from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from scholar_harness.evaluations.models import (
    EvaluationCase,
    EvaluationCheck,
    EvaluationResult,
)
from scholar_harness.evaluations.repository import SQLiteEvaluationRepository
from scholar_harness.traces.models import AgentRun, ToolExecution, TraceEvent
from scholar_harness.traces.repository import SQLiteTraceRepository


class EvaluationConflictError(RuntimeError):
    pass


class TraceEvaluator:
    def __init__(
        self,
        traces: SQLiteTraceRepository,
        evaluations: SQLiteEvaluationRepository,
    ) -> None:
        self._traces = traces
        self._evaluations = evaluations

    def evaluate(self, case_id: str, run_id: str) -> EvaluationResult:
        case = self._evaluations.get_case(case_id)
        run = self._traces.get_run(run_id)
        if run.status == "running" or run.ended_at is None:
            raise EvaluationConflictError("Running traces cannot be evaluated")
        events = self._traces.list_events(run_id)
        tools = self._traces.list_tool_executions(run_id)
        checks = self._checks(case, run, events, tools)
        score = sum(check.passed for check in checks) / len(checks)
        previous = self._evaluations.previous_result(
            case_id, exclude_run_id=run_id
        )
        previous_score = previous.score if previous is not None else None
        score_delta = score - previous_score if previous_score is not None else None
        existing = self._evaluations.get_pair_result(case_id, run_id)
        result = EvaluationResult(
            id=existing.id if existing is not None else str(uuid.uuid4()),
            case_id=case.id,
            run_id=run.id,
            case_name=case.name,
            case_prompt=case.prompt,
            expectations=case.expectations.model_copy(deep=True),
            pass_threshold=case.pass_threshold,
            runtime_type=run.runtime_type,
            run_status=run.status,
            checks=checks,
            score=score,
            passed=score >= case.pass_threshold,
            previous_score=previous_score,
            score_delta=score_delta,
            regression=score_delta is not None and score_delta < 0,
            evaluated_at=datetime.now(UTC),
        )
        return self._evaluations.save_result(result)

    def _checks(
        self,
        case: EvaluationCase,
        run: AgentRun,
        events: list[TraceEvent],
        tools: list[ToolExecution],
    ) -> list[EvaluationCheck]:
        expected = case.expectations
        checks: list[EvaluationCheck] = []
        if expected.terminal_status is not None:
            checks.append(
                self._check(
                    "run_status",
                    run.status == expected.terminal_status,
                    f"Run status is {run.status}",
                    expected.terminal_status,
                    run.status,
                )
            )

        for name in expected.required_tools:
            matching = [tool for tool in tools if tool.tool_name == name]
            successful = [tool for tool in matching if tool.is_error is False]
            checks.append(
                self._check(
                    f"required_tool:{name}",
                    bool(successful),
                    f"Required tool {name} had {len(successful)} successful execution(s)",
                    {"tool": name, "successful_minimum": 1},
                    {
                        "executions": len(matching),
                        "successful": len(successful),
                        "tool_call_ids": [tool.tool_call_id for tool in matching],
                    },
                )
            )

        for name in expected.forbidden_tools:
            matching = [tool for tool in tools if tool.tool_name == name]
            checks.append(
                self._check(
                    f"forbidden_tool:{name}",
                    not matching,
                    f"Forbidden tool {name} had {len(matching)} execution(s)",
                    {"tool": name, "executions": 0},
                    {
                        "executions": len(matching),
                        "tool_call_ids": [tool.tool_call_id for tool in matching],
                    },
                )
            )

        if expected.max_tool_calls is not None:
            checks.append(
                self._check(
                    "tool_call_limit",
                    len(tools) <= expected.max_tool_calls,
                    f"Run used {len(tools)} tool call(s)",
                    {"maximum": expected.max_tool_calls},
                    {"count": len(tools)},
                )
            )

        if expected.max_duration_ms is not None:
            assert run.ended_at is not None
            duration_ms = max(
                0.0, (run.ended_at - run.started_at).total_seconds() * 1_000
            )
            checks.append(
                self._check(
                    "duration_limit",
                    duration_ms <= expected.max_duration_ms,
                    f"Run duration was {duration_ms:.3f} ms",
                    {"maximum_ms": expected.max_duration_ms},
                    {"duration_ms": duration_ms},
                )
            )

        if expected.require_citation_validation:
            citations = [
                tool for tool in tools if tool.tool_name == "validate_citation"
            ]
            valid = [
                tool
                for tool in citations
                if tool.is_error is False
                and isinstance(tool.result, Mapping)
                and tool.result.get("valid") is True
            ]
            checks.append(
                self._check(
                    "citation_validation",
                    bool(valid),
                    f"Run had {len(valid)} valid citation check(s)",
                    {"required": expected.require_citation_validation},
                    {
                        "executions": len(citations),
                        "valid": len(valid),
                        "tool_call_ids": [tool.tool_call_id for tool in citations],
                    },
                )
            )

        if any(
            (
                expected.context_status is not None,
                expected.required_memory_ids,
                expected.forbidden_memory_ids,
                expected.max_context_items is not None,
            )
        ):
            context = self._context_observation(events)
            if expected.context_status is not None:
                checks.append(
                    self._check(
                        "context_status",
                        context["valid"]
                        and context["status"] == expected.context_status,
                        f"Context status is {context['status'] or context['reason']}",
                        {"status": expected.context_status},
                        context,
                    )
                )
            selected_ids = set(context["selected_ids"])
            for memory_id in expected.required_memory_ids:
                checks.append(
                    self._check(
                        f"required_memory:{memory_id}",
                        context["valid"] and memory_id in selected_ids,
                        f"Required memory {memory_id} "
                        f"{'was' if memory_id in selected_ids else 'was not'} selected",
                        {"memory_id": memory_id, "selected": True},
                        context,
                    )
                )
            for memory_id in expected.forbidden_memory_ids:
                checks.append(
                    self._check(
                        f"forbidden_memory:{memory_id}",
                        context["valid"] and memory_id not in selected_ids,
                        f"Forbidden memory {memory_id} "
                        f"{'was' if memory_id in selected_ids else 'was not'} selected",
                        {"memory_id": memory_id, "selected": False},
                        context,
                    )
                )
            if expected.max_context_items is not None:
                checks.append(
                    self._check(
                        "context_item_limit",
                        context["valid"]
                        and len(selected_ids) <= expected.max_context_items,
                        f"Context selected {len(selected_ids)} unique memory item(s)",
                        {"maximum": expected.max_context_items},
                        context,
                    )
                )

        answer = "".join(
            str(event.payload.get("delta") or "")
            for event in events
            if event.event_type == "message_update"
        )
        folded_answer = answer.casefold()
        for substring in expected.answer_contains:
            folded = substring.casefold()
            checks.append(
                self._check(
                    f"answer_contains:{folded}",
                    folded in folded_answer,
                    f"Answer {'contains' if folded in folded_answer else 'misses'} required text",
                    {"substring": substring},
                    {"answer": answer},
                )
            )
        return checks

    @staticmethod
    def _context_observation(events: list[TraceEvent]) -> dict[str, Any]:
        matching = [
            event for event in events if event.event_type == "context_injection"
        ]
        observation: dict[str, Any] = {
            "valid": False,
            "reason": "missing_event" if not matching else "duplicate_events",
            "event_count": len(matching),
            "status": None,
            "selected_ids": [],
            "reported_selected_count": None,
        }
        if len(matching) != 1:
            return observation
        payload = matching[0].payload
        status = payload.get("status")
        selected_ids = payload.get("selected_ids")
        reported_count = payload.get("selected_count")
        if (
            status not in {"selected", "empty", "error"}
            or not isinstance(selected_ids, list)
            or not all(isinstance(item, str) and item for item in selected_ids)
            or isinstance(reported_count, bool)
            or not isinstance(reported_count, int)
            or reported_count < 0
        ):
            observation["reason"] = "invalid_payload"
            return observation
        observation.update(
            {
                "valid": True,
                "reason": None,
                "status": status,
                "selected_ids": list(dict.fromkeys(selected_ids)),
                "reported_selected_count": reported_count,
            }
        )
        return observation

    @staticmethod
    def _check(
        check_id: str,
        passed: bool,
        message: str,
        expected: Any,
        observed: Any,
    ) -> EvaluationCheck:
        return EvaluationCheck(
            id=check_id,
            passed=passed,
            message=message,
            expected=expected,
            observed=observed,
        )
