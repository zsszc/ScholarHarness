from __future__ import annotations

import re
from collections.abc import Mapping

from scholar_harness.memory.models import MemoryEvidence, RecallMemoryInput, SaveMemoryInput
from scholar_harness.memory.repository import SQLiteMemoryRepository
from scholar_harness.papers.repository import PaperRepository
from scholar_harness.tools.registry import Tool, ToolRegistry

_SPACE = re.compile(r"\s+")


def build_memory_tools(
    repository: SQLiteMemoryRepository,
    paper_repository: PaperRepository,
) -> ToolRegistry:
    registry = ToolRegistry()

    async def save(arguments: SaveMemoryInput) -> Mapping[str, object]:
        verified: list[MemoryEvidence] = []
        for evidence in arguments.evidence:
            passage = paper_repository.read(evidence.paper_id, evidence.passage_id)
            passage_text = _SPACE.sub(" ", str(passage["text"])).strip().casefold()
            quote = _SPACE.sub(" ", evidence.quote).strip()
            if quote.casefold() not in passage_text:
                raise ValueError(
                    "Evidence quote is not present in passage "
                    f"{evidence.paper_id}/{evidence.passage_id}"
                )
            verified.append(
                evidence.model_copy(update={"quote": quote, "page": passage.get("page")})
            )

        memory = repository.create_candidate(
            content=arguments.content.strip(),
            kind=arguments.kind,
            scope=arguments.scope,
            confidence=arguments.confidence,
            evidence=verified,
            source_session_id=arguments.source_session_id,
            source_entry_id=arguments.source_entry_id,
        )
        return {
            "memory": memory.model_dump(mode="json"),
            "message": "Memory saved as candidate and requires confirmation before recall.",
        }

    async def recall(arguments: RecallMemoryInput) -> Mapping[str, object]:
        return {"items": repository.search_confirmed(arguments.query, arguments.limit)}

    registry.register(
        Tool(
            name="save_memory",
            description=(
                "Save an evidence-backed research memory as an unconfirmed candidate. "
                "The quote must occur verbatim in the referenced paper passage."
            ),
            input_model=SaveMemoryInput,
            handler=save,
        )
    )
    registry.register(
        Tool(
            name="recall_memory",
            description="Search confirmed long-term memories. Candidate memories are excluded.",
            input_model=RecallMemoryInput,
            handler=recall,
        )
    )
    return registry
