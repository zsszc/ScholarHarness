# Persisted runtime traces

Status: Draft
Date: 2026-09-17

## Problem

ScholarHarness currently streams normalized Pi events but does not persist complete
agent runs. Without durable traces, memories cannot be reliably linked to the exact
tool call and branch that produced them, and evaluation cannot replay past behavior.

## Proposed requirements

- **TRACE-001**: Persist each runtime run with runtime type, external session id,
  start/end timestamps, status, and active leaf id.
- **TRACE-002**: Persist normalized events in order while retaining the original raw
  JSON payload.
- **TRACE-003**: Persist tool executions with tool call id, validated arguments,
  result, error state, and duration.
- **TRACE-004**: Event ingestion MUST be idempotent across incremental `get_entries`
  synchronization.
- **TRACE-005**: A memory candidate SHOULD reference the run, session entry, branch
  leaf, and tool call that produced it.
- **TRACE-006**: Provide read-only APIs for listing runs and inspecting their event
  timelines.
- **TRACE-007**: Trace storage MUST redact configured secret fields before writing
  raw payloads.

## Open questions

- Should streamed deltas be stored individually or coalesced per message?
- Which tool result fields need size limits or external blob storage?
- Is event identity derived from Pi entry ids, local sequence numbers, or both?
- Which fields are redacted by default before a multi-user deployment exists?

## Acceptance criteria

To be defined after the open questions are resolved and the design is approved.
