# Evaluation suite workbench verification

Status: Verified
Date: 2026-09-18

## Automated verification

```text
UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv run ruff check .
All checks passed!

UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv run pytest
91 passed, 2 warnings in 1.19s

python -m compileall -q src
exit 0

UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv run scholar-harness pi-smoke
pi_rpc=ok, extension=ok, entry_count=1

UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache \
  uv run scholar-harness pi-smoke --check-service
pi_rpc=ok, extension=ok, tool_service=ok, entry_count=2
```

The two warnings are upstream Starlette test-client deprecations.

## Acceptance evidence

- **AC-SUITEUI-001**:
  `test_workbench_suite_workspace_uses_ordered_public_contracts` verifies Suite
  mode, explicit state regions, semantic controls, safe DOM helpers, and the public
  endpoint strings. Existing self-contained/no-external-assets tests still pass.
- **AC-SUITEUI-002**: Browser QA created “Browser Regression Suite”, added two
  cases, moved the second case to the first position, saved, and reloaded the exact
  order. It then renamed the definition to “Browser Regression Suite Updated”. A
  discovered draft-name reset during reorder was fixed by preserving
  `suiteDraftName`, and the full flow passed after restart.
- **AC-SUITEUI-003**: Browser QA executed the selected suite, observed the pending
  transition, automatic history refresh, selected returned run, and completion text
  `0/2 passed · 2 errors`. The errors are expected because the QA server deliberately
  had no model configuration.
- **AC-SUITEUI-004**: The selected run rendered total/passed/failed/error counts,
  timestamps, suite and suite-run ids, and two ordered item cards containing score,
  event count, safe `configuration_error`, run id, and result id fields.
- **AC-SUITEUI-005**: After renaming the suite definition, the editor and definition
  list displayed the updated name while the historical run detail retained its
  original “Browser Regression Suite” snapshot.
- **AC-SUITEUI-006**: Source tests verify Overview requests suite runs and displays
  backend `passed` counts. Browser QA showed `Suite runs` and `Passing suites`
  alongside the existing metrics; no score or aggregate pass calculation was added.
- **AC-SUITEUI-007**: lint, all 91 tests, compilation, Pi RPC smoke, live extension
  service smoke, desktop browser QA, and a 480×800 responsive browser pass all
  succeeded.

## Browser safety and rendering evidence

All suite definition and history values are created through `make`, which assigns
`textContent`. No persisted field is assigned to `innerHTML`. Desktop and narrow
views kept Cases/Suites navigation, ordering controls, execution, history, aggregate
fields, and item diagnostics keyboard-accessible.
