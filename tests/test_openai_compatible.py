from __future__ import annotations

import json

import httpx
import pytest

from scholar_harness.runtimes.model import (
    ModelMessage,
    ModelToolCall,
    ModelToolDefinition,
)
from scholar_harness.runtimes.openai_compatible import (
    ModelAdapterError,
    OpenAICompatibleAdapter,
)


async def test_serializes_chat_tools_and_parses_tool_calls() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://models.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer private-key"
        body = json.loads(request.content)
        assert body["model"] == "example-model"
        assert body["tool_choice"] == "auto"
        assert body["tools"] == [
            {
                "type": "function",
                "function": {
                    "name": "search_papers",
                    "description": "Search papers.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                },
            }
        ]
        assert body["messages"][1]["tool_calls"][0]["function"] == {
            "name": "search_papers",
            "arguments": '{"query":"memory"}',
        }
        assert body["messages"][2] == {
            "role": "tool",
            "content": '{"items":[]}',
            "tool_call_id": "old-call",
        }
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "I will search.",
                            "tool_calls": [
                                {
                                    "id": "new-call",
                                    "type": "function",
                                    "function": {
                                        "name": "search_papers",
                                        "arguments": '{"query":"agents"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = OpenAICompatibleAdapter(
        model="example-model",
        base_url="https://models.example/v1/",
        api_key="private-key",
        client=client,
    )
    messages = [
        ModelMessage(role="user", content="Find memory papers"),
        ModelMessage(
            role="assistant",
            tool_calls=[
                ModelToolCall(
                    id="old-call", name="search_papers", arguments={"query": "memory"}
                )
            ],
        ),
        ModelMessage(
            role="tool", content='{"items":[]}', tool_call_id="old-call"
        ),
    ]
    tools = [
        ModelToolDefinition(
            name="search_papers",
            description="Search papers.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
        )
    ]

    response = await adapter.complete(messages, tools)
    await adapter.aclose()

    assert response.content == "I will search."
    assert response.tool_calls[0] == ModelToolCall(
        id="new-call", name="search_papers", arguments={"query": "agents"}
    )
    assert response.usage == {"prompt_tokens": 10, "completion_tokens": 4}
    assert client.is_closed is False
    await client.aclose()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({}, "response has no choices"),
        ({"choices": [{}]}, "choice has no message"),
        (
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call",
                                    "type": "custom",
                                    "custom": {"name": "x"},
                                }
                            ],
                        }
                    }
                ]
            },
            "unsupported tool call type",
        ),
        (
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call",
                                    "type": "function",
                                    "function": {"name": "x", "arguments": "not-json"},
                                }
                            ],
                        }
                    }
                ]
            },
            "invalid arguments for tool x",
        ),
    ],
)
async def test_rejects_malformed_success_payloads(body, message) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleAdapter(model="model", client=client)
        with pytest.raises(ModelAdapterError, match=message):
            await adapter.complete([ModelMessage(role="user", content="hi")], [])


async def test_http_error_is_bounded_and_redacts_api_key() -> None:
    secret = "super-secret-key"

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=f"rejected {secret} " + ("x" * 2_000))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleAdapter(model="model", api_key=secret, client=client)
        with pytest.raises(ModelAdapterError) as caught:
            await adapter.complete([ModelMessage(role="user", content="hi")], [])

    error = str(caught.value)
    assert "status=401" in error
    assert secret not in error
    assert "[REDACTED]" in error
    assert len(error) < 1_200


async def test_transport_error_does_not_expose_provider_url() -> None:
    secret_url = "https://provider-token@example.invalid/v1"

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("failed", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleAdapter(
            model="model", base_url=secret_url, client=client
        )
        with pytest.raises(ModelAdapterError) as caught:
            await adapter.complete([ModelMessage(role="user", content="hi")], [])

    error = str(caught.value)
    assert error == "model_transport_error: ConnectError"
    assert secret_url not in error


async def test_rejects_invalid_local_messages_before_http() -> None:
    adapter = OpenAICompatibleAdapter(model="model")

    try:
        with pytest.raises(ModelAdapterError, match="missing tool_call_id"):
            adapter._serialize_message(ModelMessage(role="tool", content="result"))
        with pytest.raises(ModelAdapterError, match="only assistant"):
            adapter._serialize_message(
                ModelMessage(
                    role="user",
                    tool_calls=[ModelToolCall(id="call", name="x", arguments={})],
                )
            )
    finally:
        await adapter.aclose()
