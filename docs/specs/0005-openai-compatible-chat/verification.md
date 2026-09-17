# OpenAI-compatible chat verification

Verified: 2026-09-17

## Automated evidence

```bash
uv lock --check
# Resolved 33 packages; lock is current

uv run ruff check .
# All checks passed

uv run pytest
# 54 passed

python -m compileall -q src
# exit 0

uv run scholar-harness chat --help
# exit 0; documents model, endpoint, key-env, database, timeout, prompt, no-trace

uv run scholar-harness pi-smoke
# pi_rpc=ok, extension=ok
```

## Acceptance mapping

- **AC-CHAT-001**: `test_serializes_chat_tools_and_parses_tool_calls` inspects the
  mocked HTTP request and verifies model, authorization, messages, tool schema,
  parsed function arguments, content, and usage.
- **AC-CHAT-002**: `test_rejects_malformed_success_payloads`,
  `test_http_error_is_bounded_and_redacts_api_key`, and
  `test_rejects_invalid_local_messages_before_http` cover protocol and safe-error
  behavior.
- **AC-CHAT-003**:
  `test_one_shot_composition_exposes_tools_traces_and_closes` verifies the real CLI
  composition over a temporary SQLite database with all paper/memory tools, a
  completed trace, and resource cleanup. The adjacent failure test proves cleanup
  and failed trace status when the provider raises.
- **AC-CHAT-004**: `test_interactive_controls_and_tool_activity` and
  `test_eof_exits_interactive_chat` cover help, turns, tool notices, entries,
  compaction, valid/invalid forks, unknown commands, explicit exit, and EOF.
- **AC-CHAT-005**: `test_resolves_chat_configuration_without_raw_key_option` and
  `test_chat_configuration_requires_model` cover precedence, named secret lookup,
  disabled argument abbreviation, missing model, and invalid timeout.
- **AC-CHAT-006**: lock consistency, static checks, compilation, all 54 tests, CLI
  discovery, and the real Pi extension smoke test pass.

## Protocol source

The request and response mapping was checked against the official OpenAI Chat
Completions reference on 2026-09-17. Adapter tests use `httpx.MockTransport`; no
external model request or billable API call is part of verification.

## Known limitations

- Provider responses are non-streaming; normalized runtime events currently contain
  complete assistant text rather than token deltas.
- Chat Completions compatibility varies among local providers; malformed variants
  fail explicitly instead of being guessed silently.
- A Responses API adapter remains a separate future integration.
