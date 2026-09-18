# Trusted tool execution context

Status: Verified
Date: 2026-09-18

## Problem

`save_memory` currently accepts session, entry, trace-run, and tool-call provenance
as model-authored arguments. Those values are not trustworthy, session-scoped
memory cannot reliably bind itself to the active runtime, and provider-visible tool
schemas expose harness metadata that the model should never manage.

## Requirements

- **TOOLCTX-001**: Define a provider-neutral `ToolExecutionContext` carrying runtime
  type plus optional session, entry, trace-run, and tool-call ids.
- **TOOLCTX-002**: `ToolRegistry` MUST support context-aware handlers without changing
  legacy handler schemas or invocation behavior.
- **TOOLCTX-003**: MiniPy MUST supply active session id, assistant entry id, and tool
  call id for every tool execution; a tracing wrapper MUST additionally bind its
  run id without global cross-talk between concurrent tasks.
- **TOOLCTX-004**: The Pi extension MUST remove provenance from the model-visible
  `save_memory` schema and forward Pi's actual session, current leaf, and tool-call
  ids through the HTTP execution boundary.
- **TOOLCTX-005**: The Python `save_memory` schema MUST remove model-authored
  provenance fields and persist only execution-context provenance.
- **TOOLCTX-006**: A direct context-free call MAY save a global candidate with null
  provenance, but session/branch candidates MUST require runtime context.
- **TOOLCTX-007**: Client JSON arguments MUST NOT override execution context, and
  unknown provenance arguments MUST be rejected by validation.
- **TOOLCTX-008**: Context MUST remain request/task scoped under parallel turns and
  MUST be cleared after success, failure, cancellation, and runtime close.
- **TOOLCTX-009**: Tool start/end events and model-visible tool results MUST retain
  existing behavior; execution context MUST NOT be added to public tool results.
- **TOOLCTX-010**: Trusted session provenance MUST make a confirmed session-scoped
  memory eligible for automatic recall only in the originating session.

## Acceptance criteria

- **AC-TOOLCTX-001**: Registry tests prove legacy/context-aware execution, schema
  stability, missing-context behavior, and argument rejection. (TOOLCTX-001, 002,
  005..007)
- **AC-TOOLCTX-002**: MiniPy/tracing tests prove session, entry, call, and trace ids,
  including concurrent isolation and cleanup on failure/cancellation. (TOOLCTX-003,
  008, 009)
- **AC-TOOLCTX-003**: Memory integration tests prove persisted trusted provenance,
  context-free global behavior, scoped-call rejection, and same-session recall.
  (TOOLCTX-005..007, 010)
- **AC-TOOLCTX-004**: Pi extension source/smoke tests prove provenance is hidden from
  parameters and forwarded from execution context. (TOOLCTX-004, 009)
- **AC-TOOLCTX-005**: HTTP tests prove typed provenance headers reach contextual
  tools while JSON spoofing fails. (TOOLCTX-004, 007)
- **AC-TOOLCTX-006**: Lock consistency, lint, all tests, compilation, Pi smoke, live
  HTTP bridge smoke, and browser QA pass.

## Decisions

- Context is capability metadata, not tool input, so it never appears in JSON schema.
- `contextvars` carries trace identity through the transparent tracing decorator;
  explicit context objects still cross the registry/handler boundary.
- HTTP provenance headers are trusted only inside the existing localhost bridge
  boundary. Authentication and remote deployment remain a later milestone.
- Global context-free candidates stay supported for local administration and tests;
  scoped candidates fail closed because a missing owner would create unusable or
  over-broad memory.
