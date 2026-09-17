# Deterministic trace evaluations verification

Verified: 2026-09-17

## Automated evidence

```bash
uv lock --check
# Resolved 33 packages; lock is current

uv run ruff check .
# All checks passed

uv run pytest
# 75 passed

python -m compileall -q src
# exit 0

uv run scholar-harness pi-smoke
# pi_rpc=ok, extension=ok

SCHOLAR_HARNESS_URL=http://127.0.0.1:8768 \
  uv run scholar-harness pi-smoke --check-service
# pi_rpc=ok, extension=ok, tool_service=ok

curl -fsS http://127.0.0.1:8768/evaluations/cases
# 200; [] on a clean database
```

## Acceptance mapping

- **AC-EVAL-001**: `test_expectation_validation_rejects_empty_and_contradictory_cases`
  covers the case-language invariants. `test_case_repository_persists_updates_and_order`
  covers create, update, read, list, timestamps, unknown ids, and database reopen.
- **AC-EVAL-002**:
  `test_evaluator_produces_explainable_checks_for_every_expectation` covers terminal
  status, required/forbidden tools, tool-call and duration limits, citation
  validation, case-folded answer substrings, stable check ids, and structured
  evidence. `test_failed_tools_and_missing_answer_reduce_score` covers negative
  checks and failed-tool semantics.
- **AC-EVAL-003**:
  `test_results_are_idempotent_snapshot_cases_and_detect_regressions` verifies
  same-pair replacement, two-run history, previous score, negative delta, regression
  flag, result count, and unchanged snapshots after case editing.
- **AC-EVAL-004**: `test_running_trace_is_rejected_without_result` proves a running
  run produces a domain conflict and no row. API tests cover missing cases/runs.
- **AC-EVAL-005**: `test_evaluation_api_workflow_and_errors` exercises create,
  update, list, get, evaluate, result filtering, result inspection, 404, and 409.
- **AC-EVAL-006**: `test_eval_cli_prints_json_and_rejects_unknown_ids` verifies
  machine-readable successful output and parser exit code 2 for an invalid case.
- **AC-EVAL-007**: lock consistency, lint, all 75 tests, compilation, real Pi RPC,
  live extension-to-service smoke, and a live evaluation catalog request pass.

## Known limitations

- Cases grade existing runs; automated prompt execution and batch scheduling are a
  future orchestration layer.
- Checks are equally weighted deterministic signals. Semantic correctness judges
  and calibrated judge models remain outside this milestone.
- Case deletion is intentionally absent so result provenance cannot be removed
  casually; lifecycle/archival policy will be specified separately.
