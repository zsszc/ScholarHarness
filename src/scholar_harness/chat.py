from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from scholar_harness.memory.repository import SQLiteMemoryRepository
from scholar_harness.memory.tools import build_memory_tools
from scholar_harness.papers.repository import SQLitePaperRepository
from scholar_harness.papers.tools import build_paper_tools
from scholar_harness.runtimes.base import AgentRuntime
from scholar_harness.tools.registry import ToolRegistry

InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], None]

_HELP = """Commands:
  /help                     Show this help
  /compact [instructions]   Compact the active context path
  /fork ENTRY_ID            Fork the next turn from an existing entry
  /entries                  List append-only session entries
  /exit or /quit            End the chat"""


def build_chat_tools(database: Path | str) -> ToolRegistry:
    papers = SQLitePaperRepository(database)
    memories = SQLiteMemoryRepository(database)
    tools = build_paper_tools(papers)
    tools.extend(build_memory_tools(memories, papers))
    return tools


async def run_chat(
    runtime: AgentRuntime,
    *,
    prompt: str | None = None,
    input_fn: InputFunction = input,
    output_fn: OutputFunction = print,
) -> None:
    await runtime.start()
    if prompt is not None:
        if not prompt.strip():
            raise ValueError("One-shot prompt cannot be empty")
        await _run_turn(runtime, prompt, output_fn)
        return

    output_fn("ScholarHarness MiniPy chat. Type /help for commands.")
    while True:
        try:
            raw = input_fn("scholar> ")
        except EOFError:
            return
        command = raw.strip()
        if not command:
            continue
        if command in {"/exit", "/quit"}:
            return
        if command == "/help":
            output_fn(_HELP)
            continue
        if command == "/entries":
            entries = await runtime.get_entries()
            if not entries:
                output_fn("No entries.")
            for entry in entries:
                role = entry.data.get("role", "-")
                output_fn(
                    f"{entry.entry_id} parent={entry.parent_id or '-'} "
                    f"type={entry.type} role={role}"
                )
            continue
        if command == "/compact" or command.startswith("/compact "):
            instructions = command.removeprefix("/compact").strip() or None
            await runtime.compact(instructions)
            output_fn("Context compacted.")
            continue
        if command.startswith("/fork "):
            entry_id = command.removeprefix("/fork ").strip()
            if not entry_id:
                output_fn("Usage: /fork ENTRY_ID")
                continue
            try:
                await runtime.fork(entry_id)
            except KeyError as exc:
                output_fn(f"Error: {exc}")
            else:
                output_fn(f"Forked from {entry_id}.")
            continue
        if command.startswith("/"):
            output_fn("Unknown command. Type /help for commands.")
            continue
        await _run_turn(runtime, raw, output_fn)


async def _run_turn(
    runtime: AgentRuntime,
    prompt: str,
    output_fn: OutputFunction,
) -> None:
    async for event in runtime.stream(prompt):
        if event.type == "message_update":
            output_fn(str(event.data.get("delta") or ""))
        elif event.type == "tool_execution_start":
            output_fn(f"[tool] {event.data.get('toolName')} started")
        elif event.type == "tool_execution_end":
            state = "error" if event.data.get("isError") else "ok"
            output_fn(f"[tool] {event.data.get('toolName')} {state}")
