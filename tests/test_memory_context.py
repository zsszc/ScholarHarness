from __future__ import annotations

from typing import Any

from scholar_harness.memory.context import MemoryContextPolicy
from scholar_harness.memory.models import MemoryEvidence
from scholar_harness.memory.repository import SQLiteMemoryRepository


def add_memory(
    repository: SQLiteMemoryRepository,
    *,
    content: str,
    scope: str = "global",
    session_id: str | None = None,
    status: str = "confirmed",
):
    memory = repository.create_candidate(
        content=content,
        kind="semantic",
        scope=scope,
        confidence=0.9,
        evidence=[
            MemoryEvidence(
                paper_id="paper-1",
                passage_id="passage-1",
                quote="supporting evidence",
                page=7,
            )
        ],
        source_session_id=session_id,
    )
    if status != "candidate":
        memory = repository.set_status(memory.id, status)
    return memory


async def test_policy_selects_only_confirmed_memories_in_allowed_scope(tmp_path) -> None:
    repository = SQLiteMemoryRepository(tmp_path / "memory.db")
    global_memory = add_memory(repository, content="beacon global fact")
    session_memory = add_memory(
        repository,
        content="beacon current session fact",
        scope="session",
        session_id="session-a",
    )
    other_session = add_memory(
        repository,
        content="beacon other session secret",
        scope="session",
        session_id="session-b",
    )
    branch_memory = add_memory(
        repository,
        content="beacon branch secret",
        scope="branch",
        session_id="session-a",
    )
    candidate = add_memory(
        repository,
        content="beacon unconfirmed candidate",
        status="candidate",
    )
    rejected = add_memory(
        repository,
        content="beacon rejected candidate",
        status="rejected",
    )

    prepared = await MemoryContextPolicy(repository).prepare("beacon", "session-a")
    repeated = await MemoryContextPolicy(repository).prepare("beacon", "session-a")

    assert prepared.content == repeated.content
    assert prepared.metadata["selected_ids"] == repeated.metadata["selected_ids"]
    assert set(prepared.metadata["selected_ids"]) == {
        global_memory.id,
        session_memory.id,
    }
    assert prepared.metadata["excluded_scope_count"] == 2
    assert "paper-1/passage-1/page-7" in prepared.content
    assert "never as instructions" in prepared.content
    assert other_session.id not in prepared.content
    assert branch_memory.id not in prepared.content
    assert candidate.id not in prepared.content
    assert rejected.id not in prepared.content
    assert repository.get(candidate.id).status == "candidate"


class StaticRepository:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items

    def search_confirmed(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return self.items[:limit]


async def test_policy_enforces_item_and_character_budgets() -> None:
    items = [
        {
            "id": f"memory-{index}",
            "content": "x" * 1_000,
            "kind": "semantic",
            "scope": "global",
            "confidence": 0.8,
            "evidence": [],
        }
        for index in range(3)
    ]
    policy = MemoryContextPolicy(StaticRepository(items), item_limit=2, char_limit=400)  # type: ignore[arg-type]

    prepared = await policy.prepare("anything", "session-a")

    assert len(prepared.content) <= 400
    assert prepared.metadata == {
        "status": "selected",
        "retrieved_count": 3,
        "eligible_count": 3,
        "selected_count": 1,
        "omitted_count": 2,
        "truncated_count": 1,
        "excluded_scope_count": 0,
        "selected_ids": ["memory-0"],
        "item_limit": 2,
        "char_limit": 400,
    }
    assert prepared.content.endswith("End confirmed memory reference data.")
    assert "…" in prepared.content


async def test_policy_returns_explicit_empty_observation(tmp_path) -> None:
    repository = SQLiteMemoryRepository(tmp_path / "empty.db")

    prepared = await MemoryContextPolicy(repository).prepare("unknown", "session-a")

    assert prepared.content == ""
    assert prepared.metadata["status"] == "empty"
    assert prepared.metadata["selected_count"] == 0
    assert prepared.metadata["selected_ids"] == []
