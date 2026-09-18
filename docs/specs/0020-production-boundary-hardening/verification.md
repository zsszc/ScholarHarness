# Production boundary hardening verification

Status: Verified
Date: 2026-09-18

## Automated verification

```text
uv lock --check: resolved 33 packages
uv run ruff check .: all checks passed
uv run pytest: 147 passed, 2 upstream warnings in 1.73s
python -m compileall -q src: exit 0
uv run scholar-harness pi-smoke: pi_rpc=ok, extension=ok, entry_count=1
authenticated live bridge smoke:
  pi_rpc=ok, extension=ok, tool_service=ok, entry_count=2
  valid provenance token=HTTP 200, missing token=HTTP 401
```

## Acceptance evidence

- **AC-HARDEN-001**:
  `test_bridge_token_authenticates_only_provenance_calls` proves identical missing
  and invalid 401 responses before unknown-tool lookup, valid-token success,
  provenance-free retrieval, and absence of the secret from OpenAPI.
  `test_blank_bridge_token_keeps_development_mode` proves zero-config compatibility.
- **AC-HARDEN-002**:
  `test_pi_extension_hides_and_forwards_memory_provenance` proves the token is read
  from `process.env`, forwarded only through `executionHeaders`, and remains absent
  from model-visible tool parameters.
- **AC-HARDEN-003**:
  `test_repositories_share_sqlite_connection_policy` covers paper, memory, trace,
  evaluation, and chat-session repositories and verifies named rows, foreign keys,
  5000 ms busy timeout, WAL, and normal synchronous mode. The in-memory policy test
  proves its accepted non-WAL fallback.
- **AC-HARDEN-004**:
  `test_busy_timeout_allows_waiting_writer_to_complete` holds an immediate write
  lock, proves the second writer remains pending, releases the lock, and verifies
  the candidate was committed and readable.
- **AC-HARDEN-005**: Lock consistency, lint, all 147 tests, compilation, offline Pi
  smoke, and a live token-enabled API/Pi smoke passed. Direct live requests proved
  valid provenance succeeds and missing credentials fail closed.

## Boundary result

Trusted Pi provenance is now authenticated when production operators configure a
shared secret, without breaking local read-only workflows or zero-config
development. Every durable subsystem uses the same bounded SQLite concurrency and
durability policy, and real lock contention is covered by regression evidence.
