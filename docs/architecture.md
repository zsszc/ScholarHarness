# Architecture

## Ownership rules

ScholarHarness deliberately separates runtime state from research knowledge.

| State | Authority |
| --- | --- |
| Active model turn and context | Agent runtime (Pi or MiniPy) |
| Pi session entries and branch leaf | Pi |
| Normalized trace projection | ScholarHarness |
| Papers, passages, citations | ScholarHarness |
| Long-term memories and evidence | ScholarHarness |
| Retrieval and citation evaluation | ScholarHarness |

Runtime session contents are projected for display and evaluation, but are not
silently rewritten by the Python service.

## Runtime boundary

Every runtime implements the same small contract:

- start and close;
- stream a prompt as normalized events;
- abort and compact;
- fork from a stable entry id;
- read append-only entries.

Pi is integrated through its JSONL RPC mode. The client assigns an id to each
command, correlates responses without blocking the event stream, and publishes
unsolicited runtime events through an async iterator.

`MiniPyRuntime` implements the same contract with a provider-neutral `ModelAdapter`.
It owns an explicit bounded model/tool loop, append-only in-memory session entries,
path-scoped branching, cooperative abort, and visible compaction nodes. It reuses
`ToolRegistry`; model adapters never execute tools directly.

`TracingRuntime` can wrap any runtime implementation. It persists ordered, redacted
events and correlated tool executions while forwarding normalized events unchanged.
Stable session entries use idempotency keys; live deltas remain distinct for replay.

## Tool boundary

Python tools are registered once in `ToolRegistry`. MiniPyRuntime will call the
registry directly. Pi calls the same tools through a thin TypeScript extension and
localhost HTTP. The extension contains no retrieval or memory business logic.

Tool results should preserve evidence coordinates:

```json
{
  "paper_id": "paper-001",
  "passage_id": "passage-007",
  "page": 12,
  "section": "Method",
  "text": "...",
  "score": 0.84
}
```

## Memory trust boundary

Agents may propose memories, but cannot make them trusted. `save_memory` verifies
verbatim evidence against a stored passage and creates a `candidate`. Only an
explicit API action can mark it `confirmed`; `recall_memory` excludes every other
status. Rejected and superseded rows remain stored for audit and evaluation.

## Delivery milestones

1. **Runtime foundation**: Pi RPC, tools, session projection, tests.
2. **Literature ingestion**: PDF parsing, page-aware chunks, SQLite FTS5.
3. **Memory and traces**: verified candidates, provenance, replayable runtime events.
4. **Hybrid retrieval**: offline embedding baseline, RRF, citation validation.
5. **MiniPyRuntime**: educational tool loop, branching, compaction and replay.
6. **Workbench UI**: chat, session graph, tool inspector and runtime comparison.
