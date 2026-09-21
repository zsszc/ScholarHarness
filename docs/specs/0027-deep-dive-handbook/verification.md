# Verification: standalone deep-dive handbook

Status: Verified
Date: 2026-09-21

## Source and artifact audit

- Audited runtime, Pi extension, tool registry, model adapter, chat gateway,
  session persistence/turn projection, paper ingestion/retrieval, memory trust,
  trace redaction, evaluation, suites, benchmark and CI sources. The handbook
  distinguishes the MiniPy browser graph from the separate Pi RPC path and
  labels model-internal theory as outside this repository.
- Produced one 126,511-byte UTF-8 HTML document with embedded CSS, six accessible
  SVG diagrams, a step-by-step data-flow control and 80 layered interview Q&As.
  External research references are ordinary optional links, not dependencies.
- `tests/test_deep_dive_handbook.py` validates HTML tag balance, unique IDs,
  anchor targets, all relative source links, no external assets/network calls,
  essential claims and credential-pattern absence.
- `tests/handbook_interactions.cjs` runs the inline script against a minimal
  isolated DOM model, proving step changes and question search/filter behavior.
- Node `vm.Script` parses the inline script successfully. No `.env`, database,
  trace, chat contents or provider credentials are embedded.

## Repository gates

- `uv run ruff check .`: passed.
- `uv run pytest`: 165 passed; two dependency deprecation warnings.
- `python -m compileall -q src`: passed.
- `uv run scholar-harness pi-smoke`: passed.

## Browser visual acceptance

- The user opened the standalone `file:` document successfully. For automated
  inspection, the same file was served temporarily from `127.0.0.1`; no artifact
  dependency or permanent service was added.
- At a 1280 x 720 viewport, the document width equalled the viewport width
  (1280 px), with no page-level horizontal overflow. The architecture diagram,
  typography, sticky chapter navigation and source links were visually checked.
- Browser DOM inspection found all six SVG diagrams and all 80 interview
  questions. Selecting step `4 工具` changed the explanation to the expected
  controlled tool-execution text. Searching `RRF` produced four relevant
  questions and the counter `显示 4 / 80 题`; clearing restored the full list.
- Responsive media rules and overflow containment remain covered by the static
  artifact checks; the handbook does not rely on a fixed desktop-only width.

All three acceptance criteria are satisfied.
