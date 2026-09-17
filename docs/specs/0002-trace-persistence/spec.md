# Persisted runtime traces

Status: Verified
Date: 2026-09-17

## Problem

ScholarHarness currently streams normalized Pi events but does not persist complete
agent runs. Without durable traces, memories cannot be reliably linked to the exact
tool call and branch that produced them, and evaluation cannot replay past behavior.

## Requirements

- **TRACE-001**: Persist each runtime run with runtime type, external session id,
  start/end timestamps, status, and active leaf id.
- **TRACE-002**: Persist normalized events in order while retaining a redacted,
  size-bounded copy of the original JSON payload.
- **TRACE-003**: Persist tool executions with tool call id, validated arguments,
  result, error state, and duration.
- **TRACE-004**: Event ingestion MUST be idempotent across incremental `get_entries`
  synchronization by using stable Pi entry ids.
- **TRACE-005**: A memory candidate SHOULD reference the trace run and tool call in
  addition to its existing session and entry references.
- **TRACE-006**: Provide read-only APIs for listing runs and inspecting their event
  timelines.
- **TRACE-007**: Trace storage MUST recursively redact configured secret fields
  before writing raw payloads.
- **TRACE-008**: One runtime-neutral decorator MUST trace any `AgentRuntime` without
  adding trace persistence concerns to Pi-specific code.
- **TRACE-009**: Live stream deltas MUST be stored individually to preserve replay
  fidelity; UI-level coalescing is outside persistence.
- **TRACE-010**: A stored raw event MUST NOT exceed 256 KiB. Oversized payloads MUST
  be replaced by a bounded envelope recording truncation and original byte size.

## Decisions

- Streamed deltas are stored individually. A later read model may coalesce them.
- Raw JSON is capped at 256 KiB; oversized content stores a 32 KiB preview envelope.
- Synced session entries use `entry:<entry_id>` idempotency keys. Ephemeral live events
  use a monotonic run-local sequence and are not deduplicated.
- Keys matching or ending in `authorization`, `api_key`, `apikey`, `token`,
  `password`, `secret`, `cookie`, or `credential` are redacted case-insensitively at
  every nesting level. Token usage fields such as `totalTokens` remain observable.
- Trace APIs are read-only. Deletion, retention, and blob storage are deferred.

## Acceptance criteria

- **AC-TRACE-001**: Starting and completing a traced fake runtime creates one
  completed run and an ordered replayable event timeline. (TRACE-001, TRACE-002,
  TRACE-008, TRACE-009)
- **AC-TRACE-002**: Re-ingesting the same Pi entries stores each stable entry once.
  (TRACE-004)
- **AC-TRACE-003**: Tool start/end events produce one correlated tool execution with
  arguments, result, error state, and non-negative duration. (TRACE-003)
- **AC-TRACE-004**: Nested secret fields are absent from stored JSON, and oversized
  payloads produce a bounded truncation envelope. (TRACE-007, TRACE-010)
- **AC-TRACE-005**: A candidate memory can retain run and tool-call provenance.
  (TRACE-005)
- **AC-TRACE-006**: Read-only APIs list runs, events, and tool executions in stable
  order. (TRACE-006)
- **AC-TRACE-007**: Static checks, compilation, all automated tests, and Pi smoke
  verification pass.
