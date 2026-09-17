# Evaluation suites

Status: Approved
Date: 2026-09-17

## Problem

ScholarHarness can execute one evaluation case end to end, but a regression gate
normally represents several behaviors. Running case ids by hand loses ordering,
aggregate pass/fail status, historical evidence, and a stable command suitable for
CI or an interview demonstration.

## Requirements

- **EVALSUITE-001**: Persist named evaluation suites containing one to 100 unique,
  ordered existing case ids; blank names, duplicate ids, and unknown cases MUST be
  rejected.
- **EVALSUITE-002**: Suite definitions MUST support create, replace, get, and
  deterministic list operations without copying or mutating the referenced cases.
- **EVALSUITE-003**: Executing a suite MUST run every snapshotted case in suite order
  through `EvaluationRunner`, thereby preserving fresh-session isolation, tracing,
  trusted tools, deterministic checks, and cleanup for each item.
- **EVALSUITE-004**: A case execution failure MUST be recorded as a credential-safe
  item error and MUST NOT prevent later suite items from running; request
  cancellation MUST stop the suite and re-raise after the active case cleanup.
- **EVALSUITE-005**: Persist each suite run with an immutable suite-name and ordered
  case snapshot, start/end timestamps, total/passed/failed/error counts, aggregate
  pass state, and one ordered item per snapshotted case.
- **EVALSUITE-006**: A suite run MUST pass only when every item completed without an
  orchestration error and its deterministic evaluation result passed.
- **EVALSUITE-007**: Suite run and item errors MUST expose stable public categories
  and MUST NOT include provider API keys, configured base URLs, or raw model errors.
- **EVALSUITE-008**: Expose HTTP operations to create, replace, get, and list suites;
  synchronously execute a suite; and get or list persisted suite runs.
- **EVALSUITE-009**: Add `scholar-harness eval-suite-run --suite ... --database ...`
  using server-environment provider configuration and emitting the persisted suite
  run as JSON with a non-zero exit code for configuration or lookup failure.
- **EVALSUITE-010**: Concurrent suite executions MUST create independent suite-run
  records and independent per-case runtime sessions while sharing only trusted
  repository and tool services.
- **EVALSUITE-011**: Updating a suite MUST affect future executions only; persisted
  suite runs MUST retain their original name, ordered case ids, and item evidence.

## Decisions

- Suite execution is synchronous and sequential in this milestone. Sequential order
  makes provider load and evidence easy to reason about; durable jobs, concurrency
  controls, schedules, and retries remain deferred.
- A suite stores references to editable cases. The runner snapshots full case
  definitions into each item before execution so later case or suite edits cannot
  rewrite historical intent.
- Aggregate `failed_count` counts completed deterministic results that did not pass;
  `error_count` counts orchestration failures without a result. Both make the suite
  fail.
- Definition deletion and Workbench suite authoring are deferred. API and CLI form
  the CI-grade domain boundary first.

## Acceptance criteria

- **AC-EVALSUITE-001**: Repository tests prove ordered persistence, validation,
  replacement, deterministic listing, and unknown-case rejection. (EVALSUITE-001,
  EVALSUITE-002)
- **AC-EVALSUITE-002**: A scripted multi-case run proves ordered isolated execution,
  correct aggregate counts, result linkage, immutable snapshots, and persistence.
  (EVALSUITE-003, EVALSUITE-005, EVALSUITE-006, EVALSUITE-011)
- **AC-EVALSUITE-003**: Failure and cancellation tests prove safe per-item errors,
  continue-on-error behavior, later-item execution, and active-session cleanup.
  (EVALSUITE-004, EVALSUITE-007)
- **AC-EVALSUITE-004**: API tests cover definition CRUD, execution, run history,
  missing resources, invalid case ids, and missing provider configuration.
  (EVALSUITE-008)
- **AC-EVALSUITE-005**: CLI tests cover structured suite-run JSON and non-zero
  configuration/lookup failures. (EVALSUITE-009)
- **AC-EVALSUITE-006**: Parallel executions produce distinct suite-run, trace,
  result, and external-session ids. (EVALSUITE-010)
- **AC-EVALSUITE-007**: Lock consistency, lint, all tests, compilation, Pi smoke,
  and live HTTP bridge smoke pass.
