# Browser chat session gateway design

## Architecture

```text
Workbench Chat page
  |-- REST /chat/sessions       create/list/inspect/delete
  `-- WS /chat/sessions/{id}/stream
        |-- command receiver    prompt/abort/compact/fork/entries
        `-- single sender       ordered events/results/errors
              |
        ChatSessionManager
              |
        ChatSession -> TracingRuntime -> MiniPyRuntime -> ModelAdapter
                              `-> durable TraceRepository
```

`ChatSessionManager` owns an in-memory map protected by an async lock. It receives
the application's existing tool registry and trace repository, plus a provider
adapter factory. Every created session gets a new runtime and adapter while sharing
the same trusted server-side tools.

## Configuration and API boundary

The default factory reads `OPENAI_MODEL`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and
`OPENAI_TIMEOUT_SECONDS` when the application is built. If the model is absent,
the manager remains available for discovery but rejects creation with a typed
configuration error translated to HTTP 503.

Session summaries contain operational metadata only. The create request has no
provider fields, preventing credentials from crossing the browser boundary and
preventing clients from selecting an arbitrary upstream URL.

## WebSocket protocol

Client messages are JSON objects with a `type` field:

- `prompt` with non-empty `content` starts a turn;
- `abort` requests cooperative cancellation;
- `compact` may include an optional instruction;
- `fork` selects an existing entry id as the active leaf;
- `entries` requests the current branch entries.

Server messages use `session_ready`, `event`, `turn_complete`, `command_result`,
and `error`. Error objects include a stable code and readable message. Runtime
events retain the existing discriminated schema, so the workbench and tests can
inspect message, tool, lifecycle, and error events without a second event model.

A receive loop remains responsive while a separate turn task iterates the runtime.
All outbound frames pass through one queue and sender task to preserve order and
avoid concurrent WebSocket writes. A second prompt is rejected while that task is
active. Disconnect cleanup requests abort and awaits the turn before preserving the
session for reconnect.

## Lifecycle and failure modes

- Session deletion removes the session under the manager lock, then closes it.
- Session close is guarded and calls runtime shutdown before adapter `aclose` when
  available.
- Application lifespan closes all remaining sessions.
- Provider/runtime exceptions become a WebSocket error followed by turn completion
  state; they do not crash the service.
- Commands that mutate the branch are rejected while a turn is active.
- Unknown session REST requests return 404 and unknown WebSocket sessions close
  with application code 4404.

## Workbench integration

Chat becomes a fifth route in the existing self-contained page. The page creates a
session through REST, then derives a same-origin `ws:` or `wss:` URL. It renders
conversation bubbles and a separate activity stream using element construction and
`textContent`. Controls are enabled from connection and busy state, not optimistic
assumptions. The page keeps a session id in memory only and offers explicit new,
reconnect, and delete actions.

## Trade-offs

Keeping sessions in one process makes lifecycle semantics understandable and easy
to demonstrate in an interview, but sessions disappear on restart and do not span
workers. Provider streaming is not added to the adapter contract in this milestone;
the normalized runtime event boundary is kept stable so token streaming can be
introduced later without changing session commands.
