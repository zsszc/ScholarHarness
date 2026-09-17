# Foundation design

## Ownership

Pi owns live model execution and its native session. ScholarHarness owns papers,
passages, memories, normalized projections, and evaluation data. The TypeScript
extension contains schemas and transport code only.

```text
PiRuntime -- JSONL --> Pi -- tool call --> TS bridge -- HTTP --> Python tools
                                                               |-- papers
                                                               `-- memory
```

## Runtime design

`PiRpcClient` owns one subprocess, one stdout reader, a pending-future map keyed by
request id, and an event queue. Command responses resolve futures; all other messages
enter the event stream. Stderr is drained independently to avoid subprocess blocking.

`PiRuntime` converts provider-specific events to `AgentEvent`. It waits for
`agent_settled` because retries, compaction, or queued continuations may follow
`agent_end`.

## Literature design

PDF ingestion uses `pypdf`, normalizes extracted text, and chunks within page
boundaries. Passage ids encode page and chunk position. SQLite tables hold canonical
metadata and passages; FTS5 holds searchable text. Reimporting a paper replaces its
passages and FTS rows transactionally.

## Memory trust boundary

The model can propose but cannot trust memory. `save_memory` resolves the referenced
passage, verifies a normalized verbatim substring, replaces model-supplied page data
with the canonical page, and writes a candidate. Confirmation and rejection are
separate HTTP mutations. FTS recall filters on `status = confirmed`.

## Failure modes

- Pi exits: pending requests fail and the event stream closes.
- Python service is unavailable: the extension tool returns an explicit tool error.
- PDF has no extractable text: import fails and recommends OCR.
- Evidence is fabricated: memory creation fails before persistence.
- Candidate is never reviewed: it remains stored but cannot affect recall.

## Deferred decisions

- Authentication for confirmation endpoints.
- OCR implementation and confidence thresholds.
- Hybrid lexical/vector retrieval and reranking.
- Memory conflict detection and supersession policy.
- Persisted runtime traces and replay.
