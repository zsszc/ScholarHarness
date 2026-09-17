# Deterministic trace evaluations

Status: Approved
Date: 2026-09-17

## Problem

ScholarHarness persists inspectable runs, events, and tool executions, but cannot
turn them into repeatable quality signals. Agent behavior therefore has no durable
acceptance contract, regression baseline, or machine-readable evidence for
interview demonstrations and future CI.

## Requirements

- **EVAL-001**: Persist named evaluation cases with a prompt, deterministic
  expectations, pass threshold, creation time, and update time.
- **EVAL-002**: Expectations MUST support required tools, forbidden tools, maximum
  tool calls, maximum duration, required successful citation validation, required
  answer substrings, and required terminal status.
- **EVAL-003**: Case validation MUST require at least one expectation, reject
  contradictory required/forbidden tools, and enforce bounded names, prompts,
  lists, durations, and thresholds.
- **EVAL-004**: Evaluate any completed trace run against a selected case without
  invoking a model or mutating the run.
- **EVAL-005**: Every expectation MUST produce an individual check with stable id,
  pass/fail state, readable message, and structured observed/expected evidence.
- **EVAL-006**: An evaluation result MUST persist an immutable snapshot of the case
  name and expectations, its checks, normalized score, pass state, runtime type,
  run status, and evaluation timestamp.
- **EVAL-007**: Re-evaluating the same case and run MUST replace the prior result so
  retries are idempotent; evaluations of different case/run pairs remain separate.
- **EVAL-008**: Results MUST report the score delta against the immediately previous
  evaluated run for that case and flag a regression when the new score is lower.
- **EVAL-009**: Evaluation MUST reject running traces and unknown cases/runs with
  explicit errors.
- **EVAL-010**: Expose HTTP endpoints to create/update, list, and inspect cases;
  evaluate a run; and list or inspect evaluation results.
- **EVAL-011**: The CLI MUST evaluate an existing run by case id using the configured
  SQLite database and emit JSON suitable for CI.
- **EVAL-012**: Trace-derived answer text MUST use ordered `message_update` deltas;
  tool checks MUST use correlated tool executions and distinguish tool failures.

## Decisions

- This milestone implements deterministic, offline trace grading rather than an
  LLM-as-judge. The checks are explainable, cheap, stable, and safe for regression
  gates. Semantic judges can be added behind a separate evaluator interface later.
- Cases describe desired behavior but do not execute prompts in this milestone.
  Runs may originate from Pi, CLI MiniPy, browser Chat, or future runtimes.
- The repository is SQLite-backed and shares the existing application database.
- Case updates affect future evaluations only. Persisted results retain their case
  snapshot so past evidence remains interpretable.
- Scores are the fraction of passed checks. A result passes when its score meets the
  case threshold; no hidden weighting is applied.
- Duration uses run start/end timestamps. A missing end time is rejected because
  only terminal runs may be evaluated.

## Acceptance criteria

- **AC-EVAL-001**: Repository tests prove case validation, create/update/list/get,
  persistence, deterministic ordering, and independent database reopen. (EVAL-001,
  EVAL-003)
- **AC-EVAL-002**: Evaluator tests cover every expectation type, ordered answer
  reconstruction, failed tools, evidence payloads, scores, and pass thresholds.
  (EVAL-002, EVAL-004..006, EVAL-012)
- **AC-EVAL-003**: Tests prove same-pair replacement, cross-run history, score
  deltas, regression flags, and immutable case snapshots. (EVAL-006..008)
- **AC-EVAL-004**: Running and unknown traces/cases return explicit domain and HTTP
  errors without partially persisted results. (EVAL-009)
- **AC-EVAL-005**: API tests cover the complete case and result workflow with stable
  JSON contracts. (EVAL-010)
- **AC-EVAL-006**: CLI tests prove successful JSON output and non-zero failure for
  invalid identifiers or running traces. (EVAL-011)
- **AC-EVAL-007**: Lock consistency, lint, all tests, compilation, Pi smoke, and live
  HTTP bridge smoke pass.
