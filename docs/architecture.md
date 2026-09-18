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

Its optional `TurnContextProvider` is a second provider-neutral boundary. Before a
turn, MiniPy asks it for rendered context plus decision metadata, records non-empty
context as an ordinary append-only system entry, and emits `context_injection`
before model execution. MiniPy has no dependency on memory storage or trust rules;
provider failure is a safe fail-open observation while cancellation still
propagates.

`OpenAICompatibleAdapter` is the first concrete model boundary. It translates the
internal messages and tool definitions to Chat Completions function calls over
HTTP, but remains outside session, tool execution, and trace ownership. The CLI
composes it with MiniPy rather than introducing provider concerns into the runtime.

The local workbench is a thin HTTP/WebSocket client of the same paper, memory,
trace, and runtime contracts. It has no privileged SQLite path: memory review still
crosses the explicit status endpoints, passage search still crosses `ToolRegistry`,
and trace payloads arrive after backend redaction and size bounding.

`ChatSessionManager` composes one independent MiniPy and tracing runtime per browser
session. Browser session metadata and full append-only entry trees are atomically
checkpointed to SQLite after turns and tree mutations. A restarted manager lists
stored summaries without creating adapters, then lazily validates and hydrates the
runtime when a client opens that session. The browser can manage prompts, abort,
compaction, forks, and entry inspection through a normalized WebSocket protocol,
but it cannot choose a provider URL or send credentials. Application shutdown
checkpoints state and closes adapters; only explicit deletion removes the snapshot.

`TracingRuntime` can wrap any runtime implementation. It persists ordered, redacted
events and correlated tool executions while forwarding normalized events unchanged.
Stable session entries use idempotency keys; live deltas remain distinct for replay.

`TraceEvaluator` is downstream of trace persistence and never calls the model. It
combines an editable evaluation case with an immutable terminal run, emits one
evidence-bearing check per expectation, and persists a case snapshot plus score.
Results compare against the previous different run for the same case, making score
deltas and regressions available to local workflows and CI without coupling
evaluation policy to a runtime.

Memory-context expectations use that same replay boundary. The evaluator projects
exactly one persisted `context_injection` into status, deduplicated memory ids, and
counts, then discards the rendered context body. Required/forbidden ids and context
budgets can therefore gate suites and CI without querying current memory state or
leaking memory text into evaluation artifacts.

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

The CI report boundary remains downstream of persisted suite execution. It converts
one immutable `EvaluationSuiteRun` into JSON and JUnit without calling a model or
recomputing pass state. Report files use same-directory temporary files plus atomic
replacement; the dedicated `eval-gate` command maps the persisted aggregate to
quality-gate exit codes while leaving interactive `eval-suite-run` behavior intact.

The Workbench Evaluation Lab remains a presentation client. It submits typed case
documents, asks the server to execute a case or grade an existing terminal run, and
renders persisted checks and history through public evaluation APIs. Input
normalization is limited to comma-separated form ergonomics; provider selection,
execution, validation, scoring, comparison, and regression classification stay in
Python.

Its Suite workspace follows the same boundary. The browser owns only an editable
ordered list of case ids and presentation selection state. It creates or replaces
suite definitions, requests server-side execution, and renders immutable aggregate
snapshots. Suite pass state and item outcomes are never recalculated in JavaScript.

## Runtime parity boundary

Pi and MiniPy traces are compared after persistence, never by coupling the two
runtimes. `RuntimeParityService` projects normalized lifecycle order, terminal
status, tool outcomes, context statuses, and assembled assistant output from each
run. Consecutive text deltas collapse into one lifecycle node so provider chunking
does not affect parity. The default report compares semantic structure and output presence while
discarding ids, timestamps, durations, and provider-only payloads. Exact assistant
text is opt-in so nondeterministic prose does not create false architectural
failures. Versioned JSON and exit code 1 make the same report usable in CI.

## Tool boundary

Python tools are registered once in `ToolRegistry`. MiniPyRuntime will call the
registry directly. Pi calls the same tools through a thin TypeScript extension and
localhost HTTP. The extension contains no retrieval or memory business logic.

Tool arguments and execution identity cross separate boundaries. Legacy handlers
receive only their validated Pydantic input; context-aware handlers additionally
receive an immutable `ToolExecutionContext`. MiniPy supplies session, assistant
entry, and call ids. `TracingRuntime` binds run identity with a task-local
`ContextVar`, so concurrent runs cannot leak provenance. Pi supplies its read-only
session/leaf identity and call id in dedicated localhost HTTP headers. None of these
fields appears in model-visible JSON Schema or public tool results.

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
Reviewed supersession atomically links an old confirmed row to a distinct active
confirmed replacement. Matching kind, scope, and scoped-session ownership prevent
cross-boundary consolidation; active-only targets keep the relation graph at depth
one and rule out cycles.

`MemoryContextPolicy` applies the same boundary automatically to API chat, CLI chat,
case execution, suite execution, and CI gates. It preserves deterministic FTS
relevance order, admits global and matching-session confirmed rows, excludes branch
scope, and renders a bounded data-not-instructions block with memory and evidence
coordinates. Selection counts, omissions, truncation, and ids are trace evidence;
the policy never mutates memory status.

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
12. **Suite workbench**: ordered suite authoring, aggregate execution/history,
    item-level diagnostics, and overview regression-gate metrics.
13. **CI regression gate**: stable exit semantics, atomic JSON/JUnit artifacts, and
    documented GitHub Actions evidence publication.
14. **Memory context policy**: trusted pre-turn recall, scope and budget controls,
    append-only context entries, safe failure handling, and trace/Workbench evidence.
15. **Memory context evaluations**: deterministic status/id/budget assertions over
    persisted injection evidence, with suite, CI, API, and Workbench compatibility.
16. **Trusted tool execution context**: runtime-owned session/entry/run/call
    provenance, task isolation, scoped-memory ownership, and Pi/HTTP propagation.
17. **Durable browser sessions**: atomic SQLite checkpoints, validated tree restore,
    lazy provider hydration, restart continuation, and explicit durable deletion.
18. **Auditable memory supersession**: atomic reviewed replacement links, trust-
    boundary validation, chain prevention, and recall-safe consolidation.
19. **Runtime parity reports**: versioned semantic trace projection, explainable
    Pi/MiniPy contract checks, privacy-aware output comparison, and CI exit semantics.
