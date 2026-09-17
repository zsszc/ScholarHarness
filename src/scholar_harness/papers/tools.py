from __future__ import annotations

from collections.abc import Mapping

from scholar_harness.papers.models import (
    ReadPassageInput,
    SearchPapersInput,
    ValidateCitationInput,
)
from scholar_harness.papers.repository import PaperRepository
from scholar_harness.tools.registry import Tool, ToolRegistry


def build_paper_tools(repository: PaperRepository) -> ToolRegistry:
    registry = ToolRegistry()

    async def search(arguments: SearchPapersInput) -> Mapping[str, object]:
        return {
            "items": repository.search(
                arguments.query,
                arguments.limit,
                mode=arguments.mode,
            )
        }

    async def read(arguments: ReadPassageInput) -> Mapping[str, object]:
        return {"item": repository.read(arguments.paper_id, arguments.passage_id)}

    async def validate(arguments: ValidateCitationInput) -> Mapping[str, object]:
        normalized_quote = " ".join(arguments.quote.split())
        if not normalized_quote:
            return {"valid": False, "reason": "quote_empty"}
        try:
            passage = repository.read(arguments.paper_id, arguments.passage_id)
        except KeyError:
            return {"valid": False, "reason": "passage_not_found"}
        normalized_passage = " ".join(str(passage["text"]).split())
        if normalized_quote not in normalized_passage:
            return {"valid": False, "reason": "quote_not_found"}
        return {
            "valid": True,
            "reason": "quote_found",
            "paper_id": arguments.paper_id,
            "passage_id": arguments.passage_id,
        }

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
    registry.register(
        Tool(
            name="validate_citation",
            description="Verify that a direct quote occurs at an exact paper coordinate.",
            input_model=ValidateCitationInput,
            handler=validate,
        )
    )
    return registry
