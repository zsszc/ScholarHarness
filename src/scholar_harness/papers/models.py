from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Passage(BaseModel):
    id: str
    text: str
    page: int | None = None
    section: str | None = None


class Paper(BaseModel):
    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    passages: list[Passage] = Field(default_factory=list)


class SearchPapersInput(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)
    mode: Literal["lexical", "hybrid"] = "hybrid"


class ReadPassageInput(BaseModel):
    paper_id: str
    passage_id: str


class ValidateCitationInput(BaseModel):
    paper_id: str
    passage_id: str
    quote: str
