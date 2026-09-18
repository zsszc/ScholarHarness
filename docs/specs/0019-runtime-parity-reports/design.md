# Runtime parity reports design

## Projection boundary

`RuntimeParityService` reads `AgentRun`, ordered `TraceEvent`, and projected
`ToolExecution` rows from `SQLiteTraceRepository`. It creates an immutable semantic
snapshot. Only normalized live lifecycle types are retained; entry-replay rows are
excluded. Tool call ids and timing are intentionally discarded.

Message text is assembled from normalized `delta`, with Pi's legacy `text` field as
a compatibility fallback. Consecutive message-update lifecycle nodes are collapsed
so provider streaming chunk size cannot create a false mismatch. The snapshot may
carry the assembled text internally and
in the top-level left/right snapshots, but ordinary check observations report only
whether output exists. Strict mode adds an exact-output check with text observations
because the caller explicitly requested it.

## Checks

The report evaluates five default contracts:

1. terminal status;
2. ordered lifecycle event types;
3. ordered `(tool_name, is_error)` outcomes;
4. ordered context-injection statuses;
5. assistant-output presence.

Strict mode adds exact assistant text. Aggregate `passed` is true only when every
included check passes. The output uses schema version `1` so CI artifacts can evolve
without silently changing meaning.

## CLI

`scholar-harness parity --left-run ID --right-run ID [--strict-output]` loads the
configured SQLite database and prints a Pydantic JSON report. A mismatch is a normal
comparison result with exit code 1. Missing run ids are usage failures reported by
the existing argument parser.

## Trade-offs

This compares observable harness behavior, not hidden reasoning. Exact arguments and
results are omitted because equivalent runtimes may serialize provider data
differently. Evaluation cases remain responsible for task-quality assertions;
parity reports answer the narrower architectural question: did both runtimes follow
the same harness contract?
