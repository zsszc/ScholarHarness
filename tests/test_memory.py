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
