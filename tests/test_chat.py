from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

import pytest

import scholar_harness.cli as cli_module
from scholar_harness.chat import run_chat
from scholar_harness.cli import (
    ChatConfig,
    build_parser,
    resolve_chat_config,
    run_configured_chat,
    run_configured_evaluation,
    run_configured_evaluation_suite,
)
from scholar_harness.core.events import AgentEvent
from scholar_harness.memory.context import MemoryContextPolicy
from scholar_harness.memory.models import MemoryEvidence
from scholar_harness.memory.repository import SQLiteMemoryRepository
from scholar_harness.runtimes.base import AgentRuntime
from scholar_harness.runtimes.model import (
    ModelMessage,
    ModelResponse,
    ModelToolDefinition,
)
from scholar_harness.traces.repository import SQLiteTraceRepository


class ClosingModel:
    def __init__(
        self,
        response: ModelResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response or ModelResponse(content="hello from model")
        self.error = error
        self.tools: list[ModelToolDefinition] = []
        self.messages: list[ModelMessage] = []
        self.closed = False

    async def complete(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition],
    ) -> ModelResponse:
        self.messages = list(messages)
        self.tools = list(tools)
        if self.error is not None:
            raise self.error
        return self.response

    async def aclose(self) -> None:
        self.closed = True


class ControlRuntime(AgentRuntime):
    def __init__(self) -> None:
        self.started = False
        self.compactions: list[str | None] = []
        self.forks: list[str] = []
        self.entry = AgentEvent(
            type="message",
            session_id="control",
            entry_id="known-entry",
            data={"role": "assistant", "content": "prior"},
        )

    async def start(self) -> None:
        self.started = True

    async def stream(self, prompt: str) -> AsyncIterator[AgentEvent]:
        assert prompt == "ask"
        yield AgentEvent(
            type="message_update", session_id="control", data={"delta": "answer"}
        )
        yield AgentEvent(
            type="tool_execution_start",
            session_id="control",
            data={"toolName": "search_papers"},
        )
        yield AgentEvent(
            type="tool_execution_end",
            session_id="control",
            data={"toolName": "search_papers", "isError": False},
        )

    async def abort(self) -> None:
        return None

    async def compact(self, instructions: str | None = None) -> None:
        self.compactions.append(instructions)

    async def fork(self, entry_id: str) -> None:
        if entry_id != "known-entry":
            raise KeyError(entry_id)
        self.forks.append(entry_id)

    async def get_entries(self, since: str | None = None) -> list[AgentEvent]:
        return [self.entry]

    async def close(self) -> None:
        return None


def chat_args(*arguments: str):
    return build_parser().parse_args(["chat", *arguments])


def test_resolves_chat_configuration_without_raw_key_option(tmp_path) -> None:
    args = chat_args(
        "--model",
        "cli-model",
        "--base-url",
        "http://localhost:11434/v1",
        "--api-key-env",
        "LOCAL_KEY",
        "--database",
        str(tmp_path / "chat.db"),
        "--no-trace",
    )

    config = resolve_chat_config(args, {"LOCAL_KEY": "private"})

    assert config.model == "cli-model"
    assert config.base_url == "http://localhost:11434/v1"
    assert config.api_key == "private"
    assert config.trace is False
    with pytest.raises(SystemExit):
        chat_args("--model", "x", "--api-key", "must-not-be-accepted")


def test_chat_configuration_requires_model() -> None:
    with pytest.raises(ValueError, match="--model or set OPENAI_MODEL"):
        resolve_chat_config(chat_args(), {})

    with pytest.raises(ValueError, match="timeout must be positive"):
        resolve_chat_config(chat_args("--model", "x", "--timeout", "0"), {})


async def test_one_shot_composition_exposes_tools_traces_and_closes(tmp_path) -> None:
    database = tmp_path / "chat.db"
    model = ClosingModel()
    config = ChatConfig(
        model="fake",
        base_url="http://unused/v1",
        api_key=None,
        database=database,
        timeout_seconds=1,
        prompt="hello",
        trace=True,
    )
    output: list[str] = []

    run_id = await run_configured_chat(config, adapter=model, output_fn=output.append)

    assert output == ["hello from model"]
    assert model.closed is True
    assert {tool.name for tool in model.tools} == {
        "search_papers",
        "read_passage",
        "validate_citation",
        "save_memory",
        "recall_memory",
    }
    assert run_id is not None
    run = SQLiteTraceRepository(database).get_run(run_id)
    assert run.status == "completed"
    assert run.runtime_type == "mini-py-openai-compatible"


