from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from scholar_harness.papers.models import Paper, Passage

_WHITESPACE = re.compile(r"[ \t\f\v]+")
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n+")


@dataclass(frozen=True)
class PdfImportResult:
    paper: Paper
    page_count: int
    skipped_pages: int

    @property
    def passage_count(self) -> int:
        return len(self.paper.passages)


class PdfIngestor:
    """Extract page-aware text chunks from digitally readable PDF files."""

    def __init__(self, *, chunk_size: int = 1_800, chunk_overlap: int = 250) -> None:
        if chunk_size < 200:
            raise ValueError("chunk_size must be at least 200 characters")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be between 0 and chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def ingest(
        self,
        content: bytes,
        *,
        filename: str | None = None,
        paper_id: str | None = None,
        title: str | None = None,
    ) -> PdfImportResult:
        if not content.startswith(b"%PDF-"):
            raise ValueError("Uploaded file is not a PDF")

        try:
            reader = PdfReader(BytesIO(content), strict=False)
        except PyPdfError as exc:
            raise ValueError("PDF structure is invalid or corrupted") from exc
        if reader.is_encrypted:
            try:
                decrypted = reader.decrypt("")
            except PyPdfError as exc:
                raise ValueError("Encrypted PDF requires a password") from exc
            if not decrypted:
                raise ValueError("Encrypted PDF requires a password")

        metadata = reader.metadata
        resolved_id = paper_id or f"pdf-{hashlib.sha256(content).hexdigest()[:16]}"
        resolved_title = (
            title
            or (metadata.title.strip() if metadata and metadata.title else None)
            or (Path(filename).stem if filename else None)
            or resolved_id
        )
        authors = [metadata.author.strip()] if metadata and metadata.author else []

        passages: list[Passage] = []
        skipped_pages = 0
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                extracted_text = page.extract_text() or ""
            except PyPdfError as exc:
                raise ValueError(f"Could not extract text from PDF page {page_number}") from exc
            text = self.normalize_text(extracted_text)
            if not text:
                skipped_pages += 1
                continue
            for chunk_number, chunk in enumerate(self.chunk_text(text), start=1):
                passages.append(
                    Passage(
                        id=f"p{page_number:04d}-c{chunk_number:04d}",
                        page=page_number,
                        text=chunk,
                    )
                )

        if not passages:
            raise ValueError(
                "PDF contains no extractable text; scanned documents need OCR support"
            )

        return PdfImportResult(
            paper=Paper(
                id=resolved_id,
                title=resolved_title,
                authors=authors,
                passages=passages,
            ),
            page_count=len(reader.pages),
            skipped_pages=skipped_pages,
        )

    @staticmethod
    def normalize_text(text: str) -> str:
        paragraphs = []
        for paragraph in _PARAGRAPH_BREAK.split(text.replace("\x00", "")):
            lines = [_WHITESPACE.sub(" ", line).strip() for line in paragraph.splitlines()]
            normalized = " ".join(line for line in lines if line)
            if normalized:
                paragraphs.append(normalized)
        return "\n\n".join(paragraphs)

    def chunk_text(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(text):
            hard_end = min(start + self.chunk_size, len(text))
            end = self._find_boundary(text, start, hard_end)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            next_start = max(end - self.chunk_overlap, start + 1)
            start = self._skip_whitespace(text, next_start)
        return chunks

    @staticmethod
    def _find_boundary(text: str, start: int, hard_end: int) -> int:
        if hard_end >= len(text):
            return len(text)
        minimum = start + int((hard_end - start) * 0.6)
        for marker in ("\n\n", ". ", "。", "! ", "? ", "！", "？", "\n"):
            boundary = text.rfind(marker, minimum, hard_end)
            if boundary != -1:
                return boundary + len(marker)
        return hard_end

    @staticmethod
    def _skip_whitespace(text: str, start: int) -> int:
        while start < len(text) and text[start].isspace():
            start += 1
        return start
