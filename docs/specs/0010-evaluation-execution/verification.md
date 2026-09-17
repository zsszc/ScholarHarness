# Automated evaluation execution verification

Status: Verified
Date: 2026-09-17

## Automated verification

The repository contract completed successfully:

```text
UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv run ruff check .
All checks passed!

UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv run pytest
82 passed, 2 warnings in 1.01s

python -m compileall -q src
exit 0

UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv run scholar-harness pi-smoke
pi_rpc=ok, extension=ok, entry_count=1

UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache \
  uv run scholar-harness pi-smoke --check-service
pi_rpc=ok, extension=ok, tool_service=ok, entry_count=2
```

The two warnings are upstream Starlette compatibility deprecations from the test
client and do not represent failed behavior.

## Acceptance evidence

- **AC-EVALEXEC-001**: `test_runner_executes_stored_prompt_evaluates_and_cleans_session`
  asserts the persisted case prompt reaches the scripted adapter, four normalized
  events are consumed, the trace completes, and the returned persisted result
  passes.
- **AC-EVALEXEC-002**:
  `test_runner_executes_stored_prompt_evaluates_and_cleans_session` and
  `test_runner_cleans_session_on_evaluation_failure_and_cancellation` assert the
  adapter closes exactly once and the temporary manager is empty after success,
  evaluation failure, and cancellation. The failed-runtime test provides the
  remaining model-failure cleanup evidence.
- **AC-EVALEXEC-003**:
  `test_runner_evaluates_failed_trace_and_redacts_runtime_error` proves a provider
  failure becomes a persisted failed trace, is evaluated against a failed-status
  case, returns `model_error`, and does not copy the private provider URL into the
  execution document.
- **AC-EVALEXEC-004**: `test_evaluation_execution_api_success_and_errors` covers a
  successful `201` envelope, unknown-case `404`, missing-configuration `503`, and
  request-body independence while asserting provider override fields are absent
  from the response.
- **AC-EVALEXEC-005**: `test_eval_run_helper_and_cli_json_output` exercises the
  environment-backed CLI composition contract, structured JSON output, missing
  `OPENAI_MODEL`, and CLI exit code 2 for configuration failure.
- **AC-EVALEXEC-006**: `test_parallel_runner_executions_have_distinct_runs` runs two
  executions concurrently and verifies distinct trace ids, result ids, and external
  session ids followed by complete cleanup.
- **AC-EVALEXEC-007**:
  `test_workbench_evaluation_lab_uses_public_contracts_and_safe_evidence` verifies
  the same-origin execute endpoint, execution control, event-count reporting, and
  preserved manual-run endpoint. Browser QA at `http://127.0.0.1:8765/workbench`
  confirmed both “执行 Case Prompt” and “评测已有 Run” are visible together and
  persisted score history, regression state, and evidence cards still render.
- **AC-EVALEXEC-008**: lock-backed execution, lint, the 82-test suite, compilation,
  Pi RPC smoke, and a live Pi-extension-to-Python-service smoke all passed. Browser
  QA confirmed the responsive workbench loads the implemented execution surface.

## Boundary result

The milestone uses the existing `ChatSessionManager`, `TracingRuntime`, trusted
tool registry, and `TraceEvaluator`; it does not add a second agent loop or expose
provider credentials to HTTP or browser clients. Automated suite scheduling and
durable background jobs remain intentionally deferred.
