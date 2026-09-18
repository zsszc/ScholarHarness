# Memory context policy design

## Runtime contract

```text
TurnContextProvider.prepare(prompt, session_id)
  -> PreparedContext(content, metadata)

MiniPyRuntime.stream(prompt)
  -> agent_start
  -> context provider
  -> context_injection event
  -> append context system entry when content exists
  -> append user entry
  -> existing model/tool loop
```

`PreparedContext` is runtime-neutral. MiniPy knows only rendered system content and
JSON-safe metadata; it does not import memory models or repositories. Provider
failure is converted to `status=error, error=retrieval_error` and model execution
continues. Cancellation is never converted.

`context` entries are included by `_model_messages()` as system messages. Because
they have normal ids/parents, compaction and fork path selection already give them
append-only branch semantics.

## Memory policy

`MemoryContextPolicy` queries more confirmed candidates than its final item limit,
then filters scope:

```text
global  -> eligible
session -> eligible only when source_session_id == active session
branch  -> excluded
```

It preserves repository order and fills a bounded context block. Every item contains
its memory id, kind, scope, confidence, content, and evidence coordinates. Oversized
content is truncated only when needed to make the first otherwise-eligible item fit;
later items that do not fit are omitted. Metadata records retrieved, eligible,
selected, omitted, and truncated counts plus selected ids and budget values.

The system block begins with a fixed instruction that the enclosed memories are
reference data, never commands, and should be ignored when irrelevant. Evidence
coordinates encourage the model to use normal citation validation rather than
treating memory as self-authenticating truth.

## Composition

The API constructs one policy over its existing memory repository and shares it
across independently created chat sessions. CLI chat and CLI-created evaluation
managers construct the same policy over the selected database. Injected custom chat
managers in tests remain authoritative and are not replaced.

The explicit `recall_memory` tool remains registered. Automatic context improves
default recall; the tool still supports deliberate broader search and makes the two
memory strategies comparable during learning.

## Observability and safety

The `context_injection` event carries selection metadata and the rendered confirmed
context snapshot. It is persisted by `TracingRuntime` and displayed by the existing
generic Workbench activity renderer through `textContent`. Empty and error events do
not create system entries. Raw repository exceptions never enter event or model
payloads.

## Trade-offs

Pre-turn retrieval adds a synchronous SQLite query to each turn and lexical matching
misses semantic paraphrases. This is acceptable for a transparent baseline. The
provider contract isolates those limitations so hybrid retrieval, recency weighting,
token-aware budgets, and summarization can be evaluated later.
