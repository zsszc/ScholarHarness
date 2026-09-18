# Memory context policy

Status: Verified
Date: 2026-09-18

## Problem

ScholarHarness verifies and reviews long-term memories, but the runtime can use them
only when the model independently chooses `recall_memory`. That demonstrates a tool,
not a complete memory harness. A production-oriented agent needs an explicit policy
that retrieves trusted memories before a turn, controls scope and budget, presents
them as data rather than instructions, and makes every injection observable.

## Requirements

- **MEMCTX-001**: Define a provider-neutral pre-turn context contract that
  `MiniPyRuntime` MAY invoke without depending on the memory repository.
- **MEMCTX-002**: Before every model call sequence, the runtime MUST prepare context
  from the current user prompt and session id, append any prepared system context
  before the user message, and retain it in the active session branch.
- **MEMCTX-003**: The memory policy MUST retrieve only `confirmed` memories and MUST
  never inject candidate, rejected, or superseded rows.
- **MEMCTX-004**: Global memories are eligible for every session; session memories
  are eligible only when `source_session_id` matches the active session; branch
  memories MUST remain excluded until a branch-identity policy is specified.
- **MEMCTX-005**: Selection MUST preserve deterministic repository relevance order,
  enforce configurable item and character budgets, and report whether eligible
  content was omitted or truncated.
- **MEMCTX-006**: Injected text MUST label memory content as reference data rather
  than instructions and MUST include memory ids plus paper/passage/page provenance
  coordinates so the model can validate or cite sources.
- **MEMCTX-007**: Every configured turn MUST emit a normalized
  `context_injection` event before model execution, including empty selection,
  selected ids, scope decisions, budget metadata, and a stable status.
- **MEMCTX-008**: Retrieval failure MUST fail open: emit a credential-safe
  `retrieval_error` category and continue the turn without injected context; request
  cancellation MUST still propagate normally.
- **MEMCTX-009**: Context entries and events MUST survive tracing, entry replay,
  compaction boundaries, and branching without silently rewriting earlier context.
- **MEMCTX-010**: Browser chat, CLI chat, case execution, suite execution, and CI
  gates MUST use the same default memory policy over their configured database.
- **MEMCTX-011**: Manual `recall_memory` and memory review behavior MUST remain
  backward compatible; automatic injection MUST NOT confirm or mutate memories.
- **MEMCTX-012**: Provider requests, public events, traces, and Workbench activity
  MUST NOT expose unconfirmed memory content or raw retrieval exceptions.

## Decisions

- Retrieval remains lexical FTS for this milestone. The policy boundary allows a
  later hybrid/vector retriever without changing MiniPy.
- Memory context is an append-only system entry on the active branch. It is not a
  hidden global system prompt and is therefore inspectable during learning/debugging.
- The runtime emits an event even when zero memories match, making “no memory used”
  distinguishable from an unconfigured policy.
- Branch-scoped memory is explicitly denied rather than guessed from mutable leaf
  ids. A later feature may define durable branch identity and opt it in.
- Retrieval errors expose only `retrieval_error`; detailed local diagnostics remain
  outside model-visible and browser-visible payloads.

## Acceptance criteria

- **AC-MEMCTX-001**: Runtime tests prove context is prepared before the first model
  request, appears as a system message before the user prompt, emits a normalized
  event, and remains on the active entry path. (MEMCTX-001, MEMCTX-002, MEMCTX-007)
- **AC-MEMCTX-002**: Repository-backed tests prove only confirmed eligible global
  and matching-session memories are selected; every other status/scope is excluded
  and no row is mutated. (MEMCTX-003, MEMCTX-004, MEMCTX-011)
- **AC-MEMCTX-003**: Budget tests prove deterministic order, item/character bounds,
  provenance formatting, omitted/truncated metadata, and data-not-instructions
  framing. (MEMCTX-005, MEMCTX-006)
- **AC-MEMCTX-004**: Failure/cancellation tests prove safe fail-open retrieval,
  continued model execution, and normal cancellation propagation. (MEMCTX-008,
  MEMCTX-012)
- **AC-MEMCTX-005**: Trace, compaction, and fork tests prove context observability and
  append-only branch semantics. (MEMCTX-009)
- **AC-MEMCTX-006**: Composition tests prove browser, CLI, evaluation, suite, and CI
  paths receive the default policy while manual recall tests remain green.
  (MEMCTX-010, MEMCTX-011)
- **AC-MEMCTX-007**: Workbench source/browser tests render `context_injection`
  activity without interpreting memory text as HTML. (MEMCTX-007, MEMCTX-012)
- **AC-MEMCTX-008**: Lock consistency, lint, all tests, compilation, Pi smoke, live
  HTTP bridge smoke, and browser QA pass.