async def test_cli_chat_automatically_injects_confirmed_memory(tmp_path) -> None:
    database = tmp_path / "memory-chat.db"
    memories = SQLiteMemoryRepository(database)
    memory = memories.create_candidate(
        content="beacon supports automatic memory context",
        kind="semantic",
        scope="global",
        confidence=0.9,
        evidence=[
            MemoryEvidence(
                paper_id="paper-1",
                passage_id="passage-2",
                quote="memory evidence",
                page=3,
            )
        ],
    )
    memories.set_status(memory.id, "confirmed")
    model = ClosingModel()
    config = ChatConfig(
        model="fake",
        base_url="http://unused/v1",
        api_key=None,
        database=database,
        timeout_seconds=1,
        prompt="explain beacon",
        trace=True,
    )

    run_id = await run_configured_chat(config, adapter=model, output_fn=lambda _: None)

    assert [message.role for message in model.messages] == ["system", "user"]
    assert memory.id in model.messages[0].content
    assert "paper-1/passage-2/page-3" in model.messages[0].content
    assert run_id is not None
    context_event = next(
        event
        for event in SQLiteTraceRepository(database).list_events(run_id)
        if event.event_type == "context_injection"
    )
    assert context_event.payload["selected_ids"] == [memory.id]


async def test_model_failure_still_closes_adapter_and_records_failed_trace(tmp_path) -> None:
    database = tmp_path / "failed-chat.db"
    model = ClosingModel(error=RuntimeError("provider failed"))
    config = ChatConfig(
        model="fake",
        base_url="http://unused/v1",
        api_key=None,
        database=database,
        timeout_seconds=1,
        prompt="hello",
        trace=True,
    )

    with pytest.raises(RuntimeError, match="provider failed"):
        await run_configured_chat(config, adapter=model)

    assert model.closed is True
    runs = SQLiteTraceRepository(database).list_runs()
    assert runs[0].status == "failed"


async def test_evaluation_entry_points_compose_default_memory_policy(
    tmp_path, monkeypatch
) -> None:
    captured = []

    class StubManager:
        async def close_all(self) -> None:
            return None

    def capture_manager(**kwargs):
        captured.append(kwargs)
        return StubManager()

    monkeypatch.setattr(cli_module, "create_default_chat_manager", capture_manager)
    database = tmp_path / "evaluation-context.db"

    with pytest.raises(KeyError, match="Unknown evaluation case"):
        await run_configured_evaluation("missing", database)
    with pytest.raises(KeyError, match="Unknown evaluation suite"):
        await run_configured_evaluation_suite("missing", database)

    assert len(captured) == 2
    assert all(
        isinstance(call["context_provider"], MemoryContextPolicy) for call in captured
    )


async def test_interactive_controls_and_tool_activity() -> None:
    runtime = ControlRuntime()
    commands = iter(
        [
            "/help",
            "ask",
            "/entries",
            "/compact keep evidence",
            "/fork missing",
            "/fork known-entry",
            "/unknown",
            "/exit",
        ]
    )
    output: list[str] = []

    await run_chat(runtime, input_fn=lambda _prompt: next(commands), output_fn=output.append)

    assert runtime.started is True
    assert runtime.compactions == ["keep evidence"]
    assert runtime.forks == ["known-entry"]
    assert any("/compact" in line for line in output)
    assert "answer" in output
    assert "[tool] search_papers started" in output
    assert "[tool] search_papers ok" in output
    assert any("known-entry parent=-" in line for line in output)
    assert any(line.startswith("Error:") for line in output)
    assert "Forked from known-entry." in output
    assert "Unknown command. Type /help for commands." in output


async def test_eof_exits_interactive_chat() -> None:
    runtime = ControlRuntime()

    def end(_prompt: str) -> str:
        raise EOFError

    await run_chat(runtime, input_fn=end, output_fn=lambda _line: None)

    assert runtime.started is True
