# ScholarHarness

ScholarHarness is a runtime-agnostic research agent harness. It keeps literature,
memory, tools, traces, and evaluation in Python while allowing the agent runtime to
be swapped between Pi and a small educational Python runtime.

**Portfolio status: complete local-first reference implementation.** For a fast
review, start with the [three-minute portfolio guide](docs/portfolio.md),
[architecture](docs/architecture.md), and reproducible
[offline benchmark](docs/benchmark.md). Every non-trivial milestone has requirement
ids and verification evidence under [`docs/specs`](docs/specs).

The repository contains:

- a typed runtime contract and normalized event model;
- an asynchronous JSONL RPC client for `pi --mode rpc`;
- an append-only session-tree projector;
- a reusable Python tool registry;
- a persistent SQLite/FTS5 paper repository with `search_papers` and `read_passage` tools;
- deterministic hybrid lexical/vector retrieval with inspectable RRF rankings;
- strict quote-to-passage validation through the `validate_citation` tool;
- page-aware PDF ingestion with stable passage coordinates;
- evidence-verified candidate memories with explicit confirmation and recall;
- automatic pre-turn recall of trusted, scope-filtered memory with observable budgets;
- durable, redacted runtime traces and correlated tool executions;
- an inspectable Python model/tool loop with abort, branching, compaction, and replay;
- a local observability workbench for runs, tools, memory review, and library search;
- a server-owned browser chat gateway with live events and session controls;
- deterministic trace evaluations with evidence checks and regression deltas;
- a FastAPI service exposing the tool bridge;
- a thin Pi TypeScript extension that forwards tool calls to Python.

Fast evaluator path—no model credentials required:

```bash
uv sync --extra dev
uv run scholar-harness pi-smoke
uv run scholar-harness benchmark --papers 100 --queries 100 --trace-events 1000
uv run pytest
```

## Architecture

```text
UI / API
   |
   +-- PiRuntime ---- JSONL RPC ---- pi --mode rpc
   |                                      |
   |                              TypeScript bridge
   |                                      |
   +-- MiniPyRuntime                HTTP tool calls
                                          |
                                  Python ToolRegistry
                                          |
                              papers / memory / evals
```

Pi owns the live agent conversation. Python owns domain data and normalized traces.
This avoids maintaining two competing sources of truth.

## Quick start

Requirements:

- Python 3.11+
- `uv`
- Node.js and Pi only when using `PiRuntime`

```bash
uv sync --extra dev
uv run pytest
uv run scholar-harness doctor
uv run scholar-harness pi-smoke
uv run scholar-harness api --reload
```

Open `http://127.0.0.1:8765/docs` to exercise the paper tools. Papers are stored in
`data/scholar_harness.db` by default.

Open `http://127.0.0.1:8765/workbench` for the local research-agent console. It
summarizes runs and tool calls, replays normalized event timelines, exposes memory
confirmation/rejection, and searches the paper collection in hybrid or lexical
mode. With `OPENAI_MODEL` configured on the API process, its Agent Chat page creates
an independent MiniPy session and displays live model, tool, and lifecycle events.
The workbench has no external asset or build dependency and is intended for
localhost; public deployment and multi-user authentication are not part of the
current scope.

For a hardened local Pi bridge, set the same high-entropy secret in both the API and
Pi process environments:

```bash
export SCHOLAR_HARNESS_BRIDGE_TOKEN='replace-with-a-random-secret'
uv run scholar-harness api
```

Pi reads this variable automatically and sends it only with runtime-provenance
headers. When the API has a token configured, missing or invalid credentials are
rejected before the tool registry runs. Blank or unset values retain zero-config
localhost development mode. Health checks and provenance-free retrieval remain
available to the Workbench; the token is never part of model-visible tool schemas.

All repositories share a five-second SQLite busy timeout, foreign-key enforcement,
WAL journaling, and `synchronous=NORMAL`. This allows Workbench, chat, evaluation,
and Pi writes to serialize under normal contention while keeping lock waits bounded.

