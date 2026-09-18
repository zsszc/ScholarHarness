# Runtime parity reports

Status: Verified
Date: 2026-09-18

## Problem

Pi and MiniPy implement the same `AgentRuntime` interface, but interface parity does
not prove behavioral parity. The project needs a deterministic, model-independent
way to compare two persisted runs and explain whether their lifecycle, tool use,
context behavior, and response shape agree without comparing volatile ids or timing.

## Requirements

- **PARITY-001**: Project any persisted trace run into a runtime-neutral behavior
  snapshot containing runtime type, terminal status, ordered lifecycle event types,
  ordered tool outcomes, context-selection statuses, and assembled assistant text.
- **PARITY-002**: Projection MUST ignore run/session/entry/tool-call ids, timestamps,
  duration, and provider-specific payload fields.
- **PARITY-003**: Consecutive message deltas MUST be assembled in trace order;
  output presence MUST be comparable independently of exact text.
- **PARITY-004**: A parity report MUST provide named checks for terminal status,
  lifecycle sequence, tool sequence/outcomes, context statuses, and output presence.
- **PARITY-005**: Exact assistant output MUST be an optional strict check and MUST
  not be required by default because model text is nondeterministic.
- **PARITY-006**: A report MUST include both run ids/runtime types, every check's
  left/right observation, an aggregate `passed` result, and a stable schema version.
- **PARITY-007**: The CLI MUST compare two existing trace run ids, emit JSON to
  stdout, return exit 0 on parity, exit 1 on mismatch, and surface unknown runs as
  argument errors.
- **PARITY-008**: Projection MUST be read-only and MUST not expose assistant text in
  per-check observations unless strict output comparison is explicitly requested.

## Acceptance criteria

- **AC-PARITY-001**: Projection tests prove stable semantic snapshots across
  different ids, timestamps, runtime types, and provider-only payload fields.
  (PARITY-001..003, 008)
- **AC-PARITY-002**: Report tests prove default and strict success/failure behavior
  with actionable named observations. (PARITY-004..006, 008)
- **AC-PARITY-003**: CLI tests prove JSON output, exit codes, strict mode, and unknown
  run handling. (PARITY-007)
- **AC-PARITY-004**: A Pi-shaped and MiniPy-shaped fixture pair passes the default
  semantic contract while a deliberate tool mismatch fails.
- **AC-PARITY-005**: Lock consistency, lint, all tests, compilation, and Pi smoke
  pass.

## Non-goals

- This milestone does not claim that two different model providers generate the
  same prose or token usage.
- It does not execute models itself; existing traced runs remain the replay boundary.
