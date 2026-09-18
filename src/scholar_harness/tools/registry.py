from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from pydantic import BaseModel

from scholar_harness.tools.context import ToolExecutionContext

ToolHandler = Callable[[BaseModel], Mapping[str, Any] | Awaitable[Mapping[str, Any]]]
ContextToolHandler = Callable[
    [BaseModel, ToolExecutionContext | None],
    Mapping[str, Any] | Awaitable[Mapping[str, Any]],
]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: ToolHandler | ContextToolHandler
    context_aware: bool = False

    @property
    def json_schema(self) -> dict[str, Any]:
        return self.input_model.model_json_schema()


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def extend(self, other: ToolRegistry) -> None:
        for tool in other._tools.values():
            self.register(tool)

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {name}") from exc

    def schemas(self) -> dict[str, dict[str, Any]]:
        return {name: tool.json_schema for name, tool in self._tools.items()}

    def definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.json_schema,
            }
            for tool in self._tools.values()
        ]

    async def execute(
        self,
        name: str,
        arguments: Mapping[str, Any],
        *,
        context: ToolExecutionContext | None = None,
    ) -> Mapping[str, Any]:
        tool = self.get(name)
        validated = tool.input_model.model_validate(arguments)
        if tool.context_aware:
            handler = cast(ContextToolHandler, tool.handler)
            result = handler(validated, context)
        else:
            handler = cast(ToolHandler, tool.handler)
            result = handler(validated)
        if inspect.isawaitable(result):
            result = await result
        return result
