# Evaluation suites verification

Status: Verified
Date: 2026-09-17

## Automated verification

```text
UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv run ruff check .
All checks passed!

UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv run pytest
90 passed, 2 warnings in 1.22s

python -m compileall -q src
exit 0

UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv run scholar-harness pi-smoke
pi_rpc=ok, extension=ok, entry_count=1

UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache \
  uv run scholar-harness pi-smoke --check-service
pi_rpc=ok, extension=ok, tool_service=ok, entry_count=2
```

The two warnings are upstream Starlette test-client deprecations. Live OpenAPI
inspection returned the suite definition, execution, and suite-run history paths.

## Acceptance evidence

- **AC-EVALSUITE-001**:
  `test_suite_repository_validates_order_and_preserves_run_snapshots` proves name
  normalization, ordered membership, replacement, deterministic listing, duplicate
  validation, unknown-case rejection, and transactional rollback.
- **AC-EVALSUITE-002**:
  `test_suite_runner_aggregates_order_and_immutable_snapshots` executes two ordered
  cases through separate adapters, verifies pass/fail counts and result/trace links,
  then edits the suite and confirms the persisted name and case order do not change.
- **AC-EVALSUITE-003**: `test_suite_runner_continues_after_orchestration_error`
  records a safe `execution_error` and still runs the later case;
  `test_suite_runner_cancellation_cleans_active_session` proves cancellation escapes,
  the active adapter closes once, the manager is empty, and no partial terminal
  suite run is persisted. The model-failure test confirms raw provider detail is
  absent while terminal failed trace evidence remains available.
- **AC-EVALSUITE-004**: `test_suite_api_definition_execution_and_history` covers
  create/get/list contracts, synchronous execution, get/list history, missing suite,
  invalid case membership, and a persisted safe configuration-error outcome.
- **AC-EVALSUITE-005**: `test_suite_cli_helper_and_json_output` verifies composed
  execution, structured JSON output, and CLI exit code 2 for configuration failure.
- **AC-EVALSUITE-006**: `test_parallel_suite_runs_are_isolated` proves concurrent
  invocations receive distinct suite runs, traces, results, and external sessions.
- **AC-EVALSUITE-007**: lint, all 90 tests, compilation, Pi RPC smoke, live
  extension-to-service smoke, and OpenAPI route inspection passed.

## Boundary result

Evaluation suites reuse the individual case execution path and never implement a
second runtime loop. Definitions are mutable references for future work; completed
suite runs retain ordered case intent and evidence links. Scheduling, retries,
bounded parallel execution, deletion, and Workbench authoring remain deferred.
