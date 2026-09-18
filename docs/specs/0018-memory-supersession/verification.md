# Auditable memory supersession verification

Status: Verified
Date: 2026-09-18

## Automated verification

```text
uv lock --check: resolved 33 packages
uv run ruff check .: all checks passed
uv run pytest: 135 passed, 2 upstream warnings in 1.54s
python -m compileall -q src: exit 0
uv run scholar-harness pi-smoke: pi_rpc=ok, extension=ok, entry_count=1
```

## Acceptance evidence

- **AC-SUPERSEDE-001**:
  `test_confirmed_memory_can_be_superseded_atomically` verifies the retained source
  body, active replacement, relation id, idempotence, and guarded status lifecycle.
  `test_memory_repository_additively_migrates_supersession_column` opens a legacy
  schema and proves additive initialization.
- **AC-SUPERSEDE-002**:
  `test_supersession_rejects_invalid_trust_transitions` covers self replacement,
  inactive target, kind/scope/session-owner mismatch, and a superseded target. It
  also proves failed validation leaves the source active and unlinked.
- **AC-SUPERSEDE-003**:
  `test_memory_supersession_api_reports_transition_conflicts` verifies the explicit
  operation plus stable 404 and 409 mappings.
- **AC-SUPERSEDE-004**:
  `test_recall_excludes_superseded_memory` proves retrieval returns the active
  replacement and not the old record.
- **AC-SUPERSEDE-005**: Lock consistency, lint, all 135 tests, compilation, and Pi
  RPC/extension smoke passed.

## Boundary result

ScholarHarness now has an auditable consolidation primitive: a reviewer can replace
one confirmed memory with another while retaining the complete old record. The
repository enforces trust-domain compatibility and a depth-one acyclic relation;
model tools still cannot mutate trust state.
