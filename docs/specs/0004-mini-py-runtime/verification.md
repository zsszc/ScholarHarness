# MiniPyRuntime verification

Verified: 2026-09-17

## Automated evidence

```bash
uv run ruff check .
# All checks passed

uv run pytest
# 41 passed

python -m compileall -q src
# exit 0

uv run scholar-harness pi-smoke
# pi_rpc=ok, extension=ok
```

## Acceptance mapping

- **AC-MINIPY-001**: `test_executes_tool_loop_and_appends_replayable_entries`
  verifies schemas, two model steps, validated execution, correlated events, and the
  parent-linked user/assistant/tool/assistant entry chain.
- **AC-MINIPY-002**: `test_tool_failures_become_model_observations` covers unknown
  tools, invalid arguments, and handler exceptions as structured observations.
- **AC-MINIPY-003**: `test_stops_repeating_model_at_tool_round_limit` proves the
  configured bound and explicit `max_tool_rounds` terminal error.
- **AC-MINIPY-004**: `test_abort_cancels_blocked_model_and_settles_turn` and
  `test_abort_cancels_blocked_tool_and_closes_trace_event` prove cancellation and
  correlated abort settlement for both await types.
- **AC-MINIPY-005**:
  `test_fork_preserves_sibling_branches_and_scopes_context` verifies sibling
  preservation, selected-path context, and incremental append-log replay.
- **AC-MINIPY-006**:
  `test_compaction_replaces_active_model_context_but_preserves_entries` verifies a
  visible summary node, complete history retention, and context reset.
- **AC-MINIPY-007**: `test_lifecycle_and_unknown_entries_are_rejected` and
  `test_concurrent_turn_is_rejected` cover misuse errors.
- **AC-MINIPY-008**: static checks, compilation, all 41 automated tests, and the
  real Pi extension smoke test pass.

## Additional integration evidence

`test_tracing_runtime_respects_normalized_terminal_status` proves failed MiniPy
turns remain failed when wrapped by the runtime-neutral trace decorator.

## Known limitations

- Session entries are in memory; use `TracingRuntime` for durable normalized traces.
- Compaction uses a deterministic bounded transcript summary rather than a learned
  summarizer.
- The core defines the provider boundary but does not bundle a vendor model SDK.
- Tool calls execute sequentially for deterministic branching and trace order.
