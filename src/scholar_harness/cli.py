from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from scholar_harness.chat import build_chat_tools, run_chat
from scholar_harness.runtimes.base import AgentRuntime
from scholar_harness.runtimes.mini_py import MiniPyRuntime
from scholar_harness.runtimes.model import ModelAdapter
from scholar_harness.runtimes.openai_compatible import OpenAICompatibleAdapter
from scholar_harness.runtimes.pi_rpc import PiRpcClient
from scholar_harness.traces.repository import SQLiteTraceRepository
from scholar_harness.traces.runtime import TracingRuntime


@dataclass(frozen=True)
class ChatConfig:
    model: str
    base_url: str
    api_key: str | None
    database: Path
    timeout_seconds: float
    prompt: str | None
    trace: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scholar-harness")
    commands = parser.add_subparsers(dest="command", required=True)

    api = commands.add_parser("api", help="Run the ScholarHarness API")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8765)
    api.add_argument("--reload", action="store_true")

    commands.add_parser("doctor", help="Check local runtime prerequisites")

    chat = commands.add_parser(
        "chat",
        help="Chat through the educational Python runtime",
        allow_abbrev=False,
    )
    chat.add_argument("--model", help="Model id; defaults to OPENAI_MODEL")
    chat.add_argument("--base-url", help="API root; defaults to OPENAI_BASE_URL")
    chat.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="Name of the environment variable containing the API key",
    )
    chat.add_argument(
        "--database",
        type=Path,
        default=Path("data/scholar_harness.db"),
    )
    chat.add_argument("--timeout", type=float, default=60.0, dest="timeout_seconds")
    chat.add_argument("--prompt", help="Run one prompt and exit instead of interactive mode")
    chat.add_argument("--no-trace", action="store_false", dest="trace")
    chat.set_defaults(trace=True)

    smoke = commands.add_parser("pi-smoke", help="Run a real Pi RPC and extension smoke test")
    smoke.add_argument(
        "--extension",
        type=Path,
        default=Path("pi-extension/index.ts"),
        help="Path to the ScholarHarness Pi extension",
    )
    smoke.add_argument(
        "--check-service",
        action="store_true",
        help="Also call /scholar-health; start the API in another terminal first",
    )
    return parser


async def run_pi_smoke(extension: Path, *, check_service: bool = False) -> dict[str, object]:
    client = PiRpcClient(
        (
            "pi",
            "--mode",
            "rpc",
            "--no-session",
            "--offline",
            "--no-approve",
            "--extension",
            str(extension),
        ),
        cwd=Path.cwd(),
    )
    try:
        await client.start()
        state = await client.request({"type": "get_state"})
        commands = await client.request({"type": "get_commands"})
        entries = await client.request({"type": "get_entries"})

        service_status = "not-checked"
        if check_service:
            await client.request({"type": "prompt", "message": "/scholar-health"})
            event_stream = client.events()
            event = await asyncio.wait_for(anext(event_stream), timeout=5.0)
            if (
                event.get("type") != "extension_ui_request"
                or event.get("method") != "notify"
                or event.get("notifyType") != "info"
            ):
                raise RuntimeError(
                    f"ScholarHarness extension could not reach the Python service: {event}"
                )
            service_status = "ok"
    finally:
        await client.close()

    command_names = {
        command["name"] for command in commands.get("data", {}).get("commands", [])
    }
    if "scholar-health" not in command_names:
        raise RuntimeError("Pi started, but the ScholarHarness extension was not loaded")

    return {
        "pi_rpc": "ok",
        "extension": "ok",
        "tool_service": service_status,
        "session_id": state.get("data", {}).get("sessionId"),
        "entry_count": len(entries.get("data", {}).get("entries", [])),
    }


def resolve_chat_config(
    args: argparse.Namespace,
    environ: Mapping[str, str] | None = None,
) -> ChatConfig:
    values = os.environ if environ is None else environ
    model = args.model or values.get("OPENAI_MODEL")
    if not model:
        raise ValueError("Chat model is required: use --model or set OPENAI_MODEL")
    base_url = args.base_url or values.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    if not base_url.strip():
        raise ValueError("Chat base URL cannot be empty")
    if args.timeout_seconds <= 0:
        raise ValueError("Chat timeout must be positive")
    api_key = values.get(args.api_key_env) or None
    return ChatConfig(
        model=model,
        base_url=base_url,
        api_key=api_key,
        database=args.database,
        timeout_seconds=args.timeout_seconds,
        prompt=args.prompt,
        trace=args.trace,
    )


async def run_configured_chat(
    config: ChatConfig,
    *,
    adapter: ModelAdapter | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> str | None:
    active_adapter = adapter or OpenAICompatibleAdapter(
        model=config.model,
        base_url=config.base_url,
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
    )
    runtime: AgentRuntime | None = None
    trace_runtime: TracingRuntime | None = None
    try:
        mini_runtime = MiniPyRuntime(active_adapter, build_chat_tools(config.database))
        runtime = mini_runtime
        if config.trace:
            trace_runtime = TracingRuntime(
                mini_runtime,
                SQLiteTraceRepository(config.database),
                runtime_type="mini-py-openai-compatible",
            )
            runtime = trace_runtime
        await run_chat(
            runtime,
            prompt=config.prompt,
            input_fn=input_fn,
            output_fn=output_fn,
        )
    finally:
        try:
            if runtime is not None:
                await runtime.close()
        finally:
            close_adapter = getattr(active_adapter, "aclose", None)
            if close_adapter is not None:
                await close_adapter()
    return trace_runtime.last_run_id if trace_runtime else None


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "api":
        import uvicorn

        uvicorn.run(
            "scholar_harness.api:create_app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            factory=True,
        )
        return

    if args.command == "pi-smoke":
        extension = args.extension.resolve()
        if not extension.is_file():
            raise FileNotFoundError(f"Pi extension not found: {extension}")
        result = asyncio.run(run_pi_smoke(extension, check_service=args.check_service))
        print(json.dumps(result, indent=2))
        return

    if args.command == "chat":
        try:
            config = resolve_chat_config(args)
        except ValueError as exc:
            parser.error(str(exc))
        asyncio.run(run_configured_chat(config))
        return

    python_status = sys.version.split()[0]
    pi_path = shutil.which("pi")
    print(f"Python: {python_status}")
    print(f"Pi: {pi_path or 'not found (required only for PiRuntime)'}")


if __name__ == "__main__":
    main()
