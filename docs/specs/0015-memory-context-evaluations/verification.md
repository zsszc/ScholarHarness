# Memory context evaluations verification

Status: Verified
Date: 2026-09-18

## Automated verification

```text
uv lock --check: resolved 33 packages
uv run ruff check .: all checks passed
uv run pytest: 111 passed, 2 upstream warnings in 1.31s
python -m compileall -q src: exit 0
uv run scholar-harness pi-smoke: pi_rpc=ok, extension=ok, entry_count=1
uv run scholar-harness pi-smoke --check-service:
  pi_rpc=ok, extension=ok, tool_service=ok, entry_count=2
```

## Acceptance evidence

- **AC-MEMEVAL-001**: expectation validation tests prove list normalization,
  deduplication, overlap rejection, bounds, defaults, and repository snapshots.
- **AC-MEMEVAL-002**:
  `test_evaluator_checks_persisted_memory_context_without_content` proves all four
  stable checks, deduplicated selection semantics, reported-count diagnostics, and
  passing evidence.
- **AC-MEMEVAL-003**: missing/malformed parameterized coverage and
  `test_duplicate_context_events_are_invalid_evidence` prove safe reasons, failed
  checks, empty invalid selections, and absence of context bodies in result JSON.
- **AC-MEMEVAL-004**: The full existing evaluation, suite, report, API, and CI test
  suite remains green; cases without memory fields preserve their prior check sets.
- **AC-MEMEVAL-005**: Workbench source assertions cover all four fields plus restore
  and submit paths. Browser QA visibly confirmed Required/Forbidden memory ids,
  Context status, and maximum context items in the loaded Evaluation Lab editor.
- **AC-MEMEVAL-006**: Lock consistency, lint, all 111 tests, compilation, both Pi
  smokes, live HTTP bridge, and browser QA passed.

## Boundary result

Evaluation cases can now gate the memory decision that actually influenced a run.
The evaluator consumes persisted normalized events only, treats ambiguity as failed
evidence, and projects identifiers and counts without copying memory content into
results, suite history, JSON, JUnit, or CI logs.
