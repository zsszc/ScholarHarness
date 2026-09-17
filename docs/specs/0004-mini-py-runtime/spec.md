# Educational Python agent runtime

Status: Approved
Date: 2026-09-17

## Problem

Pi is the production runtime integration, but delegating every agent decision to Pi
hides the mechanics the project is meant to teach. ScholarHarness needs a small
Python runtime that makes the model/tool loop, context construction, abort,
branching, compaction, and replay directly inspectable without duplicating the
paper, memory, or trace systems.

## Requirements

- **MINIPY-001**: `MiniPyRuntime` MUST implement the existing `AgentRuntime`
  contract and emit normalized `AgentEvent` objects.
- **MINIPY-002**: Model access MUST use a provider-neutral async `ModelAdapter`
  receiving ordered messages and JSON-schema tool definitions.
- **MINIPY-003**: The runtime MUST append the user message, request a model step,
  execute every requested tool through `ToolRegistry`, append tool results, and
  continue until the model returns no tool calls.
- **MINIPY-004**: Tool start/end events MUST use the existing trace correlation
  fields: `toolCallId`, `toolName`, `args`, `result`, and `isError`.
- **MINIPY-005**: Unknown tools, invalid arguments, and handler failures MUST become
  tool error results visible to the next model step rather than corrupting or
  terminating the session.
- **MINIPY-006**: A configurable maximum tool-round count MUST prevent infinite
  model/tool loops and emit a terminal error state.
- **MINIPY-007**: `abort()` MUST interrupt an in-flight model or tool await and end
  the stream with an aborted terminal state.
- **MINIPY-008**: Session entries MUST be append-only, carry stable ids and parent
  ids, and be returned in append order by `get_entries`; `since` MUST return only
  later entries.
- **MINIPY-009**: `fork(entry_id)` MUST move the active leaf to an existing entry so
  the next prompt creates a new branch without deleting the original branch.
- **MINIPY-010**: `compact()` MUST append a visible compaction entry summarizing the
  active path. Future model context MUST start from that summary while stored
  history remains replayable.
- **MINIPY-011**: The runtime MUST reject streaming before start, concurrent turns,
  unknown fork/since ids, and use after close with explicit errors.

## Decisions

- `ModelAdapter` returns typed assistant content, tool calls, and optional usage;
  it does not execute tools or own session state.
- Tool calls in one model response execute sequentially. This makes entry parentage,
  tracing, abort behavior, and test replay deterministic; parallel execution is a
  later policy option.
- Compaction is deterministic and local in this milestone: it records role-labelled
  text excerpts from the active path plus optional instructions. A model-generated
  summarizer can later replace this policy behind a separate boundary.
- Session storage is in-memory for this educational runtime. Durable normalized
  traces remain the responsibility of `TracingRuntime`.
- A turn ends with `agent_end` followed by `agent_settled`, including aborted and
  maximum-round outcomes.

## Acceptance criteria

- **AC-MINIPY-001**: A scripted model requests a registered tool, consumes its
  result, and produces a final assistant response with correctly ordered normalized
  events and append-only entries. (MINIPY-001..004)
- **AC-MINIPY-002**: Invalid and failing tool calls are returned to the model as
  structured error observations with correlated trace events. (MINIPY-005)
- **AC-MINIPY-003**: A repeating tool-call model stops at the configured bound and
  reports `max_tool_rounds`. (MINIPY-006)
- **AC-MINIPY-004**: Aborting a blocked model call cancels it and settles the turn as
  aborted. (MINIPY-007)
- **AC-MINIPY-005**: Forking an earlier entry preserves both child branches and
  constructs the next model context only from the selected path. (MINIPY-008,
  MINIPY-009)
- **AC-MINIPY-006**: Compaction preserves all prior entries but excludes pre-summary
  detail from subsequent model context. (MINIPY-010)
- **AC-MINIPY-007**: Lifecycle and unknown-entry misuse produce explicit errors.
  (MINIPY-011)
- **AC-MINIPY-008**: Static checks, compilation, all tests, and Pi smoke verification
  pass, proving the second runtime does not regress the Pi integration.
