import pytest
from pydantic import ValidationError

from scholar_harness.papers.models import Paper, Passage
from scholar_harness.papers.repository import InMemoryPaperRepository
from scholar_harness.papers.tools import build_paper_tools


@pytest.fixture
def tools():
    repository = InMemoryPaperRepository()
    repository.add(
        Paper(
            id="paper-1",
            title="Memory for Research Agents",
            passages=[
                Passage(
                    id="p1",
                    page=7,
                    section="Method",
                    text="Episodic memory retains tool calls and observations.",
                )
            ],
        )
    )
    return build_paper_tools(repository)


async def test_search_returns_citable_coordinates(tools) -> None:
    result = await tools.execute("search_papers", {"query": "episodic memory"})

    assert result["items"][0]["paper_id"] == "paper-1"
    assert result["items"][0]["passage_id"] == "p1"
    assert result["items"][0]["page"] == 7


async def test_tool_arguments_are_validated(tools) -> None:
    with pytest.raises(ValidationError):
        await tools.execute("search_papers", {"query": "", "limit": 0})


async def test_read_passage(tools) -> None:
    result = await tools.execute(
        "read_passage", {"paper_id": "paper-1", "passage_id": "p1"}
    )
    assert result["item"]["section"] == "Method"
