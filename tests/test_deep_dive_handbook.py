import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "docs" / "scholar-harness-deep-dive.html"
RESUME_DESCRIPTION = ROOT / "docs" / "resume-project-description.zh-CN.md"


class HandbookParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.links: list[str] = []
        self.headings: list[str] = []
        self.question_count = 0
        self.diagram_count = 0
        self.external_assets: list[str] = []
        self.open_tags: list[str] = []
        self.tag_errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {"br", "hr", "img", "input", "link", "meta"}:
            self.open_tags.append(tag)
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        if tag == "details" and "qa" in (values.get("class") or "").split():
            self.question_count += 1
        if tag == "svg" and values.get("role") == "img":
            self.diagram_count += 1
        if tag in {"script", "img", "image", "iframe", "audio", "video", "source"}:
            asset = values.get("src") or values.get("href")
            if asset:
                self.external_assets.append(asset)
        if tag == "link" and values.get("rel") == "stylesheet":
            self.external_assets.append(values.get("href") or "")

    def handle_endtag(self, tag: str) -> None:
        if not self.open_tags or self.open_tags[-1] != tag:
            self.tag_errors.append(f"Unexpected closing tag: {tag}")
        else:
            self.open_tags.pop()


def test_deep_dive_handbook_is_offline_and_source_linked() -> None:
    html = DOCUMENT.read_text(encoding="utf-8")
    parser = HandbookParser()
    parser.feed(html)

    assert html.startswith("<!doctype html>")
    assert "<html lang=\"zh-CN\">" in html
    assert "</html>" in html
    assert parser.question_count >= 80
    assert parser.diagram_count >= 7
    assert len(parser.ids) == len(set(parser.ids))
    assert not parser.open_tags
    assert not parser.tag_errors
    assert not parser.external_assets
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "WebSocket(" not in html
    assert re.search(r"\bsk-[A-Za-z0-9_-]{16,}\b", html) is None
    assert "@import" not in html
    assert re.search(r"url\((?!#)", html) is None

    local_links = [link for link in parser.links if not link.startswith(("#", "https://"))]
    assert local_links
    assert all((DOCUMENT.parent / unquote(link)).exists() for link in local_links)
    for anchor in parser.links:
        if anchor.startswith("#"):
            assert anchor[1:] in parser.ids


def test_deep_dive_handbook_has_required_explanations() -> None:
    html = DOCUMENT.read_text(encoding="utf-8")
    for text in (
        "MiniPy 的单会话分支图",
        "不是 Pi 原生",
        "非神经语义检索",
        "candidate",
        "confirmed",
        "TracingRuntime",
        "RRF(d)",
        "context_injection",
        "不调用第二个模型",
        "LLM-as-a-judge",
        "Transformer",
        "模型位置",
        "Recall@5 从 50% 提升至 95%",
        "Hybrid 相比 Vector-only",
        "RRF 单独带来 45pp",
        "retrieval-evaluation.json",
        "resume-project-description.zh-CN.md",
    ):
        assert text in html


def test_resume_description_is_pi_led_and_evidence_bounded() -> None:
    content = RESUME_DESCRIPTION.read_text(encoding="utf-8")

    assert "基于 Pi 的个人文献知识库与研究 Agent Harness" in content
    assert "Python Reference Runtime" in content
    assert "Recall@5 从 50% 提升至 95%" in content
    assert "20 条标注查询的受控离线" in content
    assert "不是公开论文检索基准" in content
    assert "RRF 单独带来 45pp" in content


def test_deep_dive_handbook_interactions_without_browser() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable")
    result = subprocess.run(
        [node, str(ROOT / "tests" / "handbook_interactions.cjs")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
