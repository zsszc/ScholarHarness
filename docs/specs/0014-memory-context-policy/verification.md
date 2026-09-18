# Memory context policy verification

Status: Verified
Date: 2026-09-18

## Automated verification

```text
UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv lock --check
Resolved 33 packages

UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv run ruff check .
All checks passed!

UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv run pytest
107 passed, 2 warnings in 1.24s

python -m compileall -q src
exit 0

UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache uv run scholar-harness pi-smoke
pi_rpc=ok, extension=ok, entry_count=1

UV_CACHE_DIR=/private/tmp/scholar-harness-uv-cache \
  uv run scholar-harness pi-smoke --check-service
pi_rpc=ok, extension=ok, tool_service=ok, entry_count=2
```

The two warnings are upstream Starlette test-client deprecations.

## Acceptance evidence

- **AC-MEMCTX-001**:
  `test_injects_prepared_context_before_user_message_and_traces_decision` proves
  provider input, event order, append-only context entry, and system-before-user
  model messages.
- **AC-MEMCTX-002**:
  `test_policy_selects_only_confirmed_memories_in_allowed_scope` uses the real
  SQLite/FTS repository to admit only global and matching-session confirmed rows,
  exclude other sessions/branch/unconfirmed statuses, and preserve candidate state.
- **AC-MEMCTX-003**: The scope test proves evidence-coordinate and
  data-not-instructions framing. `test_policy_enforces_item_and_character_budgets`
  proves the hard character/item bound plus selected, omitted, and truncated
  metadata. Repeated preparation proves deterministic ordering, backed by stable
  `(rank, created_at, id)` repository ordering.
- **AC-MEMCTX-004**: `test_context_failure_is_safe_and_does_not_block_model`
  verifies the stable `retrieval_error` category, normalized zero counts, no raw
  exception disclosure, and continued model execution.
  `test_cancelling_turn_cancels_context_retrieval` proves cancellation propagation.
- **AC-MEMCTX-005**:
  `test_context_entries_follow_forks_and_compaction_without_rewrite` proves branch
  path isolation, preservation of sibling context entries, and post-compaction
  ordering. The CLI composition test reads the persisted `context_injection` trace.
- **AC-MEMCTX-006**: `test_cli_chat_automatically_injects_confirmed_memory`,
  `test_default_api_chat_uses_memory_context_policy`, and
  `test_evaluation_entry_points_compose_default_memory_policy` cover CLI, browser
  chat, case, suite, and therefore CI-gate composition. Existing memory tool/API
  tests remain green.
- **AC-MEMCTX-007**: `test_workbench_chat_uses_server_session_gateway` asserts the
  explicit safe-DOM activity branch. Browser QA loaded a completed
  `memory-context-browser-qa` run and visibly rendered the `context_injection`
  timeline with selected id/count/content and no tool calls.
- **AC-MEMCTX-008**: Lock consistency, lint, all 107 tests, compilation, Pi RPC
  smoke, live extension-to-service smoke, and browser QA passed.

## Boundary result

MiniPy now accepts generic prepared turn context without importing memory policy.
The default `MemoryContextPolicy` is shared by interactive and evaluation paths,
admits only explicitly confirmed in-scope records, applies bounded deterministic
formatting, and leaves both its injected snapshot and its decision metadata
inspectable in session branches and durable traces.
