# Evaluation suite workbench

Status: Verified
Date: 2026-09-18

## Problem

Evaluation suites provide a CI-grade API and CLI, but the Workbench still exposes
only individual cases. A viewer cannot see how cases form a regression gate, run a
suite, or inspect aggregate and per-case outcomes without manually using ids and
JSON. The UI should make that orchestration visible while retaining the backend as
the sole execution and scoring authority.

## Requirements

- **SUITEUI-001**: Extend Evaluation Lab with distinct Case and Suite workspaces
  without adding external assets or a frontend build chain.
- **SUITEUI-002**: List suite definitions and persisted suite runs with explicit
  loading, empty, ready, and error states.
- **SUITEUI-003**: Provide a suite editor for name and one to 100 unique cases; the
  editor MUST make membership order visible and allow add, remove, move-up, and
  move-down operations.
- **SUITEUI-004**: Selecting a suite MUST restore its ordered definition; saving
  MUST create or replace through the public suite APIs while preserving an explicit
  “new suite” action.
- **SUITEUI-005**: Executing a selected suite MUST show pending/disabled state, call
  the no-body execution endpoint, refresh suite history and Overview, and select the
  returned suite run.
- **SUITEUI-006**: Suite-run detail MUST show aggregate pass state, suite snapshot
  name, total/passed/failed/error counts, start/end times, and ordered item rows.
- **SUITEUI-007**: Each item row MUST show case snapshot name, position, pass/error
  state, score, event count, runtime error, public orchestration error, run id, and
  result id without exposing raw provider details.
- **SUITEUI-008**: Suite history MUST show chronological aggregate outcomes with
  accessible count labels and preserve historical snapshots after definition edits.
- **SUITEUI-009**: Overview MUST display suite-run and passing-suite-run counts from
  the public suite-run API without removing existing metrics.
- **SUITEUI-010**: All suite names, prompts, errors, identifiers, and evidence MUST
  be rendered through DOM text properties rather than interpreted as HTML.
- **SUITEUI-011**: The suite interface MUST retain visible focus states, semantic
  controls, keyboard-operable ordering actions, and a single-column narrow layout.
- **SUITEUI-012**: The browser MUST reuse suite HTTP contracts and MUST NOT read
  SQLite, execute models directly, aggregate pass state, or duplicate scoring rules.

## Decisions

- Case and Suite modes share the Evaluation Lab route and use local toggle buttons;
  this avoids adding another top-level navigation destination.
- An available-case selector plus ordered membership list is clearer than a native
  multi-select because native selection does not communicate execution order.
- The backend-provided aggregate and item fields are rendered verbatim. The browser
  derives only presentation labels and never recomputes whether a suite passed.
- Definition/run deletion and execution cancellation controls remain deferred.

## Acceptance criteria

- **AC-SUITEUI-001**: Source tests verify self-contained Case/Suite modes, explicit
  states, responsive behavior, safe DOM rendering, and semantic controls.
  (SUITEUI-001, SUITEUI-002, SUITEUI-010, SUITEUI-011)
- **AC-SUITEUI-002**: Source/browser tests create and edit a suite, add/remove and
  reorder cases, reload the definition, and verify the ordered payload.
  (SUITEUI-003, SUITEUI-004)
- **AC-SUITEUI-003**: Browser tests execute a suite, observe pending/completion
  state, refresh Overview/history, and select the returned run. (SUITEUI-005)
- **AC-SUITEUI-004**: A seeded suite run renders all aggregate fields and ordered
  item metadata through safe DOM APIs. (SUITEUI-006, SUITEUI-007, SUITEUI-010)
- **AC-SUITEUI-005**: Multiple seeded runs render chronological history and retain
  their original suite snapshots after a definition edit. (SUITEUI-008)
- **AC-SUITEUI-006**: Overview suite metrics come from `/evaluations/suite-runs`
  and no browser-side score or pass calculation is introduced. (SUITEUI-009,
  SUITEUI-012)
- **AC-SUITEUI-007**: Lock consistency, lint, all tests, compilation, Pi smoke, live
  HTTP bridge smoke, and desktop/narrow browser QA pass.
