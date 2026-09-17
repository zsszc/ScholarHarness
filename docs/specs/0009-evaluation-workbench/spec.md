# Evaluation workbench

Status: Approved
Date: 2026-09-17

## Problem

Deterministic trace evaluations are available through HTTP and CLI, but interview
viewers and local users must manually compose JSON and correlate ids. The workbench
should make case authoring, run selection, evidence inspection, and regression
history understandable without hiding the underlying deterministic contracts.

## Requirements

- **EVALUI-001**: Add a sixth Workbench area named Evaluation Lab without external
  scripts, styles, fonts, or a frontend build chain.
- **EVALUI-002**: List evaluation cases and persisted results with explicit loading,
  empty, ready, and error states.
- **EVALUI-003**: Provide a form to create a case with name, prompt, pass threshold,
  required tools, forbidden tools, maximum tool calls, maximum duration, citation
  validation, answer substrings, and terminal status.
- **EVALUI-004**: Selecting a case MUST load its complete definition into the form;
  saving MUST update that case while preserving an explicit “new case” action.
- **EVALUI-005**: Allow selecting a terminal trace run and evaluating it against the
  selected case through the existing API; running traces MUST be visibly disabled
  or rejected with the backend message.
- **EVALUI-006**: Result inspection MUST show score, pass threshold, pass/regression
  state, runtime, run status, previous score, delta, evaluation time, and every
  check's id, message, expected evidence, and observed evidence.
- **EVALUI-007**: Display a chronological score history for the selected case with
  accessible numeric labels and visible regression markers.
- **EVALUI-008**: The Overview MUST add evaluation result, passing result, and
  regression counts without removing existing metrics.
- **EVALUI-009**: All persisted or user-authored evaluation data MUST be rendered
  through DOM text properties rather than interpreted as HTML.
- **EVALUI-010**: Controls MUST expose pending/disabled state during mutations,
  visible focus states, semantic labels, and a responsive single-column layout at
  narrow widths.
- **EVALUI-011**: Comma-separated list inputs MUST trim values, remove blanks and
  duplicates, and submit arrays matching the evaluation API contract.
- **EVALUI-012**: The Evaluation Lab MUST reuse the existing public APIs and MUST
  NOT read SQLite or duplicate scoring logic in the browser.

## Decisions

- The UI is added to the existing self-contained HTML document and follows its
  research-console visual language and safe DOM helpers.
- Comma-separated fields keep case authoring compact and dependency-free. Commas
  inside an individual tool name or required substring are not supported.
- Results are not deleted from the workbench. Provenance lifecycle remains governed
  by the backend's current no-delete policy.
- History uses proportional CSS bars plus text labels rather than a chart library.
- Evaluation is available only for runs already present in `/runs`; the browser
  does not execute case prompts automatically.

## Acceptance criteria

- **AC-EVALUI-001**: Source tests verify the sixth route, self-contained assets,
  responsive layout, semantic controls, and explicit panel states. (EVALUI-001,
  EVALUI-002, EVALUI-010)
- **AC-EVALUI-002**: Source and browser tests create a case containing every field,
  reload it, edit it, and verify normalized list payloads. (EVALUI-003, EVALUI-004,
  EVALUI-011)
- **AC-EVALUI-003**: Browser tests choose a terminal run, execute an evaluation,
  and display the persisted result. (EVALUI-005)
- **AC-EVALUI-004**: A seeded result renders all summary fields, every check, and
  structured expected/observed evidence through safe DOM APIs. (EVALUI-006,
  EVALUI-009)
- **AC-EVALUI-005**: Multiple seeded results render chronological score bars,
  numeric labels, deltas, and regression state. (EVALUI-007)
- **AC-EVALUI-006**: Overview aggregation includes result, passing, and regression
  counts obtained from the evaluation API. (EVALUI-008, EVALUI-012)
- **AC-EVALUI-007**: Lock consistency, lint, all tests, compilation, Pi smoke, live
  HTTP bridge smoke, and desktop/narrow browser QA pass.
