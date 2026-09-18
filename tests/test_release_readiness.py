from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import scholar_harness

ROOT = Path(__file__).parents[1]


def test_public_markdown_relative_links_resolve() -> None:
    documents = [
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "docs" / "architecture.md",
        ROOT / "docs" / "benchmark.md",
        ROOT / "docs" / "ci.md",
        ROOT / "docs" / "portfolio.md",
        ROOT / "docs" / "release.md",
    ]
    missing: list[str] = []
    for document in documents:
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", document.read_text()):
            path_text = target.split("#", 1)[0]
            if not path_text or "://" in path_text or path_text.startswith("mailto:"):
                continue
            if not (document.parent / path_text).resolve().exists():
                missing.append(f"{document.relative_to(ROOT)} -> {target}")

    assert missing == []


def test_package_and_api_versions_and_metadata_agree() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    version = metadata["project"]["version"]
    api_source = (ROOT / "src/scholar_harness/api.py").read_text()
    extension = json.loads((ROOT / "pi-extension/package.json").read_text())

    assert version == scholar_harness.__version__ == extension["version"] == "0.1.0"
    assert f'version="{version}"' in api_source
    assert metadata["project"]["urls"]["Repository"].endswith("/zsszc/ScholarHarness")
    assert "Typing :: Typed" in metadata["project"]["classifiers"]
    assert (ROOT / "src/scholar_harness/py.typed").is_file()


def test_mandatory_ci_is_pinned_credential_free_and_complete() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    required_commands = [
        "uv sync --locked --extra dev",
        "uv lock --check",
        "uv run ruff check .",
        "uv run pytest",
        "python -m compileall -q src",
        "uv run scholar-harness pi-smoke",
        "uv run scholar-harness benchmark",
        "uv build",
    ]

    assert "pull_request:" in workflow
    assert "contents: read" in workflow
    assert "${{ secrets." not in workflow
    assert "@earendil-works/pi-coding-agent@0.85.1" in workflow
    for command in required_commands:
        assert command in workflow
    action_refs = re.findall(r"uses:\s*([^\s]+)", workflow)
    assert action_refs
    assert all(re.search(r"@[0-9a-f]{40}$", item) for item in action_refs)
    assert workflow.index("uv build") < workflow.index("actions/upload-artifact@")


def test_release_evidence_is_linked_and_complete() -> None:
    readme = (ROOT / "README.md").read_text()
    changelog = (ROOT / "CHANGELOG.md").read_text()
    release = (ROOT / "docs/release.md").read_text()

    assert "actions/workflows/ci.yml/badge.svg" in readme
    assert "CHANGELOG.md" in readme
    assert "docs/release.md" in readme
    assert "## 0.1.0 — 2026-09-18" in changelog
    for item in (
        "uv build",
        "scholar-harness --help",
        "git status --short --branch",
        "docs/benchmark.json",
        "signed `v0.1.0` tag",
    ):
        assert item in release
