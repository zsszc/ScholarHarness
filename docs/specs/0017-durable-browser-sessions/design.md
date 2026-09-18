# Durable browser sessions design

## Storage

`SQLiteChatSessionRepository` owns two additive tables:

```text
chat_sessions(id, created_at, updated_at, active_leaf_id, last_run_id)
chat_session_entries(session_id, position, entry_id, parent_id,
                     entry_type, event_timestamp, data_json)
```

`save(snapshot)` uses `BEGIN IMMEDIATE`, upserts metadata, deletes the prior entry
set, inserts the complete ordered replacement, and commits. JSON is UTF-8 and entry
data is bounded by the existing runtime/tool limits. No provider configuration is
stored.

## Restore boundary

MiniPy accepts optional initial entries and active leaf. Before assigning internal
state it validates the complete tree in order: every entry has a unique id, matches
the runtime session, and references either no parent or an earlier entry. The active
leaf must be null only for an empty tree or identify a loaded entry. Validation uses
copies so caller mutation cannot rewrite runtime state.

## Lazy manager lifecycle

The manager keeps live sessions separately from repository summaries:

```text
list -> merge live info with stored summaries (no adapter creation)
get  -> return live, otherwise load snapshot -> create adapter -> restore/start
create -> create/start -> initial checkpoint
delete -> close live if present -> delete snapshot
close_all -> checkpoint/close live -> keep snapshots
```

`ChatSession` checkpoints in `finally` after a turn and after successful fork or
compaction. Restored `TracingRuntime.last_run_id` retains the last durable trace link;
the next turn naturally replaces it with a new run.

## Failure handling

SQLite transactions roll back incomplete checkpoints. Snapshot validation errors
are categorized as corrupt-session activation failures and do not delete data.
Without an adapter factory, list remains available while create/activation returns
the existing configuration error. Evaluation managers omit the repository and keep
their current ephemeral cleanup behavior.
