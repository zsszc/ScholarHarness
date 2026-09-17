from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from scholar_harness.runtimes.model import (
    ModelAdapter,
    ModelMessage,
    ModelResponse,
    ModelToolCall,
    ModelToolDefinition,
)

_ERROR_PREVIEW_CHARS = 1_024


class ModelAdapterError(RuntimeError):
    """A credential-safe HTTP or protocol failure from a model adapter."""


class OpenAICompatibleAdapter(ModelAdapter):
    def __init__(
        self,
        *,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("model cannot be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not base_url.strip():
            raise ValueError("base_url cannot be empty")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or None
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def complete(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition],
    ) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [self._serialize_message(message) for message in messages],
        }
        if tools:
            payload["tools"] = [self._serialize_tool(tool) for tool in tools]
            payload["tool_choice"] = "auto"

        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        try:
            response = await self._client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise ModelAdapterError(f"model_transport_error: {exc}") from exc

        if not response.is_success:
            preview = response.text[:_ERROR_PREVIEW_CHARS]
            if self.api_key:
                preview = preview.replace(self.api_key, "[REDACTED]")
            raise ModelAdapterError(
                f"model_http_error: status={response.status_code} body={preview}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise ModelAdapterError("model_protocol_error: response is not JSON") from exc
        return self._parse_response(body)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _serialize_message(message: ModelMessage) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.name and message.role != "tool":
            payload["name"] = message.name
        if message.role == "tool":
            if not message.tool_call_id:
                raise ModelAdapterError(
                    "model_protocol_error: tool message is missing tool_call_id"
                )
            payload["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            if message.role != "assistant":
                raise ModelAdapterError(
                    "model_protocol_error: only assistant messages may contain tool calls"
                )
            payload["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(
                            call.arguments, ensure_ascii=False, separators=(",", ":")
                        ),
                    },
                }
                for call in message.tool_calls
            ]
        return payload

    @staticmethod
    def _serialize_tool(tool: ModelToolDefinition) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    @classmethod
    def _parse_response(cls, body: Any) -> ModelResponse:
        if not isinstance(body, Mapping):
            raise ModelAdapterError("model_protocol_error: response must be an object")
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ModelAdapterError("model_protocol_error: response has no choices")
        first = choices[0]
        if not isinstance(first, Mapping) or not isinstance(first.get("message"), Mapping):
            raise ModelAdapterError("model_protocol_error: choice has no message")
        message = first["message"]
        content = cls._parse_content(message.get("content"))
        tool_calls = cls._parse_tool_calls(message.get("tool_calls", []))
        usage_value = body.get("usage", {})
        usage = dict(usage_value) if isinstance(usage_value, Mapping) else {}
        return ModelResponse(content=content, tool_calls=tool_calls, usage=usage)

    @staticmethod
    def _parse_content(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts = []
            for part in value:
                if isinstance(part, Mapping) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
            if parts:
                return "".join(parts)
        raise ModelAdapterError("model_protocol_error: unsupported message content")

    @staticmethod
    def _parse_tool_calls(value: Any) -> list[ModelToolCall]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ModelAdapterError("model_protocol_error: tool_calls must be a list")
        parsed = []
        for raw_call in value:
            if not isinstance(raw_call, Mapping) or raw_call.get("type") != "function":
                raise ModelAdapterError(
                    "model_protocol_error: unsupported tool call type"
                )
            function = raw_call.get("function")
            if not isinstance(function, Mapping):
                raise ModelAdapterError(
                    "model_protocol_error: tool call has no function"
                )
            call_id = raw_call.get("id")
            name = function.get("name")
            arguments_json = function.get("arguments")
            if not isinstance(call_id, str) or not isinstance(name, str):
                raise ModelAdapterError(
                    "model_protocol_error: tool call id and name must be strings"
                )
            if not isinstance(arguments_json, str):
                raise ModelAdapterError(
                    "model_protocol_error: tool arguments must be JSON text"
                )
            try:
                arguments = json.loads(arguments_json)
            except json.JSONDecodeError as exc:
                raise ModelAdapterError(
                    f"model_protocol_error: invalid arguments for tool {name}"
                ) from exc
            if not isinstance(arguments, dict):
                raise ModelAdapterError(
                    f"model_protocol_error: arguments for tool {name} must be an object"
                )
            parsed.append(ModelToolCall(id=call_id, name=name, arguments=arguments))
        return parsed
