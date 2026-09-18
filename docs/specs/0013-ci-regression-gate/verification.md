# CI regression gate verification

Status: Verified
Date: 2026-09-18

## Automated verification

```text
UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv run ruff check .
All checks passed!

UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv run pytest
97 passed, 2 warnings in 1.24s

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

- **AC-CIGATE-001**: `test_eval_gate_cli_exit_codes_and_artifacts` injects passing
  and failing completed suite runs, verifies parseable persisted JSON on stdout,
  and observes exit codes 0 and 1.
- **AC-CIGATE-002**:
  `test_eval_gate_configuration_failure_is_exit_two_without_artifacts` covers
  configuration and unknown-suite failures, exit code 2, empty stdout, and absent
  artifacts.
- **AC-CIGATE-003**: `test_json_report_parity_and_atomic_replacement` verifies exact
  stdout/report JSON parity, UTF-8 output, nested parent creation, replacement, and
  no leftover temporary file. The writer failure test proves an old target remains
  intact and the temporary file is removed when replacement fails.
- **AC-CIGATE-004**:
  `test_junit_report_maps_order_failures_errors_and_escapes_xml` parses the generated
  XML and verifies aggregate counts/timing, ordered names, pass/failure/error mapping,
  identifiers, and escaping for `<`, `>`, `&`, and quotes.
- **AC-CIGATE-005**: The existing `test_suite_cli_helper_and_json_output` and full
  evaluation-suite suite continue to pass without changing `eval-suite-run`.
- **AC-CIGATE-006**:
  `test_ci_documentation_preserves_artifacts_then_enforces_gate` verifies the local
  command, JSON/JUnit paths, `continue-on-error`, unconditional artifact publication,
  and final gate enforcement. The workflow follows the current official setup-uv
  and upload-artifact usage checked on 2026-09-18.
- **AC-CIGATE-007**: lint, all 97 tests, compilation, Pi RPC smoke, and live
  extension-to-service smoke passed.

## Boundary result

The report layer is a pure projection of `EvaluationSuiteRun`. It neither calls the
model nor recalculates aggregate pass state. Operational failures create no report;
completed quality failures produce evidence before returning exit 1.
