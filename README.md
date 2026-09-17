# ScholarHarness

ScholarHarness is a runtime-agnostic research agent harness. It keeps literature,
memory, tools, traces, and evaluation in Python while allowing the agent runtime to
be swapped between Pi and a small educational Python runtime.

The repository currently contains the first vertical slice:

- a typed runtime contract and normalized event model;
- an asynchronous JSONL RPC client for `pi --mode rpc`;
- an append-only session-tree projector;
- a reusable Python tool registry;
- a persistent SQLite/FTS5 paper repository with `search_papers` and `read_passage` tools;
- deterministic hybrid lexical/vector retrieval with inspectable RRF rankings;
- strict quote-to-passage validation through the `validate_citation` tool;
- page-aware PDF ingestion with stable passage coordinates;
- evidence-verified candidate memories with explicit confirmation and recall;
- durable, redacted runtime traces and correlated tool executions;
- a FastAPI service exposing the tool bridge;
- a thin Pi TypeScript extension that forwards tool calls to Python.

## Architecture

```text
UI / API
   |
   +-- PiRuntime ---- JSONL RPC ---- pi --mode rpc
   |                                      |
   |                              TypeScript bridge
   |                                      |
   +-- MiniPyRuntime (planned)      HTTP tool calls
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
```

`recall_memory` searches only `confirmed` records. Rejected and superseded records
remain auditable in SQLite but cannot silently influence the agent.

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
