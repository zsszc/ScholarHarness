# OpenAI-compatible model adapter and CLI chat

Status: Verified
Date: 2026-09-17

## Problem

`MiniPyRuntime` exposes the agent loop but currently only runs with test adapters.
Users need a real terminal entry point that can connect the loop to an OpenAI-style
Chat Completions endpoint, reuse the paper and memory tools, and persist traces
without placing provider credentials in code or logs.

## Requirements

- **CHAT-001**: Provide an async `OpenAICompatibleAdapter` implementing
  `ModelAdapter` against `POST /chat/completions`.
- **CHAT-002**: Serialize system, user, assistant, assistant tool-call, and tool
  result messages according to the Chat Completions function-tool shape.
- **CHAT-003**: Serialize every `ModelToolDefinition` as a function tool containing
  name, description, and JSON Schema parameters.
- **CHAT-004**: Parse assistant text, multiple function tool calls, JSON arguments,
  and usage into `ModelResponse` without executing tools in the adapter.
- **CHAT-005**: Malformed success payloads, empty choices, unsupported tool-call
  shapes, and invalid argument JSON MUST raise an explicit adapter protocol error.
- **CHAT-006**: Non-success HTTP responses MUST raise a bounded error containing the
  status and a response preview, never the authorization header or API key.
- **CHAT-007**: The adapter MUST support an optional API key, configurable base URL,
  model, request timeout, and injected async HTTP client for deterministic tests.
- **CHAT-008**: Add a `scholar-harness chat` command that composes the SQLite paper,
  memory, and trace repositories with `MiniPyRuntime` and the compatible adapter.
- **CHAT-009**: Chat configuration MUST read secrets from a named environment
  variable. The CLI MUST NOT accept the secret value as a command-line argument.
- **CHAT-010**: Interactive chat MUST display assistant deltas and concise tool
  activity, support `/compact`, `/fork`, `/entries`, `/help`, and `/exit`, and keep
  the session alive across prompts.
- **CHAT-011**: A one-shot `--prompt` mode MUST run one turn and exit for scripting
  and smoke tests.
- **CHAT-012**: Chat turns MUST be wrapped by `TracingRuntime` by default, with an
  explicit `--no-trace` opt-out.
- **CHAT-013**: Closing the chat command MUST close the runtime and HTTP client even
  after model or input failures.

## Decisions

- The adapter targets the widely implemented Chat Completions function-calling
  protocol rather than binding MiniPy to a vendor SDK. This supports OpenAI and
  compatible local servers while leaving a future Responses adapter independent.
- Requests are non-streaming at the provider boundary for this milestone. The
  runtime still emits normalized message events; token streaming is a later adapter
  capability.
- `httpx` becomes a runtime dependency and is injected in tests with `MockTransport`.
- Default base URL is `https://api.openai.com/v1`; model selection is mandatory via
  `--model` or `OPENAI_MODEL` because model availability varies by provider.
- Default secret environment variable is `OPENAI_API_KEY`. An empty key is valid for
  local endpoints that do not require authentication.
- The shared SQLite database remains `data/scholar_harness.db` unless overridden.

## Acceptance criteria

- **AC-CHAT-001**: A mocked endpoint receives correct messages, tool schemas,
  authorization, and model fields and returns parsed text, tool calls, and usage.
  (CHAT-001..004, CHAT-007)
- **AC-CHAT-002**: Invalid arguments, malformed response shapes, and HTTP failures
  raise bounded, credential-safe adapter errors. (CHAT-005, CHAT-006)
- **AC-CHAT-003**: One-shot CLI composition runs a fake model turn through
  `MiniPyRuntime`, exposes paper and memory tools, records a completed trace, and
  closes owned resources. (CHAT-008, CHAT-011..013)
- **AC-CHAT-004**: Interactive command tests cover help, compaction, fork, entry
  listing, tool activity, and clean exit. (CHAT-010)
- **AC-CHAT-005**: CLI parsing accepts endpoint/model/key-environment configuration,
  rejects a missing model clearly, and exposes no raw API-key option. (CHAT-007,
  CHAT-009)
- **AC-CHAT-006**: Static checks, compilation, all tests, and Pi smoke verification
  pass.