For a full Pi-extension-to-Python bridge check, keep the API running in one terminal
and run this in another:

```bash
uv run scholar-harness pi-smoke --check-service
```

Add a paper:

```bash
curl -X POST http://127.0.0.1:8765/papers \
  -H 'content-type: application/json' \
  -d '{
    "id": "demo-paper",
    "title": "Memory for Research Agents",
    "passages": [
      {"id": "p1", "text": "Long-term memory requires evidence provenance.", "page": 3}
    ]
  }'
```

Search it:

```bash
curl -X POST http://127.0.0.1:8765/internal/tools/search_papers \
  -H 'content-type: application/json' \
  -d '{"query": "evidence memory", "limit": 5}'
```

`search_papers` defaults to `hybrid` retrieval and accepts `"mode": "lexical"`
for a BM25-only search. Hybrid hits include `lexical_rank`, `vector_rank`, and the
fused `score`, making the agent's retrieval decision inspectable. The built-in
feature-hashing vectors are an offline development baseline; the provider boundary
is designed for a later sentence-transformer or hosted embedding adapter.

Before presenting a direct quote, validate its exact coordinate:

```bash
curl -X POST http://127.0.0.1:8765/internal/tools/validate_citation \
  -H 'content-type: application/json' \
  -d '{
    "paper_id": "demo-paper",
    "passage_id": "p1",
    "quote": "Long-term memory requires evidence provenance."
  }'
```

Import a digitally readable PDF:

```bash
curl -X POST 'http://127.0.0.1:8765/papers/import/pdf' \
  -F 'file=@/absolute/path/to/paper.pdf'
```

Scanned image-only PDFs are rejected with an explicit OCR-required error. OCR is a
later milestone rather than silently indexing empty or unreliable text.

## Memory lifecycle

`save_memory` never writes directly into trusted long-term context. It verifies that
every quoted source occurs in the referenced paper passage and stores the result as
`candidate`. Candidates can be inspected and explicitly promoted:

```bash
curl http://127.0.0.1:8765/memories?status=candidate
curl -X POST http://127.0.0.1:8765/memories/MEMORY_ID/confirm
curl -X POST http://127.0.0.1:8765/memories/OLD_ID/supersede \
  -H 'content-type: application/json' \
  -d '{"replacement_id":"CONFIRMED_REPLACEMENT_ID"}'
```

`recall_memory` searches only `confirmed` records. Rejected and superseded records
remain auditable in SQLite but cannot silently influence the agent. Supersession is
an explicit reviewer operation: it preserves the old content, evidence, and
provenance while recording its active confirmed replacement. Kind, scope, and
scoped-session ownership must match, and replacement chains are rejected.

Memory provenance is harness-owned rather than model-authored. The model-visible
`save_memory` schema contains no session, entry, run, or tool-call ids. MiniPy adds
them through `ToolExecutionContext`, the tracing decorator adds its task-local run
id, and the Pi extension forwards its read-only session identity through dedicated
localhost bridge headers. Context-free administration may create global candidates;
session and branch candidates require an owning runtime context.

MiniPy chats and evaluation runs also search confirmed memory automatically before
each turn. Global memories are eligible everywhere; session memories are eligible
only in their originating session; branch memories remain excluded until the
harness has a durable branch-identity policy. The bounded result is added as an
inspectable system entry labelled as reference data, and every decision (including
an empty match or safe retrieval failure) is emitted as `context_injection` in the
live activity stream and trace. Manual `recall_memory` remains available when the
agent needs an explicit follow-up search.

## Runtime traces

Wrap any runtime with `TracingRuntime` to persist ordered events, run status, and tool
executions without coupling that runtime to SQLite. Stable Pi session entries are
deduplicated by entry id; live streaming deltas remain separate for exact replay.
Sensitive fields are recursively redacted and raw payloads are capped at 256 KiB.

Trace inspection endpoints:

