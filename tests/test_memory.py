import sqlite3

import pytest

from scholar_harness.memory.context import MemoryContextPolicy
from scholar_harness.memory.repository import SQLiteMemoryRepository
from scholar_harness.memory.tools import build_memory_tools
from scholar_harness.papers.models import Paper, Passage
from scholar_harness.papers.repository import InMemoryPaperRepository
from scholar_harness.tools.context import ToolExecutionContext


@pytest.fixture
def memory_system(tmp_path):
    papers = InMemoryPaperRepository()
    papers.add(
        Paper(
            id="paper-memory",
            title="Memory Evidence",
            passages=[
                Passage(
                    id="p0001-c0001",
                    page=4,
                    text="Evidence provenance prevents unsupported long-term memories.",
                )
            ],
        )
    )
    memories = SQLiteMemoryRepository(tmp_path / "memory.db")
    return memories, build_memory_tools(memories, papers)


async def test_candidate_requires_verbatim_evidence(memory_system) -> None:
    _memories, tools = memory_system

    with pytest.raises(ValueError, match="quote is not present"):
        await tools.execute(
            "save_memory",
            {
                "content": "Unsupported claim",
                "evidence": [
                    {
                        "paper_id": "paper-memory",
                        "passage_id": "p0001-c0001",
                        "quote": "This quote was invented",
                    }
                ],
            },
        )


async def test_candidate_is_hidden_until_confirmation(memory_system) -> None:
    memories, tools = memory_system
    saved = await tools.execute(
        "save_memory",
        {
            "content": "Evidence provenance helps prevent unsupported memories.",
            "confidence": 0.8,
            "evidence": [
                {
                    "paper_id": "paper-memory",
                    "passage_id": "p0001-c0001",
                    "quote": "Evidence provenance prevents unsupported long-term memories.",
                }
            ],
        },
    )
    memory_id = saved["memory"]["id"]

    assert saved["memory"]["status"] == "candidate"
    assert await tools.execute("recall_memory", {"query": "provenance"}) == {"items": []}

    memories.set_status(memory_id, "confirmed")
    recalled = await tools.execute("recall_memory", {"query": "provenance"})

    assert recalled["items"][0]["id"] == memory_id
    assert recalled["items"][0]["evidence"][0]["page"] == 4


async def test_memory_provenance_comes_only_from_execution_context(memory_system) -> None:
    memories, tools = memory_system
    arguments = {
        "content": "Session provenance is trusted.",
        "scope": "session",
        "evidence": [
            {
                "paper_id": "paper-memory",
                "passage_id": "p0001-c0001",
                "quote": "Evidence provenance prevents unsupported long-term memories.",
            }
        ],
    }
    context = ToolExecutionContext(
        runtime_type="mini-py",
        session_id="session-trusted",
        entry_id="entry-trusted",
        trace_run_id="run-trusted",
        tool_call_id="call-trusted",
    )

    with pytest.raises(ValueError, match="requires trusted runtime context"):
        await tools.execute("save_memory", arguments)
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        await tools.execute(
            "save_memory", {**arguments, "source_session_id": "spoofed"}, context=context
        )

    saved = await tools.execute("save_memory", arguments, context=context)
    memory = memories.get(saved["memory"]["id"])

    assert memory.source_session_id == "session-trusted"
    assert memory.source_entry_id == "entry-trusted"
    assert memory.trace_run_id == "run-trusted"
    assert memory.source_tool_call_id == "call-trusted"
    memories.set_status(memory.id, "confirmed")
    matching = await MemoryContextPolicy(memories).prepare(
        "provenance", "session-trusted"
    )
    other = await MemoryContextPolicy(memories).prepare("provenance", "session-other")
    assert matching.metadata["selected_ids"] == [memory.id]
    assert other.metadata["selected_ids"] == []


def test_memory_status_persists(memory_system) -> None:
    memories, _tools = memory_system
    created = memories.create_candidate(
        content="A candidate",
        kind="semantic",
        scope="global",
        confidence=0.5,
        evidence=[],
    )

    confirmed = memories.set_status(created.id, "confirmed")

    assert confirmed.status == "confirmed"
    assert memories.list(status="candidate") == []
    assert memories.list(status="confirmed")[0].id == created.id


