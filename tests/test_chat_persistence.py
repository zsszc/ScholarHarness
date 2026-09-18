from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from scholar_harness.chat_persistence import (
    ChatSessionSnapshot,
    SQLiteChatSessionRepository,
)
from scholar_harness.core.events import AgentEvent
from scholar_harness.runtimes.mini_py import MiniPyRuntime
from scholar_harness.runtimes.model import ModelResponse
from scholar_harness.tools.registry import ToolRegistry


class RecordingModel:
    def __init__(self) -> None:
        self.calls = []

    async def complete(self, messages, tools):
        self.calls.append(list(messages))
        return ModelResponse(content="continued")


def entry(
    entry_id: str,
    *,
    parent_id: str | None,
    session_id: str = "session-1",
    role: str = "user",
    content: str = "content",
) -> AgentEvent:
    return AgentEvent(
        type="message",
        session_id=session_id,
        entry_id=entry_id,
        parent_id=parent_id,
        data={"id": entry_id, "role": role, "content": content},
    )


def test_repository_atomically_round_trips_replaces_and_deletes(tmp_path) -> None:
    repository = SQLiteChatSessionRepository(tmp_path / "sessions.db")
    created = datetime.now(UTC) - timedelta(hours=1)
    first = entry("entry-1", parent_id=None, content="first")
    second = entry(
        "entry-2", parent_id="entry-1", role="assistant", content="answer"
    )
    snapshot = ChatSessionSnapshot(
        id="session-1",
        created_at=created,
        active_leaf_id="entry-2",
        last_run_id="run-1",
        entries=[first, second],
    )

    saved = repository.save(snapshot)

    assert saved.id == snapshot.id
    assert saved.created_at == created
    assert saved.active_leaf_id == "entry-2"
    assert saved.last_run_id == "run-1"
    assert saved.entries == [first, second]
    assert repository.list()[0].entry_count == 2

    invalid = snapshot.model_copy(update={"entries": [first, first]})
    with pytest.raises(sqlite3.IntegrityError):
        repository.save(invalid)
    assert repository.get("session-1").entries == [first, second]

    replaced = snapshot.model_copy(
        update={
            "updated_at": datetime.now(UTC),
            "active_leaf_id": "entry-1",
            "last_run_id": "run-2",
            "entries": [first],
        }
    )
    repository.save(replaced)

    assert repository.get("session-1").entries == [first]
    assert repository.list()[0].entry_count == 1
    assert repository.delete("session-1") is True
    assert repository.delete("session-1") is False
    with pytest.raises(KeyError, match="Unknown stored chat session"):
        repository.get("session-1")


async def test_minipy_restores_branch_and_continues_from_active_leaf() -> None:
    root = entry("root", parent_id=None, content="root question")
    answer = entry(
        "answer", parent_id="root", role="assistant", content="root answer"
    )
    sibling = entry("sibling", parent_id="answer", content="inactive sibling")
    model = RecordingModel()
    runtime = MiniPyRuntime(
        model,
        ToolRegistry(),
        session_id="session-1",
        initial_entries=[root, answer, sibling],
        active_leaf_id="answer",
    )
    await runtime.start()

    _ = [event async for event in runtime.stream("continued question")]

    assert [message.content for message in model.calls[0]] == [
        "root question",
        "root answer",
        "continued question",
    ]
    entries = await runtime.get_entries()
    assert entries[:3] == [root, answer, sibling]
    assert entries[3].parent_id == "answer"


@pytest.mark.parametrize(
    ("entries", "leaf", "message"),
    [
        ([entry("one", parent_id=None), entry("one", parent_id=None)], "one", "Duplicate"),
        ([entry("one", parent_id=None, session_id="other")], "one", "different session"),
        ([entry("one", parent_id="missing")], "one", "unknown or forward"),
        ([entry("one", parent_id=None)], None, "requires an active leaf"),
        ([entry("one", parent_id=None)], "missing", "Unknown restored active leaf"),
        (
            [
                AgentEvent(
                    type="message",
                    session_id="session-1",
                    data={"role": "user", "content": "missing id"},
                )
            ],
            None,
            "missing an id",
        ),
    ],
)
def test_minipy_rejects_corrupt_restored_trees(entries, leaf, message) -> None:
    with pytest.raises(ValueError, match=message):
        MiniPyRuntime(
            RecordingModel(),
            ToolRegistry(),
            session_id="session-1",
            initial_entries=entries,
            active_leaf_id=leaf,
        )
