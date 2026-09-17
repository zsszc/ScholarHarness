from types import SimpleNamespace

import pytest

from scholar_harness.papers import pdf as pdf_module
from scholar_harness.papers.pdf import PdfIngestor


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakeReader:
    def __init__(self, _stream, strict=False) -> None:
        self.is_encrypted = False
        self.metadata = SimpleNamespace(title="  Test Paper  ", author="Ada")
        self.pages = [
            FakePage("First page evidence.\n\nSecond paragraph."),
            FakePage(""),
        ]


def test_pdf_ingestor_preserves_page_coordinates(monkeypatch) -> None:
    monkeypatch.setattr(pdf_module, "PdfReader", FakeReader)
    result = PdfIngestor().ingest(b"%PDF-fake", filename="fallback.pdf")

    assert result.paper.title == "Test Paper"
    assert result.paper.authors == ["Ada"]
    assert result.paper.passages[0].page == 1
    assert result.paper.passages[0].id == "p0001-c0001"
    assert result.page_count == 2
    assert result.skipped_pages == 1


def test_pdf_chunking_has_bounded_overlap() -> None:
    text = "Sentence with evidence. " * 80
    chunks = PdfIngestor(chunk_size=240, chunk_overlap=40).chunk_text(text)

    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 240 for chunk in chunks)


def test_rejects_non_pdf() -> None:
    with pytest.raises(ValueError, match="not a PDF"):
        PdfIngestor().ingest(b"plain text")
