from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from scholar_harness.core.events import AgentEvent
from scholar_harness.runtimes.base import AgentRuntime


class PiRpcError(RuntimeError):
    """Raised when Pi rejects a command or its RPC stream becomes invalid."""


class PiRpcClient:
    """Async JSONL client for a single `pi --mode rpc` subprocess."""

    def __init__(
        self,
        command: Sequence[str] = ("pi", "--mode", "rpc"),
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._command = tuple(command)
        self._cwd = cwd
        self._env = dict(env) if env is not None else None
        self._process: asyncio.subprocess.Process | None = None
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._stderr_tail: list[str] = []

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def stderr_tail(self) -> list[str]:
        return list(self._stderr_tail)

    async def start(self) -> None:
        if self.running:
            return
        if not self._command:
            raise ValueError("Pi command cannot be empty")

        process_env = os.environ.copy()
        if self._env:
            process_env.update(self._env)

        self._process = await asyncio.create_subprocess_exec(
            *self._command,
            cwd=str(self._cwd) if self._cwd else None,
            env=process_env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader_task = asyncio.create_task(self._read_stdout(), name="pi-rpc-stdout")
        self._stderr_task = asyncio.create_task(self._read_stderr(), name="pi-rpc-stderr")

    async def request(
        self,
        command: Mapping[str, Any],
        *,
        timeout_seconds: float = 30.0,
    ) -> dict[str, Any]:
        if not self.running or self._process is None or self._process.stdin is None:
            raise PiRpcError("Pi RPC process is not running")

        request_id = str(command.get("id") or uuid.uuid4())
        if request_id in self._pending:
            raise PiRpcError(f"Duplicate Pi RPC request id: {request_id}")

        payload = dict(command)
        payload["id"] = request_id
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[request_id] = future

        try:
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
            self._process.stdin.write(encoded.encode("utf-8"))
            await self._process.stdin.drain()
            response = await asyncio.wait_for(future, timeout=timeout_seconds)
        except Exception:
            self._pending.pop(request_id, None)
            raise

        if not response.get("success", False):
            raise PiRpcError(str(response.get("error") or "Pi rejected the RPC command"))
        return response

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            event = await self._events.get()
            if event is None:
                break
            yield event

    async def close(self) -> None:
        process = self._process
        if process is None:
            return

        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=3.0)
            except TimeoutError:
                process.kill()
                await process.wait()

        tasks = [task for task in (self._reader_task, self._stderr_task) if task]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._process = None

    async def _read_stdout(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        error: BaseException | None = None
        try:
            while raw_line := await self._process.stdout.readline():
                line = raw_line.decode("utf-8").rstrip("\r\n")
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise PiRpcError(f"Invalid JSON from Pi RPC: {line[:200]}") from exc

                request_id = message.get("id")
                if message.get("type") == "response" and request_id in self._pending:
                    future = self._pending.pop(request_id)
                    if not future.done():
                        future.set_result(message)
                else:
                    await self._events.put(message)
        except BaseException as exc:
            error = exc
        finally:
            if error is None:
                error = PiRpcError("Pi RPC process closed its stdout")
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(error)
            self._pending.clear()
            await self._events.put(None)

    async def _read_stderr(self) -> None:
        assert self._process is not None and self._process.stderr is not None
        while raw_line := await self._process.stderr.readline():
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            self._stderr_tail.append(line)
            del self._stderr_tail[:-50]


class PiRuntime(AgentRuntime):
    """Runtime adapter that normalizes Pi RPC commands and events."""

    def __init__(self, client: PiRpcClient) -> None:
        self._client = client
        self._session_id = "unknown"

    async def start(self) -> None:
        await self._client.start()
        response = await self._client.request({"type": "get_state"})
        self._session_id = str(response.get("data", {}).get("sessionId") or "unknown")

    async def stream(self, prompt: str) -> AsyncIterator[AgentEvent]:
        await self._client.request({"type": "prompt", "message": prompt})
        async for raw in self._client.events():
            event = self._normalize(raw)
            yield event
            if raw.get("type") == "agent_settled":
                break

    async def abort(self) -> None:
        await self._client.request({"type": "abort"})

    async def compact(self, instructions: str | None = None) -> None:
        command: dict[str, Any] = {"type": "compact"}
        if instructions:
            command["customInstructions"] = instructions
        await self._client.request(command, timeout_seconds=180.0)

    async def fork(self, entry_id: str) -> None:
        await self._client.request({"type": "fork", "entryId": entry_id})

    async def get_entries(self, since: str | None = None) -> list[AgentEvent]:
        command: dict[str, Any] = {"type": "get_entries"}
        if since:
            command["since"] = since
        response = await self._client.request(command)
        entries = response.get("data", {}).get("entries", [])
        return [self._normalize_entry(entry) for entry in entries]

    async def close(self) -> None:
        await self._client.close()

    def _normalize(self, raw: Mapping[str, Any]) -> AgentEvent:
        return AgentEvent(
            type=str(raw.get("type") or "unknown"),
            session_id=self._session_id,
            entry_id=raw.get("entryId") or raw.get("id"),
            parent_id=raw.get("parentId"),
            data=dict(raw),
        )

    def _normalize_entry(self, entry: Mapping[str, Any]) -> AgentEvent:
        return AgentEvent(
            type=str(entry.get("type") or "unknown"),
            session_id=self._session_id,
            entry_id=entry.get("id"),
            parent_id=entry.get("parentId"),
            data=dict(entry),
            timestamp=(
                entry.get("timestamp")
                or AgentEvent.model_fields["timestamp"].default_factory()
            ),
        )