def test_memory_repository_additively_migrates_supersession_column(tmp_path) -> None:
    database = tmp_path / "legacy-memory.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE memories (
                id TEXT PRIMARY KEY, content TEXT NOT NULL, kind TEXT NOT NULL,
                scope TEXT NOT NULL, status TEXT NOT NULL, confidence REAL NOT NULL,
                source_session_id TEXT, source_entry_id TEXT, trace_run_id TEXT,
                source_tool_call_id TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    repository = SQLiteMemoryRepository(database)
    with repository.connect() as connection:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(memories)").fetchall()
        }

    assert "superseded_by_id" in columns


def test_confirmed_memory_can_be_superseded_atomically(memory_system) -> None:
    memories, tools = memory_system
    old = memories.create_candidate(
        content="Old provenance guidance",
        kind="semantic",
        scope="global",
        confidence=0.5,
        evidence=[],
    )
    replacement = memories.create_candidate(
        content="Replacement provenance guidance",
        kind="semantic",
        scope="global",
        confidence=0.9,
        evidence=[],
    )
    memories.set_status(old.id, "confirmed")
    memories.set_status(replacement.id, "confirmed")

    superseded = memories.supersede(old.id, replacement.id)
    repeated = memories.supersede(old.id, replacement.id)

    assert superseded.status == "superseded"
    assert superseded.superseded_by_id == replacement.id
    assert repeated == superseded
    assert superseded.content == "Old provenance guidance"
    assert memories.get(replacement.id).status == "confirmed"
    with pytest.raises(ValueError, match="cannot change status"):
        memories.set_status(old.id, "confirmed")
    with pytest.raises(ValueError, match="record a replacement"):
        memories.set_status(replacement.id, "superseded")


def test_supersession_rejects_invalid_trust_transitions(memory_system) -> None:
    memories, _tools = memory_system

    def add(
        content: str,
        *,
        kind: str = "semantic",
        scope: str = "global",
        owner: str | None = None,
        confirmed: bool = True,
    ):
        item = memories.create_candidate(
            content=content,
            kind=kind,  # type: ignore[arg-type]
            scope=scope,  # type: ignore[arg-type]
            confidence=0.5,
            evidence=[],
            source_session_id=owner,
        )
        return memories.set_status(item.id, "confirmed") if confirmed else item

    source = add("source")
    kind_mismatch = add("kind mismatch", kind="procedural")
    scope_mismatch = add("scope mismatch", scope="session", owner="session-a")
    candidate = add("candidate", confirmed=False)
    owner_a = add("owner a", scope="session", owner="session-a")
    owner_b = add("owner b", scope="session", owner="session-b")

    invalid = [
        (source.id, source.id),
        (source.id, kind_mismatch.id),
        (source.id, scope_mismatch.id),
        (source.id, candidate.id),
        (owner_a.id, owner_b.id),
    ]
    for memory_id, replacement_id in invalid:
        with pytest.raises(ValueError):
            memories.supersede(memory_id, replacement_id)
    assert memories.get(source.id).status == "confirmed"
    assert memories.get(source.id).superseded_by_id is None

    replacement = add("replacement")
    final = add("final")
    memories.supersede(replacement.id, final.id)
    with pytest.raises(ValueError, match="active confirmed"):
        memories.supersede(source.id, replacement.id)


@pytest.mark.asyncio
async def test_recall_excludes_superseded_memory(memory_system) -> None:
    memories, tools = memory_system
    old = memories.create_candidate(
        content="provenance old rule",
        kind="semantic",
        scope="global",
        confidence=0.5,
        evidence=[],
    )
    replacement = memories.create_candidate(
        content="provenance replacement rule",
        kind="semantic",
        scope="global",
        confidence=0.9,
        evidence=[],
    )
    memories.set_status(old.id, "confirmed")
    memories.set_status(replacement.id, "confirmed")
    memories.supersede(old.id, replacement.id)

    recalled = await tools.execute("recall_memory", {"query": "provenance"})

    assert [item["id"] for item in recalled["items"]] == [replacement.id]
