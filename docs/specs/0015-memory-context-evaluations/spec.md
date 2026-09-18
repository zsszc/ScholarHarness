# Memory context evaluations

Status: Approved
Date: 2026-09-18

## Problem

ScholarHarness can now inject trusted memory and record every selection decision,
but evaluation cases cannot express whether the right memory was recalled. A memory
harness needs deterministic retrieval assertions so regressions in trust, scope,
ranking, and budgets can fail the same local suites and CI gate as tool behavior.

## Requirements

- **MEMEVAL-001**: Evaluation expectations MUST optionally declare a required
  context status (`selected`, `empty`, or `error`), required memory ids, forbidden
  memory ids, and a maximum selected-context item count.
- **MEMEVAL-002**: Memory id lists MUST be normalized like existing expectation
  lists, reject empty/oversized values, remove duplicates, and reject overlap
  between required and forbidden ids.
- **MEMEVAL-003**: Every configured memory expectation MUST produce an independent,
  evidence-bearing `EvaluationCheck` with a stable id.
- **MEMEVAL-004**: Evaluation MUST use persisted `context_injection` events only;
  it MUST NOT rerun retrieval, query the memory store, or trust current memory state.
- **MEMEVAL-005**: A missing context event MUST fail every configured memory check
  with an explicit safe observation rather than raising or silently passing.
- **MEMEVAL-006**: Required ids MUST all appear in `selected_ids`; forbidden ids
  MUST not appear; the selected-count limit MUST compare against the normalized
  observed id set rather than model-visible context text.
- **MEMEVAL-007**: Malformed context-event payloads MUST be handled deterministically
  as safe invalid observations and MUST NOT leak memory content into check evidence.
- **MEMEVAL-008**: Case/result/suite snapshots, JSON/JUnit reports, API round trips,
  and historical rows MUST preserve the new optional expectations compatibly.
- **MEMEVAL-009**: The Workbench case editor MUST author and restore the new fields,
  and check rendering MUST continue to use safe DOM text nodes.
- **MEMEVAL-010**: Cases without memory expectations MUST keep their existing check
  count, scoring, pass/fail result, and report behavior.

## Decisions

- Assertions target memory ids rather than full content. Ids are durable trace
  evidence and avoid copying potentially sensitive memory text into evaluation
  results and CI artifacts.
- A trace run represents one streamed turn, so exactly one normalized context event
  is expected. Multiple events are invalid evidence instead of using an ambiguous
  first/last heuristic.
- `max_context_items` uses the deduplicated observed `selected_ids` length and also
  records the provider's reported count for diagnostics.
- Expectations remain optional and additive; existing persisted JSON documents load
  with defaults.

## Acceptance criteria

- **AC-MEMEVAL-001**: Model validation tests cover normalization, overlap, bounds,
  optional compatibility, and serialization round trips. (MEMEVAL-001, 002, 008)
- **AC-MEMEVAL-002**: Evaluator tests prove passing/failing status, required,
  forbidden, and count checks with stable expected/observed evidence. (MEMEVAL-003,
  004, 006)
- **AC-MEMEVAL-003**: Missing, duplicate, and malformed-event tests fail safely,
  never query live memory, and never expose context content. (MEMEVAL-005, 007)
- **AC-MEMEVAL-004**: Existing evaluation and suite tests prove no behavior change
  when memory expectations are absent. (MEMEVAL-008, 010)
- **AC-MEMEVAL-005**: API and Workbench tests prove authoring/restoration and safe
  rendering through the public case contract. (MEMEVAL-008, 009)
- **AC-MEMEVAL-006**: Lock consistency, lint, all tests, compilation, Pi smoke, live
  HTTP bridge smoke, and browser QA pass.
