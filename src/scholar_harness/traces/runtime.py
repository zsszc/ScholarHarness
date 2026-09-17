from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from scholar_harness.core.events import AgentEvent
from scholar_harness.runtimes.base import AgentRuntime
from scholar_harness.traces.repository import SQLiteTraceRepository


class TracingRuntime(AgentRuntime):
    """Runtime-neutral decorator that records streams without changing events."""

    def __init__(
        self,
        runtime: AgentRuntime,
        repository: SQLiteTraceRepository,
        *,
        runtime_type: str,
    ) -> None:
        self._runtime = runtime
        self._repository = repository
        self._runtime_type = runtime_type
        self.last_run_id: str | None = None

    async def start(self) -> None:
        await self._runtime.start()

    async def stream(self, prompt: str) -> AsyncIterator[AgentEvent]:
        run = self._repository.create_run(self._runtime_type)
        self.last_run_id = run.id
        settled = False
        try:
            async for event in self._runtime.stream(prompt):
                self._repository.update_run_context(
                    run.id,
                    external_session_id=event.session_id,
                    active_leaf_id=event.entry_id,
                )
                self._repository.append_event(run.id, event)
                if event.type == "agent_settled":
                    settled = True
                yield event
        except (GeneratorExit, asyncio.CancelledError):
            self._repository.finish_run(run.id, "aborted")
            raise
        except Exception as exc:
            self._repository.finish_run(run.id, "failed", error=str(exc))
            raise
        else:
            self._repository.finish_run(
                run.id, "completed" if settled else "aborted"
            )

    async def abort(self) -> None:
        await self._runtime.abort()

    async def compact(self, instructions: str | None = None) -> None:
        await self._runtime.compact(instructions)

    async def fork(self, entry_id: str) -> None:
        await self._runtime.fork(entry_id)

    async def get_entries(self, since: str | None = None) -> list[AgentEvent]:
        entries = await self._runtime.get_entries(since)
        if not entries:
            return entries
        if self.last_run_id is None:
            run = self._repository.create_run(
                f"{self._runtime_type}-sync",
                external_session_id=entries[0].session_id,
            )
            self.last_run_id = run.id
            self._repository.ingest_entries(run.id, entries)
            self._repository.finish_run(run.id, "completed")
        else:
            self._repository.ingest_entries(self.last_run_id, entries)
        return entries

    async def close(self) -> None:
        await self._runtime.close()
