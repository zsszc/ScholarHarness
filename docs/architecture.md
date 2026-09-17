# Architecture

## Ownership rules

ScholarHarness deliberately separates runtime state from research knowledge.

| State | Authority |
| --- | --- |
| Active model turn and context | Agent runtime (Pi or MiniPy) |
| Pi session entries and branch leaf | Pi |
| Browser MiniPy session lifecycle | ScholarHarness API process |
| Normalized trace projection | ScholarHarness |
| Papers, passages, citations | ScholarHarness |
| Long-term memories and evidence | ScholarHarness |
| Retrieval and citation evaluation | ScholarHarness |
| Deterministic run evaluation and baselines | ScholarHarness |

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

`OpenAICompatibleAdapter` is the first concrete model boundary. It translates the
internal messages and tool definitions to Chat Completions function calls over
HTTP, but remains outside session, tool execution, and trace ownership. The CLI
composes it with MiniPy rather than introducing provider concerns into the runtime.

The local workbench is a thin HTTP/WebSocket client of the same paper, memory,
trace, and runtime contracts. It has no privileged SQLite path: memory review still
crosses the explicit status endpoints, passage search still crosses `ToolRegistry`,
and trace payloads arrive after backend redaction and size bounding.

`ChatSessionManager` composes one independent MiniPy and tracing runtime per browser
session. Sessions and branch entries are deliberately process-local, while emitted
runs are durable. The browser can manage prompts, abort, compaction, forks, and
entry inspection through a normalized WebSocket protocol, but it cannot choose a
provider URL or send credentials. Application shutdown closes every provider
adapter owned by the manager.

`TracingRuntime` can wrap any runtime implementation. It persists ordered, redacted
events and correlated tool executions while forwarding normalized events unchanged.
Stable session entries use idempotency keys; live deltas remain distinct for replay.

`TraceEvaluator` is downstream of trace persistence and never calls the model. It
combines an editable evaluation case with an immutable terminal run, emits one
evidence-bearing check per expectation, and persists a case snapshot plus score.
Results compare against the previous different run for the same case, making score
deltas and regressions available to local workflows and CI without coupling
evaluation policy to a runtime.

`EvaluationRunner` closes the execution/evaluation loop without adding another
agent implementation. It loads a persisted case, creates a fresh server-owned
MiniPy session, streams the stored prompt through the normal tracing boundary,
evaluates the resulting terminal run, and always removes the temporary session.
Runtime failures remain terminal trace evidence and expose only stable public error
categories. Parallel invocations share repositories and trusted tools but never a
runtime session.

`EvaluationSuiteRunner` is the synchronous regression-gate layer above individual
case execution. Suite definitions retain ordered case references; each run snapshots
the suite and case intent, executes isolated cases sequentially, continues after a
safe per-item orchestration error, and persists aggregate counts plus evidence
links. Definition edits therefore affect future runs without rewriting history.

The Workbench Evaluation Lab remains a presentation client. It submits typed case
documents, asks the server to execute a case or grade an existing terminal run, and
renders persisted checks and history through public evaluation APIs. Input
normalization is limited to comma-separated form ergonomics; provider selection,
execution, validation, scoring, comparison, and regression classification stay in
Python.

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
6. **Observability workbench**: run timelines, tool inspector, memory review, and
   literature search.
7. **Browser chat gateway**: server-owned MiniPy sessions, live normalized events,
   reconnect, abort, compaction, and branching controls.
8. **Trace evaluations**: deterministic behavior checks, immutable evidence,
   regression baselines, HTTP workflows, and CI-friendly CLI output.
9. **Evaluation workbench**: case authoring, terminal-run grading, evidence
   inspection, score history, and responsive regression visualization.
10. **Automated evaluation execution**: isolated case-prompt runs, guaranteed
    cleanup, safe failure evidence, and API/CLI/Workbench entry points.
11. **Evaluation suites**: ordered multi-case regression gates, immutable aggregate
    history, failure isolation, HTTP workflows, and CI-friendly CLI output.
