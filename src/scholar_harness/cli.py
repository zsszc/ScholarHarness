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

from scholar_harness.benchmark import run_benchmark
from scholar_harness.chat import build_chat_tools, run_chat
from scholar_harness.chat_sessions import (
    ChatConfigurationError,
    ChatSessionManager,
    create_default_chat_manager,
)
from scholar_harness.evaluations.models import EvaluationExecution, EvaluationSuiteRun
from scholar_harness.evaluations.reports import (
    suite_run_json,
    suite_run_junit,
    write_text_atomic,
)
from scholar_harness.evaluations.repository import SQLiteEvaluationRepository
from scholar_harness.evaluations.runner import EvaluationExecutionError, EvaluationRunner
from scholar_harness.evaluations.service import EvaluationConflictError, TraceEvaluator
from scholar_harness.evaluations.suites import EvaluationSuiteRunner
from scholar_harness.memory.context import MemoryContextPolicy
from scholar_harness.memory.repository import SQLiteMemoryRepository
from scholar_harness.retrieval_evaluation import (
    load_retrieval_dataset,
    run_retrieval_evaluation,
)
from scholar_harness.runtimes.base import AgentRuntime
from scholar_harness.runtimes.mini_py import MiniPyRuntime
from scholar_harness.runtimes.model import ModelAdapter
from scholar_harness.runtimes.openai_compatible import OpenAICompatibleAdapter
from scholar_harness.runtimes.pi_rpc import PiRpcClient
from scholar_harness.traces.parity import RuntimeParityService
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

    evaluate = commands.add_parser(
        "eval", help="Evaluate an existing trace run against a deterministic case"
    )
    evaluate.add_argument("--case", required=True, dest="case_id")
    evaluate.add_argument("--run", required=True, dest="run_id")
    evaluate.add_argument(
        "--database",
        type=Path,
        default=Path("data/scholar_harness.db"),
    )

    eval_run = commands.add_parser(
        "eval-run", help="Execute and evaluate a case through MiniPy"
    )
    eval_run.add_argument("--case", required=True, dest="case_id")
    eval_run.add_argument(
        "--database",
        type=Path,
        default=Path("data/scholar_harness.db"),
    )

    eval_suite_run = commands.add_parser(
        "eval-suite-run", help="Execute every case in an evaluation suite"
    )
    eval_suite_run.add_argument("--suite", required=True, dest="suite_id")
    eval_suite_run.add_argument(
        "--database", type=Path, default=Path("data/scholar_harness.db")
    )

    eval_gate = commands.add_parser(
        "eval-gate", help="Execute an evaluation suite as a CI quality gate"
    )
    eval_gate.add_argument("--suite", required=True, dest="suite_id")
    eval_gate.add_argument(
        "--database", type=Path, default=Path("data/scholar_harness.db")
    )
    eval_gate.add_argument("--json-output", type=Path)
    eval_gate.add_argument("--junit-output", type=Path)

    parity = commands.add_parser(
        "parity", help="Compare two persisted runtime traces"
    )
    parity.add_argument("--left-run", required=True, dest="left_run_id")
    parity.add_argument("--right-run", required=True, dest="right_run_id")
    parity.add_argument(
        "--database", type=Path, default=Path("data/scholar_harness.db")
    )
    parity.add_argument(
        "--strict-output",
        action="store_true",
        help="Also require exact assembled assistant text",
    )

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

    benchmark = commands.add_parser(
        "benchmark", help="Benchmark offline storage and retrieval paths"
    )
    benchmark.add_argument("--papers", type=_positive_int, default=100)
    benchmark.add_argument("--passages-per-paper", type=_positive_int, default=4)
    benchmark.add_argument("--queries", type=_positive_int, default=100)
    benchmark.add_argument("--trace-events", type=_positive_int, default=1_000)
    benchmark.add_argument("--database", type=Path)
    benchmark.add_argument("--json-output", type=Path)

    retrieval_eval = commands.add_parser(
        "retrieval-eval", help="Run labelled lexical/vector/hybrid retrieval ablation"
    )
    retrieval_eval.add_argument("--dataset", type=Path, required=True)
    retrieval_eval.add_argument("--k", type=_positive_int, default=5)
    retrieval_eval.add_argument("--json-output", type=Path)
    return parser


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


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
        mini_runtime = MiniPyRuntime(
            active_adapter,
            build_chat_tools(config.database),
            context_provider=MemoryContextPolicy(
                SQLiteMemoryRepository(config.database)
            ),
        )
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