```text
GET /runs
GET /runs/{run_id}
GET /runs/{run_id}/events
GET /runs/{run_id}/tools
```

Compare a Pi trace with a MiniPy trace through the shared behavioral contract:

```bash
uv run scholar-harness parity \
  --left-run PI_RUN_ID \
  --right-run MINIPY_RUN_ID \
  --database data/scholar_harness.db
```

The versioned JSON report compares terminal status, normalized lifecycle ordering,
tool names/error outcomes, memory-context statuses, and whether an assistant answer
was produced. Volatile ids, timestamps, latency, provider payloads, and exact prose
are ignored. Add `--strict-output` only for deterministic fixtures where assistant
text must match exactly; mismatches return exit code 1 for CI use.

## Deterministic evaluations

Evaluation cases turn completed traces into explainable regression signals without
calling another model. Expectations can require or forbid tools, bound tool calls
and duration, require successful citation validation, check terminal status, and
assert case-insensitive answer substrings. They can also require a memory-context
status or memory ids, forbid memory ids, and bound selected context items using the
persisted `context_injection` decision rather than rerunning retrieval. Every check
records expected and observed evidence, and each result compares its score with the
previous run for that case. Memory checks retain ids and counts but never copy the
injected memory body into evaluation results or CI artifacts.

Create a case through the API:

```bash
curl -X POST http://127.0.0.1:8765/evaluations/cases \
  -H 'content-type: application/json' \
  -d '{
    "name": "Evidence-grounded answer",
    "prompt": "Find and cite evidence about agent memory.",
    "expectations": {
      "required_tools": ["search_papers", "validate_citation"],
      "require_citation_validation": true,
      "answer_contains": ["evidence"],
      "terminal_status": "completed"
    },
    "pass_threshold": 1.0
  }'
```

Execute a case from its stored prompt, or evaluate an existing run. Both CLI paths
print CI-friendly JSON:

```bash
curl -X POST \
  http://127.0.0.1:8765/evaluations/cases/CASE_ID/execute

uv run scholar-harness eval-run \
  --case CASE_ID \
  --database data/scholar_harness.db

curl -X POST \
  http://127.0.0.1:8765/evaluations/cases/CASE_ID/runs/RUN_ID

uv run scholar-harness eval \
  --case CASE_ID \
  --run RUN_ID \
  --database data/scholar_harness.db
```

`eval-run` uses a fresh, server-configured MiniPy session, persists its trace,
evaluates the terminal run, and removes the temporary session. A model failure is
still evaluated when it produced a terminal failed trace. Evaluation results
snapshot the case definition used at evaluation time; editing a case affects future
evaluations but does not rewrite existing evidence.

Group cases into an ordered regression suite and run the whole gate:

```bash
curl -X POST http://127.0.0.1:8765/evaluations/suites \
  -H 'content-type: application/json' \
  -d '{"name":"Research regression","case_ids":["CASE_A","CASE_B"]}'

curl -X POST \
  http://127.0.0.1:8765/evaluations/suites/SUITE_ID/execute

uv run scholar-harness eval-suite-run \
  --suite SUITE_ID \
  --database data/scholar_harness.db
```

Suites run cases sequentially in fresh sessions and persist an immutable aggregate
with ordered item snapshots, pass/fail/error counts, trace ids, and result ids. An
orchestration error is reduced to a safe category and does not hide later cases.

In the Workbench, open **Evaluation Lab → Suites** to create or edit the ordered
case membership, move cases up or down, execute the regression gate, and inspect
aggregate history plus every case outcome. Overview reports total and passing suite
runs from the same persisted API contract.

Use the CI gate command when suite failure must fail a job and produce portable
evidence:

```bash
uv run scholar-harness eval-gate \
  --suite SUITE_ID \
  --database data/scholar_harness.db \
  --json-output artifacts/evaluation-gate.json \
  --junit-output artifacts/evaluation-gate.xml
```

