# Trace persistence verification

Verified: 2026-09-17

## Automated evidence

```bash
uv run ruff check .
# All checks passed

uv run pytest
# 25 passed

python -m compileall -q src
# exit 0

uv run scholar-harness pi-smoke
# pi_rpc=ok, extension=ok
```

## Acceptance mapping

- **AC-TRACE-001**: `test_tracing_runtime_completes_and_replays_in_order` proves
  runtime-neutral forwarding, completed status, session binding, and ordered deltas.
- **AC-TRACE-002**: `test_idempotent_entry_ingestion` ingests the same stable Pi
  entry twice and retains one row.
- **AC-TRACE-003**: `test_tool_events_are_correlated` verifies start/end correlation,
  redacted arguments, result, error state, and duration.
- **AC-TRACE-004**:
  `test_redacts_nested_secrets_without_losing_usage_and_bounds_payload` and
  `test_oversized_tool_result_keeps_correlation` verify recursive redaction,
  telemetry preservation, payload bounds, and tool correlation after truncation.
- **AC-TRACE-005**:
  `test_memory_repository_additively_migrates_provenance_columns` verifies migration
  and persistence of trace run and tool-call references.
- **AC-TRACE-006**: `test_trace_read_apis` verifies run, event, and tool endpoints plus
  missing-run handling.
- **AC-TRACE-007**: static analysis, compilation, tests, and real Pi extension loading
  all pass.

## Known limitations

- The application exposes the tracing decorator but does not yet provide a chat API
  that owns a long-running Pi process; the future workbench will compose it there.
- Payload previews are stored inline. External blob storage and retention policies
  remain deferred.
- FastAPI's current test client dependencies emit two upstream deprecation warnings.
