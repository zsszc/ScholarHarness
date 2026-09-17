from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentEvent(BaseModel):
    """Runtime-neutral event consumed by storage, evaluation, and UI layers."""

    type: str
    session_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    entry_id: str | None = None
    parent_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
