from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class PreparedContext(BaseModel):
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class TurnContextProvider(Protocol):
    async def prepare(self, prompt: str, session_id: str) -> PreparedContext: ...
