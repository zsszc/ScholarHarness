# OpenAI-compatible chat design

## Components

```text
terminal input
     |
chat command
     |-- OpenAICompatibleAdapter -- HTTP --> /chat/completions
     |-- MiniPyRuntime
     |     `-- paper + memory ToolRegistry
     `-- TracingRuntime --------------------> SQLite traces
```

## Protocol mapping

The adapter maps internal messages to the Chat Completions wire format:

| Internal role | Wire fields |
| --- | --- |
| system/user | `role`, `content` |
| assistant text | `role`, `content` |
| assistant calls | `role`, `content`, `tool_calls[].function` |
| tool result | `role=tool`, `content`, `tool_call_id` |

Tool definitions become `{"type":"function","function":{...}}`. The request uses
`tool_choice="auto"` when tools exist. The adapter parses function arguments from a
JSON object string and refuses non-object values because `ToolRegistry` expects a
mapping.

The mapping follows the official OpenAI Chat Completions reference consulted on
2026-09-17:
`https://developers.openai.com/api/reference/cli/resources/chat/subresources/completions`.

## HTTP and secret boundary

The adapter builds an `httpx.AsyncClient` only when a client is not injected. It
owns and closes only clients it creates. Authorization is added only when an API key
is non-empty. Protocol errors expose no request headers; HTTP body previews are
capped at 1 KiB.

The URL is normalized by removing trailing slashes and appending
`/chat/completions`. Timeouts and transport errors become `ModelAdapterError` with a
stable category.

## CLI composition

The command creates one paper repository and one memory repository over the selected
SQLite file, merges both tool registries, creates `MiniPyRuntime`, and normally wraps
it with `TracingRuntime(runtime_type="mini-py-openai-compatible")`.

Configuration precedence is explicit CLI option, then environment, then documented
default. Only an environment-variable *name* is accepted for secrets.

## Interactive control commands

- `/help`: show commands.
- `/compact [instructions]`: append a compaction node.
- `/fork ENTRY_ID`: select a branch leaf.
- `/entries`: print stable entry ids, parents, types, and roles.
- `/exit` or `/quit`: close cleanly.

Other non-empty input becomes a model turn. Assistant message deltas are printed;
tool start/end events show names and success/error without dumping large results.

## Failure modes

- Missing model configuration fails before creating an HTTP client.
- EOF behaves like `/exit`.
- Adapter/model failures are reported to stderr by the CLI entry point and still
  trigger resource cleanup.
- A malformed provider response never reaches the runtime as a partial response.