The command exits `0` for a passing suite, `1` for a completed failing suite, and
`2` for configuration or invocation errors. See [docs/ci.md](docs/ci.md) for report
semantics and a GitHub Actions workflow that publishes evidence even on failure.

## Educational Python runtime

`MiniPyRuntime` implements the same `AgentRuntime` contract as Pi while keeping the
agent loop visible in Python. A provider-specific `ModelAdapter` receives ordered
`ModelMessage` objects and complete JSON-schema tool definitions, then returns a
`ModelResponse` containing text and zero or more `ModelToolCall` objects.

The runtime executes calls through the same `ToolRegistry`, returns structured tool
errors to the model, stops repeated calls at a configurable bound, and emits trace-
compatible tool events. Its append-only entries support incremental replay,
branching from any stable entry, and explicit compaction nodes. Wrap it in
`TracingRuntime(runtime, repository, runtime_type="mini-py")` to persist runs exactly
like Pi runs.

The core deliberately contains no provider SDK. A hosted or local model adapter is
an integration at the model boundary, while session and tool-loop behavior stays
testable without network access.

Run the Python loop against an OpenAI-compatible Chat Completions endpoint:

```bash
export OPENAI_API_KEY="your-key"
export OPENAI_MODEL="your-model-id"
uv run scholar-harness chat
```

For an OpenAI-compatible local server, the key may be omitted:

```bash
OPENAI_MODEL="local-model" \
OPENAI_BASE_URL="http://127.0.0.1:11434/v1" \
uv run scholar-harness chat
```

Use `--prompt "..."` for one turn and exit. Interactive mode provides `/entries`,
`/fork ENTRY_ID`, `/compact [instructions]`, `/help`, and `/exit`. Runs are traced
to `data/scholar_harness.db` by default; use `--no-trace` only when an unpersisted
session is intentional. The secret value is read from `OPENAI_API_KEY` (or the
environment-variable name selected by `--api-key-env`) and is never accepted as a
CLI argument.

The same server environment enables browser chat:

```bash
export OPENAI_API_KEY="your-key"
export OPENAI_MODEL="your-model-id"
uv run scholar-harness api
```

Open the Workbench and select **Agent Chat**. Browser requests cannot provide an API
key or provider URL; the gateway reads `OPENAI_MODEL`, `OPENAI_BASE_URL`,
`OPENAI_API_KEY`, and optional `OPENAI_TIMEOUT_SECONDS` only from the API process.
Sessions survive WebSocket reconnects and API restarts. Browser-owned MiniPy entry
trees, active leaves, compaction/fork state, and last-run links are atomically
checkpointed in the same SQLite database. Listing restored sessions does not create
model clients; the provider adapter is initialized only when a session is opened.
Explicit session deletion removes the durable checkpoint, while graceful shutdown
keeps it available for the next process.

Select **Evaluation Lab** to author or edit deterministic cases, evaluate any
terminal run, or execute the selected Case prompt in a fresh isolated session.
Inspect each check's expected and observed evidence and compare score history.
Regression rows show the previous score and signed delta; all displayed values come
from persisted backend result snapshots rather than browser-side rescoring.

## Pi bridge

Start the Python service, then load `pi-extension/index.ts` as a Pi extension. The
bridge registers named tools in Pi and forwards execution to the Python API. Set
`SCHOLAR_HARNESS_URL` if the service is not running on `http://127.0.0.1:8765`.

The Python RPC client expects Pi to be installed and available as `pi`. Pi is not a
Python dependency and is intentionally kept outside the package environment.

Install the current official Pi CLI with:

```bash
npm install -g --ignore-scripts @earendil-works/pi-coding-agent
```

See [docs/architecture.md](docs/architecture.md) for ownership rules and the next
implementation milestones.

## Development process

Development follows the lightweight SDD workflow documented in
[`docs/sdd/README.md`](docs/sdd/README.md). The verified foundation specification is
under [`docs/specs/0001-foundation/`](docs/specs/0001-foundation/); future behavior is
specified before implementation and committed at verified milestones.
