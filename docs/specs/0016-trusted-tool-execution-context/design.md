# Trusted tool execution context design

## Flow

```text
TracingRuntime -- task-local trace binding --+
                                            |
MiniPyRuntime -- session/entry/call --------+--> ToolExecutionContext
                                                   |
                                             ToolRegistry.execute
                                                   |
                                              save_memory

Pi Extension -- ctx.sessionManager/toolCallId --> HTTP provenance headers
                                                   |
                                             ToolRegistry.execute
```

`Tool` declares whether its handler accepts context. The registry validates normal
arguments exactly as before, then passes a separate immutable context object only to
context-aware handlers. It never merges context into arguments or schemas.

`TracingRuntime.stream()` binds `(run_id, runtime_type)` in a `ContextVar` around the
inner stream and resets the token in `finally`. MiniPy combines that binding with
its own session id, the assistant entry that emitted the call, and the call id.

## Memory boundary

`SaveMemoryInput` contains only semantic content, kind, scope, confidence, and
evidence. `save_memory` copies provenance exclusively from `ToolExecutionContext`.
A missing context is valid only for global scope and produces nullable provenance.
Session and branch scopes fail before persistence when runtime ownership is absent.

The Pi bridge uses the fifth tool-execute argument (`ExtensionContext`) and its
read-only session manager. Provenance travels as dedicated headers, not request JSON,
and the FastAPI route constructs the same typed context used by MiniPy.

## Failure and concurrency

Context validation occurs before handler execution. Existing structured runtime
tool errors therefore remain unchanged. Context variables are task-local and reset
even when the inner stream raises, is cancelled, or is closed, preventing one run's
trace id from leaking into another concurrent execution.
