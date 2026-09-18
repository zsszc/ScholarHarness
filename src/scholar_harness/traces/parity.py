from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from scholar_harness.traces.models import TraceEvent
from scholar_harness.traces.repository import SQLiteTraceRepository

_LIFECYCLE_TYPES = {
    "agent_start",
    "context_injection",
    "message_update",
    "tool_execution_start",
    "tool_execution_end",
    "agent_end",
    "agent_settled",
}


class ToolOutcome(BaseModel):
    tool_name: str
    is_error: bool | None = None


class RuntimeBehaviorSnapshot(BaseModel):
    run_id: str
    runtime_type: str
    terminal_status: str
    lifecycle: list[str]
    tools: list[ToolOutcome]
    context_statuses: list[str]
    assistant_text: str


class ParityCheck(BaseModel):
    name: str
    passed: bool
    left: Any
    right: Any


class RuntimeParityReport(BaseModel):
    schema_version: Literal[1] = 1
    left_run_id: str
    left_runtime_type: str
    right_run_id: str
    right_runtime_type: str
    strict_output: bool
    passed: bool
    checks: list[ParityCheck]


class RuntimeParityService:
    def __init__(self, repository: SQLiteTraceRepository) -> None:
        self._repository = repository

    def snapshot(self, run_id: str) -> RuntimeBehaviorSnapshot:
        run = self._repository.get_run(run_id)
        events = self._repository.list_events(run_id)
        lifecycle = self._lifecycle(events)
        context_statuses = [
            str(event.payload.get("status") or "unknown")
            for event in events
            if event.event_type == "context_injection"
        ]
        assistant_text = "".join(
            self._message_delta(event.payload)
            for event in events
            if event.event_type == "message_update"
        )
        tools = self._tool_outcomes(events)
        return RuntimeBehaviorSnapshot(
            run_id=run.id,
            runtime_type=run.runtime_type,
            terminal_status=run.status,
            lifecycle=lifecycle,
            tools=tools,
            context_statuses=context_statuses,
            assistant_text=assistant_text,
        )

    def compare(
        self,
        left_run_id: str,
        right_run_id: str,
        *,
        strict_output: bool = False,
    ) -> RuntimeParityReport:
        left = self.snapshot(left_run_id)
        right = self.snapshot(right_run_id)
        checks = [
            self._check(
                "terminal_status", left.terminal_status, right.terminal_status
            ),
            self._check("lifecycle", left.lifecycle, right.lifecycle),
            self._check(
                "tool_outcomes",
                [item.model_dump() for item in left.tools],
                [item.model_dump() for item in right.tools],
            ),
            self._check(
                "context_statuses", left.context_statuses, right.context_statuses
            ),
            self._check(
                "assistant_output_present",
                bool(left.assistant_text),
                bool(right.assistant_text),
            ),
        ]
        if strict_output:
            checks.append(
                self._check(
                    "assistant_output_exact",
                    left.assistant_text,
                    right.assistant_text,
                )
            )
        return RuntimeParityReport(
            left_run_id=left.run_id,
            left_runtime_type=left.runtime_type,
            right_run_id=right.run_id,
            right_runtime_type=right.runtime_type,
            strict_output=strict_output,
            passed=all(check.passed for check in checks),
            checks=checks,
        )

    @staticmethod
    def _check(name: str, left: Any, right: Any) -> ParityCheck:
        return ParityCheck(name=name, passed=left == right, left=left, right=right)

    @staticmethod
    def _message_delta(payload: dict[str, Any]) -> str:
        value = payload.get("delta")
        if value is None:
            value = payload.get("text")
        return str(value or "")

    @staticmethod
    def _lifecycle(events: list[TraceEvent]) -> list[str]:
        lifecycle: list[str] = []
        for event in events:
            event_type = event.event_type
            if event_type not in _LIFECYCLE_TYPES:
                continue
            if event_type == "message_update" and lifecycle[-1:] == [event_type]:
                continue
            lifecycle.append(event_type)
        return lifecycle

    @staticmethod
    def _tool_outcomes(events: list[TraceEvent]) -> list[ToolOutcome]:
        outcomes: list[ToolOutcome] = []
        positions: dict[str, int] = {}
        for event in events:
            if event.event_type == "tool_execution_start":
                call_id = str(event.payload.get("toolCallId") or "")
                if call_id and call_id not in positions:
                    positions[call_id] = len(outcomes)
                    outcomes.append(
                        ToolOutcome(
                            tool_name=str(
                                event.payload.get("toolName") or "unknown"
                            )
                        )
                    )
            elif event.event_type == "tool_execution_end":
                call_id = str(event.payload.get("toolCallId") or "")
                outcome = ToolOutcome(
                    tool_name=str(event.payload.get("toolName") or "unknown"),
                    is_error=bool(event.payload.get("isError")),
                )
                position = positions.get(call_id)
                if position is None:
                    positions[call_id] = len(outcomes)
                    outcomes.append(outcome)
                else:
                    if outcome.tool_name == "unknown":
                        outcome.tool_name = outcomes[position].tool_name
                    outcomes[position] = outcome
        return outcomes
