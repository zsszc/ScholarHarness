from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from pydantic import BaseModel, ConfigDict, Field


class ToolExecutionContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    runtime_type: str = Field(min_length=1)
    session_id: str | None = None
    entry_id: str | None = None
    trace_run_id: str | None = None
    tool_call_id: str | None = None


class TraceExecutionBinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    runtime_type: str


_TRACE_BINDING: ContextVar[TraceExecutionBinding | None] = ContextVar(
    "scholar_harness_trace_binding", default=None
)


def current_trace_binding() -> TraceExecutionBinding | None:
    return _TRACE_BINDING.get()


@contextmanager
def bind_trace_execution(
    run_id: str, runtime_type: str
) -> Iterator[TraceExecutionBinding]:
    binding = TraceExecutionBinding(run_id=run_id, runtime_type=runtime_type)
    token = _TRACE_BINDING.set(binding)
    try:
        yield binding
    finally:
        _TRACE_BINDING.reset(token)
