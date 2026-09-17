# Browser chat session gateway verification

Verified: 2026-09-17

## Automated evidence

```bash
uv lock --check
# Resolved 33 packages; lock is current

uv run ruff check .
# All checks passed

uv run pytest
# 67 passed

python -m compileall -q src
# exit 0

uv run scholar-harness pi-smoke
# pi_rpc=ok, extension=ok

SCHOLAR_HARNESS_URL=http://127.0.0.1:8768 \
  uv run scholar-harness pi-smoke --check-service
# pi_rpc=ok, extension=ok, tool_service=ok
```

The focused browser-chat suite covers seven manager/API/WebSocket scenarios plus the
workbench source contract. The full suite includes all prior runtime, repository,
trace, retrieval, memory, Pi, and UI regression tests.

## Acceptance mapping

- **AC-CHAT-001**: `test_manager_lifecycle_and_metadata_are_secret_free` and
  `test_chat_rest_and_scripted_websocket_tool_loop` verify isolated creation,
  deterministic listing, inspection, idempotent deletion, metadata, and the absence
  of credential/provider URL fields.
- **AC-CHAT-002**: `test_chat_rest_and_scripted_websocket_tool_loop` executes a
  two-model-round echo tool call and asserts the complete ordered normalized event
  sequence and trace run id.
- **AC-CHAT-003**: `test_websocket_rejects_second_prompt_and_aborts_on_command`,
  `test_websocket_disconnect_aborts_turn_and_preserves_session`, and the scripted
  socket workflow verify concurrency rejection, abort, compact, fork, entries,
  unknown commands, disconnect cleanup, and reconnect.
- **AC-CHAT-004**: `test_manager_lifecycle_and_metadata_are_secret_free` proves
  explicit deletion, repeated deletion, and manager shutdown close adapters once;
  every `TestClient` context also exercises FastAPI lifespan cleanup.
- **AC-CHAT-005**: `test_missing_server_configuration_is_explicit` and
  `test_missing_configuration_returns_503_without_breaking_service` verify that
  missing server configuration is isolated to chat creation and that request
  payloads cannot override it.
- **AC-CHAT-006**: `test_workbench_chat_uses_server_session_gateway` and existing
  safe-DOM assertions cover the Chat route, all five commands, server-only
  configuration, WebSocket construction, and `textContent` rendering. Manual
  browser QA covers interaction and responsive presentation.
- **AC-CHAT-007**: lock consistency, lint, all 67 tests, compilation, real Pi RPC,
  live extension-to-service smoke, and browser QA pass.

## Manual browser evidence

- With no `OPENAI_MODEL`, the Chat page remained usable and displayed the server's
  explicit configuration message after session creation returned 503.
- With a temporary server-side model configuration, the page created a session,
  connected its same-origin WebSocket, enabled controls, submitted a prompt, and
  displayed its user message and runtime state transitions.
- A deliberately unavailable provider produced a durable failed trace and a final
  visible error state containing the trace id; the subsequent completion frame did
  not overwrite the error.
- Entry refresh populated the fork selector with the stable user entry.
- The default desktop layout and a 390×844 viewport rendered without horizontal
  overflow; the Chat columns collapsed to one column at the narrow breakpoint.

## Known limitations

- Live sessions are process-local and disappear on API restart; traces remain
  durable. Multi-worker routing, restoration, and idle TTL are deferred.
- The current adapter returns complete model responses, so text arrives as one
  normalized message event rather than token deltas.
- The gateway is localhost-only and has no authentication or public deployment
  hardening.
