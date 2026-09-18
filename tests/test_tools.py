import asyncio

import pytest
from pydantic import BaseModel, ValidationError

from scholar_harness.papers.models import Paper, Passage
from scholar_harness.papers.repository import InMemoryPaperRepository
from scholar_harness.papers.tools import build_paper_tools
from scholar_harness.tools.context import (
    ToolExecutionContext,
    bind_trace_execution,
    current_trace_binding,
)
from scholar_harness.tools.registry import Tool, ToolRegistry


class ContextInput(BaseModel):
    value: str


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


async def test_registry_passes_context_separately_without_changing_schema() -> None:
    registry = ToolRegistry()
    observed = []

    async def contextual(arguments: ContextInput, context: ToolExecutionContext | None):
        observed.append(context)
        return {"value": arguments.value}

    registry.register(
        Tool(
            name="contextual",
            description="Observe trusted context.",
            input_model=ContextInput,
            handler=contextual,
            context_aware=True,
        )
    )
    context = ToolExecutionContext(
        runtime_type="test", session_id="session-1", tool_call_id="call-1"
    )

    result = await registry.execute("contextual", {"value": "ok"}, context=context)
    await registry.execute("contextual", {"value": "none"})

    assert result == {"value": "ok"}
    assert observed == [context, None]
    assert registry.schemas()["contextual"]["properties"] == {
        "value": {"title": "Value", "type": "string"}
    }


async def test_trace_execution_binding_is_task_local_and_resets() -> None:
    async def observe(run_id: str):
        with bind_trace_execution(run_id, "parallel"):
            await asyncio.sleep(0)
            return current_trace_binding()

    first, second = await asyncio.gather(observe("run-1"), observe("run-2"))

    assert first is not None and first.run_id == "run-1"
    assert second is not None and second.run_id == "run-2"
    assert current_trace_binding() is None

    with pytest.raises(RuntimeError, match="failure"):
        with bind_trace_execution("failed-run", "test"):
            raise RuntimeError("failure")
    assert current_trace_binding() is None
