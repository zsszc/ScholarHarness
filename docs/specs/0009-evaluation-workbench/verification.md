# Evaluation workbench verification

Verified: 2026-09-17

## Automated evidence

```bash
uv lock --check
# Resolved 33 packages; lock is current

uv run ruff check .
# All checks passed

uv run pytest
# 76 passed

python -m compileall -q src
# exit 0

uv run scholar-harness pi-smoke
# pi_rpc=ok, extension=ok

SCHOLAR_HARNESS_URL=http://127.0.0.1:8768 \
  uv run scholar-harness pi-smoke --check-service
# pi_rpc=ok, extension=ok, tool_service=ok

curl -fsS http://127.0.0.1:8768/workbench
# 200; complete self-contained HTML document
```

The embedded module also passed a Node syntax parse before browser execution.

## Acceptance mapping

- **AC-EVALUI-001**: `test_workbench_contains_all_areas_and_no_external_assets`
  verifies the sixth route, CSP, and self-contained document.
  `test_workbench_uses_safe_dom_and_explicit_panel_states` verifies safe render
  helpers and loading/empty/error state definitions. Browser QA covers semantic
  labels, focusable controls, desktop layout, and the narrow breakpoint.
- **AC-EVALUI-002**:
  `test_workbench_evaluation_lab_uses_public_contracts_and_safe_evidence` verifies
  case APIs and list normalization. Browser QA created a case with every field,
  submitted duplicate list tokens, observed normalized values after reload, changed
  its name/threshold/rules, and persisted the update.
- **AC-EVALUI-003**: Browser QA listed only terminal runs, selected two different
  browser-chat traces, executed evaluations, and immediately displayed their
  persisted results.
- **AC-EVALUI-004**: The source test verifies expected/observed evidence is passed
  through safe `pre` construction. Browser QA displayed score, threshold, runtime,
  terminal status, previous score, delta, time, run id, and all eight checks with
  expected/observed JSON.
- **AC-EVALUI-005**: Two result rows rendered in chronological history. Tightening
  the duration expectation and re-evaluating produced `25% · -12 pts · regression`
  with a red regression status.
- **AC-EVALUI-006**: Source assertions cover all three new overview metric elements;
  the browser loaded result, passing, and regression counts from the public result
  endpoint.
- **AC-EVALUI-007**: lock consistency, lint, all 76 tests, compilation, real Pi RPC,
  live extension-to-service smoke, HTTP workbench smoke, and browser QA pass.

## Manual browser evidence

- Desktop Evaluation Lab exposed the case list/editor beside execution, history,
  persisted results, and check detail.
- Required-tools and answer inputs normalized duplicate comma-separated tokens on
  the server round trip.
- Result evidence clearly distinguished four passing and four failing checks, then
  surfaced a duration regression after the case rule changed.
- At 390×844, navigation remained accessible and the Evaluation Lab collapsed to a
  readable single column without horizontal overflow.

## Known limitations

- The page evaluates existing terminal runs; it does not schedule prompt execution.
- Case history is bounded to the 500 newest results loaded by the workbench.
- Commas cannot be embedded inside one tool name or required answer substring.
