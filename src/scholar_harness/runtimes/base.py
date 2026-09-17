from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from scholar_harness.core.events import AgentEvent


class AgentRuntime(ABC):
    """Small contract shared by Pi and the planned educational Python runtime."""

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stream(self, prompt: str) -> AsyncIterator[AgentEvent]:
        raise NotImplementedError

    @abstractmethod
    async def abort(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def compact(self, instructions: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    async def fork(self, entry_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_entries(self, since: str | None = None) -> list[AgentEvent]:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
