from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class ModelToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ModelMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ModelToolCall] = Field(default_factory=list)


class ModelToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class ModelResponse(BaseModel):
    content: str = ""
    tool_calls: list[ModelToolCall] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)


class ModelAdapter(Protocol):
    async def complete(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition],
    ) -> ModelResponse: ...
