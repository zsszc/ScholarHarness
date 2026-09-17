from __future__ import annotations

from collections.abc import Mapping

from scholar_harness.papers.models import ReadPassageInput, SearchPapersInput
from scholar_harness.papers.repository import PaperRepository
from scholar_harness.tools.registry import Tool, ToolRegistry


def build_paper_tools(repository: PaperRepository) -> ToolRegistry:
    registry = ToolRegistry()

    async def search(arguments: SearchPapersInput) -> Mapping[str, object]:
        return {"items": repository.search(arguments.query, arguments.limit)}

    async def read(arguments: ReadPassageInput) -> Mapping[str, object]:
        return {"item": repository.read(arguments.paper_id, arguments.passage_id)}

    registry.register(
        Tool(
            name="search_papers",
            description="Search the user's paper collection and return citable passages.",
            input_model=SearchPapersInput,
            handler=search,
        )
    )
    registry.register(
        Tool(
            name="read_passage",
            description="Read one exact passage by paper and passage id.",
            input_model=ReadPassageInput,
            handler=read,
        )
    )
    return registry
