# Memory context evaluations design

## Data contract

`EvaluationExpectations` gains four optional dimensions:

```text
context_status: selected | empty | error | null
required_memory_ids: string[]
forbidden_memory_ids: string[]
max_context_items: integer | null
```

The lists share the existing normalization boundary and add mutual-exclusion
validation. Defaults keep old case, result, suite-item, report, and database JSON
documents valid without migration.

## Trace projection

`TraceEvaluator` projects one private `_ContextObservation` from persisted events.
The projection accepts exactly one `context_injection` event with a known status and
a string-only `selected_ids` list. It records status, deduplicated ids, reported
selected count, and event count. It deliberately discards `content` and all other
payload fields.

Each configured expectation becomes its own check:

```text
context_status
required_memory:<id>
forbidden_memory:<id>
context_item_limit
```

Missing, duplicate, or malformed events yield `valid=false` plus a stable reason.
All configured checks then fail using that same safe observation. Retrieval is not
re-executed, preserving the historical decision that actually influenced the run.

## Workbench and compatibility

The case editor adds comma-separated required/forbidden memory ids, an optional
status select, and optional maximum item count. Existing `parseList`, request, and
safe `make(..., text)` rendering paths remain authoritative. Suite execution and CI
reports already snapshot/serialize the typed expectations, so no separate scoring
or report implementation is introduced.

## Trade-offs

Memory ids are less portable between independently seeded databases than semantic
labels, but they make trust and scope regressions exact and auditable. Semantic
retrieval-quality datasets can later introduce aliases or fixtures without making
this deterministic baseline depend on another model.
