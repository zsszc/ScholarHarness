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
    assert result["items"][0]["retrieval_mode"] == "hybrid"


async def test_tool_arguments_are_validated(tools) -> None:
    with pytest.raises(ValidationError):
        await tools.execute("search_papers", {"query": "", "limit": 0})


async def test_read_passage(tools) -> None:
    result = await tools.execute(
        "read_passage", {"paper_id": "paper-1", "passage_id": "p1"}
    )
    assert result["item"]["section"] == "Method"


async def test_search_accepts_explicit_lexical_mode(tools) -> None:
    result = await tools.execute(
        "search_papers", {"query": "episodic", "mode": "lexical"}
    )

    assert result["items"][0]["retrieval_mode"] == "lexical"


async def test_validate_citation_checks_coordinate_and_normalized_quote(tools) -> None:
    valid = await tools.execute(
        "validate_citation",
        {
            "paper_id": "paper-1",
            "passage_id": "p1",
            "quote": "Episodic   memory retains tool calls",
        },
    )
    altered = await tools.execute(
        "validate_citation",
        {"paper_id": "paper-1", "passage_id": "p1", "quote": "invented claim"},
    )
    missing = await tools.execute(
        "validate_citation",
        {"paper_id": "paper-1", "passage_id": "missing", "quote": "evidence"},
    )
    empty = await tools.execute(
        "validate_citation",
        {"paper_id": "paper-1", "passage_id": "p1", "quote": "  "},
    )

    assert valid["valid"] is True
    assert valid["reason"] == "quote_found"
    assert altered == {"valid": False, "reason": "quote_not_found"}
    assert missing == {"valid": False, "reason": "passage_not_found"}
    assert empty == {"valid": False, "reason": "quote_empty"}
