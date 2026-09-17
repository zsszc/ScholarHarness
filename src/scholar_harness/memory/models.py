from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MemoryKind = Literal["semantic", "episodic", "procedural"]
MemoryScope = Literal["global", "session", "branch"]
MemoryStatus = Literal["candidate", "confirmed", "rejected", "superseded"]


class MemoryEvidence(BaseModel):
    paper_id: str = Field(min_length=1)
    passage_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)


class Memory(BaseModel):
    id: str
    content: str
    kind: MemoryKind
    scope: MemoryScope
    status: MemoryStatus
    confidence: float
    evidence: list[MemoryEvidence]
    source_session_id: str | None = None
    source_entry_id: str | None = None
    trace_run_id: str | None = None
    source_tool_call_id: str | None = None
    created_at: datetime
    updated_at: datetime


class SaveMemoryInput(BaseModel):
    content: str = Field(min_length=1, max_length=8_000)
    kind: MemoryKind = "semantic"
    scope: MemoryScope = "global"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[MemoryEvidence] = Field(min_length=1, max_length=20)
    source_session_id: str | None = None
    source_entry_id: str | None = None
    trace_run_id: str | None = None
    source_tool_call_id: str | None = None


class RecallMemoryInput(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)
