from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TerminalRunStatus = Literal["completed", "failed", "aborted"]


class EvaluationExpectations(BaseModel):
    required_tools: list[str] = Field(default_factory=list, max_length=50)
    forbidden_tools: list[str] = Field(default_factory=list, max_length=50)
    max_tool_calls: int | None = Field(default=None, ge=0, le=1_000)
    max_duration_ms: float | None = Field(default=None, gt=0, le=86_400_000)
    require_citation_validation: bool = False
    answer_contains: list[str] = Field(default_factory=list, max_length=50)
    terminal_status: TerminalRunStatus | None = None

    @field_validator("required_tools", "forbidden_tools", "answer_contains")
    @classmethod
    def normalize_string_list(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("expectation list values cannot be empty")
            if len(cleaned) > 200:
                raise ValueError("expectation list values cannot exceed 200 characters")
            if cleaned not in normalized:
                normalized.append(cleaned)
        return normalized

    @model_validator(mode="after")
    def validate_expectations(self) -> EvaluationExpectations:
        overlap = set(self.required_tools) & set(self.forbidden_tools)
        if overlap:
            names = ", ".join(sorted(overlap))
            raise ValueError(f"tools cannot be both required and forbidden: {names}")
        configured = any(
            (
                self.required_tools,
                self.forbidden_tools,
                self.max_tool_calls is not None,
                self.max_duration_ms is not None,
                self.require_citation_validation,
                self.answer_contains,
                self.terminal_status is not None,
            )
        )
        if not configured:
            raise ValueError("at least one evaluation expectation is required")
        return self


class EvaluationCaseInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=20_000)
    expectations: EvaluationExpectations
    pass_threshold: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("name", "prompt")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value cannot be blank")
        return cleaned


class EvaluationCase(EvaluationCaseInput):
    id: str
    created_at: datetime
    updated_at: datetime


class EvaluationCheck(BaseModel):
    id: str
    passed: bool
    message: str
    expected: Any = None
    observed: Any = None


class EvaluationResult(BaseModel):
    id: str
    case_id: str
    run_id: str
    case_name: str
    case_prompt: str
    expectations: EvaluationExpectations
    pass_threshold: float
    runtime_type: str
    run_status: TerminalRunStatus
    checks: list[EvaluationCheck]
    score: float
    passed: bool
    previous_score: float | None = None
    score_delta: float | None = None
    regression: bool = False
    evaluated_at: datetime


class EvaluationExecution(BaseModel):
    result: EvaluationResult
    run_id: str
    event_count: int
    runtime_error: str | None = None
    started_at: datetime
    ended_at: datetime
