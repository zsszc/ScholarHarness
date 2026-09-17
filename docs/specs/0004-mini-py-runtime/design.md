# MiniPyRuntime design

## Components

```text
prompt
  |
MiniPyRuntime ---- ordered messages ----> ModelAdapter
  |                                         |
  |<---- assistant content + tool calls ----+
  |
  +---- validated execution ----> ToolRegistry
  |
  +---- normalized events ------> TracingRuntime / UI
  `---- append-only entries ----> branch / compact / replay
```

## Model boundary

The runtime defines `ModelMessage`, `ModelToolCall`, `ModelResponse`, and a
`ModelAdapter` protocol. These types capture only the information the loop needs.
Vendor-specific adapters translate their APIs at this boundary; tests use a scripted
adapter and never call a network service.

Tool definitions include name, description, and the Pydantic-generated input JSON
schema already owned by `ToolRegistry`.

## Turn state machine

```text
idle -> agent_start -> append user -> model step
                                      | no calls -> append assistant -> settled
                                      ` calls   -> append assistant intent
                                                   -> tool start/end + result
                                                   -> model step
```

The round counter increments for each model response containing tool calls. At the
configured limit the runtime appends a terminal assistant error entry rather than
making another provider request.

Tool failures are represented as `{"error": {"type": ..., "message": ...}}`.
The observation is appended with role `tool`; the loop then continues so the model
can recover or explain the failure.

## Session entries and branches

Entries are immutable records held in append order and indexed by id. Every newly
appended entry points at the current active leaf, then becomes the new leaf. Forking
only changes the leaf pointer. Path construction walks parents back to a root, so a
new turn after fork cannot see sibling-branch messages.

`get_entries(since=id)` slices the append log after that stable id. This is replay of
the runtime's durable shape; `TracingRuntime` can ingest it idempotently.

## Compaction

Compaction walks the active path, extracts bounded textual content, and appends a
`compaction` entry containing the summary and optional instructions. Context building
finds the most recent compaction entry on the selected path, emits it as a system
message, and includes only its descendants. Ancestors stay addressable for replay
and future forks.

## Abort and lifecycle

Each turn owns an abort event. Model and tool awaitables run in child tasks raced
against that event. Aborting cancels the child task and lets the generator emit
terminal `agent_end` and `agent_settled` events. A lock rejects concurrent turns
instead of interleaving entry chains.

`start()` is idempotent before close. `close()` aborts current work and permanently
closes the runtime instance.
