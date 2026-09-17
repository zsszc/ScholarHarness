from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

RunStatus = Literal["running", "completed", "failed", "aborted"]


class AgentRun(BaseModel):
    id: str
    runtime_type: str
    external_session_id: str | None = None
    status: RunStatus
    active_leaf_id: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    error: str | None = None


class TraceEvent(BaseModel):
    id: int
    run_id: str
    sequence: int
    event_type: str
    entry_id: str | None = None
    parent_id: str | None = None
    event_timestamp: datetime
    idempotency_key: str | None = None
    payload: dict[str, Any]


class ToolExecution(BaseModel):
    run_id: str
    tool_call_id: str
    tool_name: str
    arguments: Any = None
    result: Any = None
    is_error: bool | None = None
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = None
