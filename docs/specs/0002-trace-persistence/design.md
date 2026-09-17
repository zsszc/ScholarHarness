# Trace persistence design

## Components

```text
AgentRuntime
    |
TracingRuntime decorator
    |
SQLiteTraceRepository
    |-- agent_runs
    |-- agent_events
    `-- tool_executions
```

`TracingRuntime` creates one run per prompt stream, forwards events unchanged, and
persists them before yielding. It marks the run completed on `agent_settled`, failed
on an exception, and aborted when the stream closes without settling.

## Ordering and identity

`agent_events` has a run-local monotonic `sequence` with a unique `(run_id,
sequence)` constraint. An optional `idempotency_key` has a unique partial index per
run. Live events omit the key because identical deltas may be legitimate. Session
entry synchronization uses `entry:<entry_id>`.

Sequence assignment and insertion occur inside `BEGIN IMMEDIATE`, avoiding duplicate
sequence numbers when multiple writers share one SQLite database.

## Tool projection

Every raw event remains in `agent_events`. Additionally:

- `tool_execution_start` upserts `(run_id, tool_call_id)` with tool name, redacted
  arguments, and start time.
- `tool_execution_end` adds the redacted result, error state, end time, and duration.

Projection is idempotent by the unique `(run_id, tool_call_id)` key.

## Redaction and bounds

Payloads are recursively copied. Dictionary values whose normalized keys match the
configured secret markers, or end in one of those markers, become `[REDACTED]`.
Camel-case keys are normalized first, so `accessToken` is protected while
`totalTokens` remains useful telemetry. Redaction occurs before serialization or
size measurement.

If compact JSON exceeds 256 KiB, storage replaces it with:

```json
{"truncated": true, "original_bytes": 300000, "preview": "..."}
```

The preview contains at most 32 KiB of already-redacted serialized JSON. External
blob storage is deliberately deferred.

## API

- `GET /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/events`
- `GET /runs/{run_id}/tools`

All endpoints are read-only and return 404 for unknown runs.

## Memory provenance

Memory rows gain nullable `trace_run_id` and `source_tool_call_id` columns. Existing
databases are upgraded with additive SQLite migrations. The fields are supplied by
the agent/tool caller and retained for audit; a later policy may require them for
automatic candidate generation.

## Alternatives rejected

- Tracing only `PiRuntime`: prevents reuse by MiniPyRuntime.
- Coalescing deltas on write: loses exact replay and complicates recovery.
- Hash-deduplicating live events: identical deltas can be semantically distinct.
- Storing unlimited raw tool results: unsafe for database growth and accidental
  credential retention.
