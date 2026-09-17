from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

from scholar_harness.runtimes.pi_rpc import PiRpcClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scholar-harness")
    commands = parser.add_subparsers(dest="command", required=True)

    api = commands.add_parser("api", help="Run the ScholarHarness API")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8765)
    api.add_argument("--reload", action="store_true")

    commands.add_parser("doctor", help="Check local runtime prerequisites")

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


def main() -> None:
    args = build_parser().parse_args()
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

    python_status = sys.version.split()[0]
    pi_path = shutil.which("pi")
    print(f"Python: {python_status}")
    print(f"Pi: {pi_path or 'not found (required only for PiRuntime)'}")


if __name__ == "__main__":
    main()