async def run_configured_evaluation(
    case_id: str,
    database: Path,
    *,
    environ: Mapping[str, str] | None = None,
    chat_manager: ChatSessionManager | None = None,
) -> EvaluationExecution:
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    sessions = chat_manager or create_default_chat_manager(
        tools=build_chat_tools(database),
        traces=traces,
        environ=environ,
        context_provider=MemoryContextPolicy(SQLiteMemoryRepository(database)),
    )
    runner = EvaluationRunner(
        sessions,
        evaluations,
        TraceEvaluator(traces, evaluations),
    )
    try:
        return await runner.execute(case_id)
    finally:
        await sessions.close_all()


async def run_configured_evaluation_suite(
    suite_id: str,
    database: Path,
    *,
    environ: Mapping[str, str] | None = None,
    chat_manager: ChatSessionManager | None = None,
) -> EvaluationSuiteRun:
    traces = SQLiteTraceRepository(database)
    evaluations = SQLiteEvaluationRepository(database)
    sessions = chat_manager or create_default_chat_manager(
        tools=build_chat_tools(database),
        traces=traces,
        environ=environ,
        context_provider=MemoryContextPolicy(SQLiteMemoryRepository(database)),
    )
    runner = EvaluationRunner(
        sessions, evaluations, TraceEvaluator(traces, evaluations)
    )
    try:
        return await EvaluationSuiteRunner(evaluations, runner).execute(suite_id)
    finally:
        await sessions.close_all()


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

    if args.command == "benchmark":
        report = run_benchmark(
            papers=args.papers,
            passages_per_paper=args.passages_per_paper,
            queries=args.queries,
            trace_events=args.trace_events,
            database=args.database,
        )
        output = report.model_dump_json(indent=2) + "\n"
        if args.json_output is not None:
            write_text_atomic(args.json_output, output)
        print(output, end="")
        return

    if args.command == "retrieval-eval":
        dataset = load_retrieval_dataset(args.dataset)
        report = run_retrieval_evaluation(dataset, k=args.k)
        output = report.model_dump_json(indent=2) + "\n"
        if args.json_output is not None:
            write_text_atomic(args.json_output, output)
        print(output, end="")
        return

    if args.command == "chat":
        try:
            config = resolve_chat_config(args)
        except ValueError as exc:
            parser.error(str(exc))
        asyncio.run(run_configured_chat(config))
        return

    if args.command == "eval":
        evaluator = TraceEvaluator(
            SQLiteTraceRepository(args.database),
            SQLiteEvaluationRepository(args.database),
        )
        try:
            result = evaluator.evaluate(args.case_id, args.run_id)
        except (KeyError, EvaluationConflictError) as exc:
            parser.error(str(exc))
        print(result.model_dump_json(indent=2))
        return

    if args.command == "eval-run":
        try:
            execution = asyncio.run(
                run_configured_evaluation(args.case_id, args.database)
            )
        except (
            ChatConfigurationError,
            EvaluationConflictError,
            EvaluationExecutionError,
            KeyError,
        ) as exc:
            parser.error(str(exc))
        print(execution.model_dump_json(indent=2))
        return

    if args.command == "eval-suite-run":
        try:
            suite_run = asyncio.run(
                run_configured_evaluation_suite(args.suite_id, args.database)
            )
            if suite_run.items and all(
                item.error == "configuration_error" for item in suite_run.items
            ):
                raise ChatConfigurationError("OPENAI_MODEL is required")
        except (ChatConfigurationError, KeyError) as exc:
            parser.error(str(exc))
        print(suite_run.model_dump_json(indent=2))
        return

    if args.command == "eval-gate":
        try:
            suite_run = asyncio.run(
                run_configured_evaluation_suite(args.suite_id, args.database)
            )
            if suite_run.items and all(
                item.error == "configuration_error" for item in suite_run.items
            ):
                raise ChatConfigurationError("OPENAI_MODEL is required")
            json_report = suite_run_json(suite_run)
            if args.json_output is not None:
                write_text_atomic(args.json_output, json_report)
            if args.junit_output is not None:
                write_text_atomic(args.junit_output, suite_run_junit(suite_run))
        except (ChatConfigurationError, KeyError, OSError) as exc:
            parser.error(str(exc))
        print(json_report, end="")
        if not suite_run.passed:
            raise SystemExit(1)
        return

    if args.command == "parity":
        service = RuntimeParityService(SQLiteTraceRepository(args.database))
        try:
            report = service.compare(
                args.left_run_id,
                args.right_run_id,
                strict_output=args.strict_output,
            )
        except KeyError as exc:
            parser.error(str(exc))
        print(report.model_dump_json(indent=2))
        if not report.passed:
            raise SystemExit(1)
        return

    python_status = sys.version.split()[0]
    pi_path = shutil.which("pi")
    print(f"Python: {python_status}")
    print(f"Pi: {pi_path or 'not found (required only for PiRuntime)'}")


if __name__ == "__main__":
    main()
