# Automated evaluation execution

Status: Approved
Date: 2026-09-17

## Problem

Evaluation cases currently grade only runs that a user created elsewhere and then
selected manually. A regression workflow needs one operation that executes the case
prompt through the real agent harness, persists its trace, evaluates that terminal
run, and returns evidence while preserving server-side model and tool boundaries.

## Requirements

- **EVALEXEC-001**: Execute an evaluation case's stored prompt through a fresh
  server-owned `MiniPyRuntime` using the same trusted tool registry and tracing
  repository as browser chat.
- **EVALEXEC-002**: Every execution MUST use an isolated temporary chat session and
  MUST close/remove that session after completion, model failure, evaluation
  failure, or request cancellation.
- **EVALEXEC-003**: A completed agent turn MUST be evaluated against the current
  case definition and return the persisted `EvaluationResult`.
- **EVALEXEC-004**: When the model/runtime fails after trace creation, the terminal
  failed trace MUST still be evaluated so cases can explicitly test failure
  behavior; the response MUST include a credential-safe runtime error.
- **EVALEXEC-005**: The execution response MUST include result, run id, emitted
  event count, runtime error, and start/end timestamps.
- **EVALEXEC-006**: Missing model configuration MUST return `503`; unknown case MUST
  return `404`; a non-terminal or unavailable trace MUST return an explicit conflict
  without leaking provider credentials or URL.
- **EVALEXEC-007**: Expose `POST /evaluations/cases/{case_id}/execute` without
  accepting model, provider URL, API key, prompt override, or tool override fields.
- **EVALEXEC-008**: Add `scholar-harness eval-run --case ... --database ...` using
  the same server-environment configuration and JSON output contract.
- **EVALEXEC-009**: Evaluation Lab MUST add an “Execute Case Prompt” action that
  shows pending state, renders the returned result, refreshes history/overview, and
  keeps the existing “evaluate selected run” workflow.
- **EVALEXEC-010**: Parallel executions MUST receive independent runtime sessions
  and traces while sharing only the trusted repository/tool services.
- **EVALEXEC-011**: Execution metadata and errors MUST NOT expose API keys or the
  configured provider base URL.

## Decisions

- Execution is synchronous at the HTTP boundary for this milestone. The endpoint
  returns when one case run and deterministic evaluation finish. Durable background
  jobs, queues, cancellation endpoints, and schedules are deferred.
- `EvaluationRunner` orchestrates existing components rather than implementing a
  second agent loop. It depends on `ChatSessionManager`, `TraceEvaluator`, and the
  evaluation repository.
- Runtime failure is evidence, not automatically an orchestration failure, when a
  terminal trace exists. The deterministic case decides whether that behavior
  passes.
- Public runtime errors use a stable category. Detailed credential-safe trace errors
  remain inspectable through the existing run endpoint.
- The API request has no body. The persisted case prompt is the sole task input and
  server environment remains the sole provider configuration source.

## Acceptance criteria

- **AC-EVALEXEC-001**: A scripted model/tool-loop test proves the stored prompt is
  executed, normalized events are counted, a terminal trace is persisted, and its
  result passes. (EVALEXEC-001, EVALEXEC-003, EVALEXEC-005)
- **AC-EVALEXEC-002**: Lifecycle tests prove temporary sessions and adapters close
  exactly once on success, runtime failure, evaluation failure, and cancellation.
  (EVALEXEC-002)
- **AC-EVALEXEC-003**: A failing adapter produces a failed trace, safe runtime error,
  and deterministic result instead of losing evidence. (EVALEXEC-004, EVALEXEC-011)
- **AC-EVALEXEC-004**: API tests cover success, missing configuration, missing case,
  request-body independence, and stable response fields. (EVALEXEC-006,
  EVALEXEC-007)
- **AC-EVALEXEC-005**: CLI tests cover JSON output with an injected local compatible
  endpoint and non-zero missing-configuration behavior. (EVALEXEC-008)
- **AC-EVALEXEC-006**: Parallel scripted executions produce distinct session ids,
  run ids, and results. (EVALEXEC-010)
- **AC-EVALEXEC-007**: Workbench source/browser tests execute a stored case prompt,
  show pending/completion state, and select the returned result without breaking
  manual run evaluation. (EVALEXEC-009)
- **AC-EVALEXEC-008**: Lock consistency, lint, all tests, compilation, Pi smoke,
  live HTTP bridge smoke, and browser QA pass.
