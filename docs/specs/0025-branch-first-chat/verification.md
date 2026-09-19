# Verification: branch-first research chat

Status: Verified
Date: 2026-09-19

## Automated evidence

- `uv run ruff check .`: passed.
- `uv run pytest`: 161 passed; two pre-existing dependency deprecation warnings.
- `python -m compileall -q src`: passed.
- `uv run scholar-harness pi-smoke`: Pi RPC and extension passed.
- `uv run scholar-harness pi-smoke --check-service`: Pi RPC, extension, HTTP
  tool service all passed.
- Embedded Workbench JavaScript parsed with Node's `vm.Script`.
- `tests/test_turn_graph.py` proves linear and sibling paths, tool result ownership,
  active ancestry, retry isolation and preserved old answers.
- Chat API test proves read-only graph projection, branch isolation, absence of
  provider config fields, and unchanged active leaf.
- Workbench source regression covers graph route, explicit fork anchors, safe text
  rendering and MiniPy labeling alongside previous contracts.

## Browser evidence

- Opened the live Workbench and observed connected nodes, selected/active styling
  and visible branch edges.
- Selecting a historical sibling changed the transcript and tool inspector while
  keeping send disabled and the active path unchanged.
- Explicitly continued from that node and sent a harmless test prompt through the
  configured DeepSeek model: a new sibling turn appeared, with the correct ancestor
  path and a completed answer.
- Explicitly retried a prior user turn: active leaf moved to the question, its
  previous answer disappeared from model-context transcript but remained visible
  under "preserved old answer". Reloading restored this state from SQLite.
