# Durable browser sessions verification

Status: Verified
Date: 2026-09-18

## Automated verification

```text
uv lock --check: resolved 33 packages
uv run ruff check .: all checks passed
uv run pytest: 130 passed, 2 upstream warnings in 1.59s
python -m compileall -q src: exit 0
uv run scholar-harness pi-smoke: pi_rpc=ok, extension=ok, entry_count=1
uv run scholar-harness pi-smoke --check-service:
  pi_rpc=ok, extension=ok, tool_service=ok, entry_count=2
```

## Acceptance evidence

- **AC-SESSION-001**:
  `test_repository_atomically_round_trips_replaces_and_deletes` verifies exact
  entry/timestamp metadata, deterministic positions, full replacement, cascade
  deletion, and rollback preserving the prior snapshot after an invalid insert.
- **AC-SESSION-002**:
  `test_minipy_restores_branch_and_continues_from_active_leaf` proves inactive
  siblings remain stored while the next user entry follows the saved leaf. The
  parameterized corruption test covers duplicate/missing ids, foreign sessions,
  dangling/forward parents, missing active leaf, and unknown active leaf.
- **AC-SESSION-003**:
  `test_manager_restores_persisted_session_lazily_and_continues` proves no adapter on
  list, creation/turn/fork/compact/close checkpoints, original metadata and run link,
  lazy hydration, compacted continuation, and shutdown retention.
- **AC-SESSION-004**: Provider-unavailable tests prove list/delete without hydration
  plus stable REST/WebSocket configuration errors. The corrupt-session test proves
  adapter cleanup, stable restore error, and snapshot retention.
- **AC-SESSION-005**:
  `test_websocket_session_survives_application_restart_and_deletion` runs two FastAPI
  lifespans over one database, restores entries, continues with prior model context,
  and removes the durable row only after explicit DELETE.
- **AC-SESSION-006**: All existing evaluation managers remain repository-free and
  ephemeral; the full suite confirms unchanged evaluation cleanup and secret-free
  chat metadata.
- **AC-SESSION-007**: Lock consistency, lint, all 130 tests, compilation, both Pi
  smokes, live HTTP bridge, and browser QA passed. Browser QA discovered
  `qa-durable-session-0017` after a process restart and displayed the stable missing
  provider error while retaining the session id.

## Boundary result

Browser MiniPy sessions are now durable independently of live model adapters.
Atomic SQLite snapshots preserve the complete append-only tree and active branch;
managers list them cheaply, validate them before lazy hydration, retain them across
shutdown, and delete them only through the explicit session lifecycle operation.
