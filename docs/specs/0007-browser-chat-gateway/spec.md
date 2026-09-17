# Browser chat session gateway

Status: Approved
Date: 2026-09-17

## Problem

ScholarHarness can run a traced MiniPy agent from the CLI and inspect completed
runs in the workbench, but the browser cannot yet drive the same runtime. A local
session gateway should expose the agent loop as an inspectable, interruptible
conversation without sending provider credentials or arbitrary provider URLs to
the browser.

## Requirements

- **CHAT-001**: The service MUST create long-lived, in-memory chat sessions backed
  by an independent `MiniPyRuntime` and the existing tracing decorator.
- **CHAT-002**: Provider model, base URL, API key, and timeout MUST be read from the
  server environment; browser requests MUST NOT accept or expose credentials or a
  provider base URL.
- **CHAT-003**: The HTTP API MUST create, list, inspect, and delete sessions and
  return stable session metadata without secret fields.
- **CHAT-004**: Each session MUST expose a WebSocket endpoint that emits normalized
  runtime events in order and accepts prompt commands.
- **CHAT-005**: The WebSocket MUST accept abort, compact, fork, and entry-list
  commands in addition to prompts, with explicit success or error messages.
- **CHAT-006**: A session MUST reject a second prompt while a turn is active and
  MUST report malformed or unknown commands without terminating the connection.
- **CHAT-007**: Disconnecting a WebSocket during a turn MUST abort that turn while
  preserving the session for a later reconnect.
- **CHAT-008**: Deleting a session and shutting down the application MUST close its
  runtime and provider adapter exactly once; deletion MUST be idempotent from the
  manager's perspective.
- **CHAT-009**: Session metadata MUST report session id, creation time, busy state,
  entry count, active leaf, and last trace run id.
- **CHAT-010**: The workbench MUST add a Chat area with connection state,
  conversation messages, live runtime/tool activity, prompt submission, abort,
  compact, fork, reconnect, new-session, and delete controls.
- **CHAT-011**: Chat data MUST use safe DOM text insertion and every chat operation
  MUST present a visible pending, success, empty, disconnected, or error state.
- **CHAT-012**: When provider configuration is absent, session creation MUST fail
  with a clear `503` response while the rest of the service remains available.

## Decisions

- Sessions are process-local and intentionally disposable; durable learning comes
  from the existing trace and memory stores. Multi-process routing and restoration
  are deferred.
- One WebSocket owns a session's active interaction at a time, and only one model
  turn may run per session. Reconnection is supported after disconnect.
- The provider adapter may complete a model request before yielding its normalized
  message event. Runtime and tool events are still forwarded immediately as they
  occur.
- The gateway is localhost-oriented and adds no authentication. Public deployment,
  authorization, rate limits, and session TTL are out of scope.
- The browser cannot override server provider configuration. This keeps API keys
  server-side and avoids an arbitrary outbound-request surface.

## Acceptance criteria

- **AC-CHAT-001**: REST tests create, list, inspect, and delete isolated sessions;
  returned data contains no credential or provider URL. (CHAT-001..003, CHAT-009)
- **AC-CHAT-002**: WebSocket tests execute a prompt through a scripted tool loop and
  receive ordered normalized runtime events plus completion metadata. (CHAT-004)
- **AC-CHAT-003**: Tests cover concurrent prompt rejection, malformed commands,
  abort, compact, fork, entry listing, disconnect, and reconnect behavior.
  (CHAT-005..007)
- **AC-CHAT-004**: Lifecycle tests prove explicit deletion and application shutdown
  release runtime and adapter resources without double-close failures. (CHAT-008)
- **AC-CHAT-005**: Missing provider configuration produces `503`; configured
  sessions use server settings without browser-supplied connection parameters.
  (CHAT-002, CHAT-012)
- **AC-CHAT-006**: Workbench source and browser tests verify the Chat area, controls,
  live state transitions, responsive layout, and safe DOM rendering. (CHAT-010,
  CHAT-011)
- **AC-CHAT-007**: Lock consistency, lint, compilation, all tests, Pi smoke, live
  service smoke, and browser interaction checks pass.
