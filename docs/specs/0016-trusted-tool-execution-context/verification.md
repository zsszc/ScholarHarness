# Trusted tool execution context verification

Status: Verified
Date: 2026-09-18

## Automated verification

```text
uv lock --check: resolved 33 packages
uv run ruff check .: all checks passed
uv run pytest: 117 passed, 2 upstream warnings in 1.25s
python -m compileall -q src: exit 0
uv run scholar-harness pi-smoke: pi_rpc=ok, extension=ok, entry_count=1
uv run scholar-harness pi-smoke --check-service:
  pi_rpc=ok, extension=ok, tool_service=ok, entry_count=2
```

## Acceptance evidence

- **AC-TOOLCTX-001**:
  `test_registry_passes_context_separately_without_changing_schema` proves separate
  contextual invocation, legacy-compatible absence, and unchanged JSON Schema.
  Extra-field validation proves model arguments cannot carry provenance.
- **AC-TOOLCTX-002**:
  `test_traced_runtime_supplies_trusted_tool_execution_context` proves runtime type,
  session, assistant entry, call, and trace-run identity plus post-run cleanup.
  `test_trace_execution_binding_is_task_local_and_resets` proves concurrent task
  isolation and exception cleanup.
- **AC-TOOLCTX-003**:
  `test_memory_provenance_comes_only_from_execution_context` proves scoped calls
  fail without context, spoofed JSON fails, all trusted coordinates persist, and a
  confirmed session memory is recalled only by its owning session.
- **AC-TOOLCTX-004**:
  `test_pi_extension_hides_and_forwards_memory_provenance` verifies the Pi schema and
  session/call header source. Both real Pi extension smoke tests pass.
- **AC-TOOLCTX-005**: `test_http_tool_context_owns_memory_provenance` proves direct
  scoped rejection, spoof rejection, typed header propagation, and persisted values.
- **AC-TOOLCTX-006**: Lock consistency, lint, all 117 tests, compilation, both Pi
  smokes, live HTTP bridge, and browser QA passed. Browser QA displayed the session
  candidate with `run qa-run-0016 · tool qa-call-0016` without confirming it.

## Boundary result

Tool business arguments and harness execution identity are now separate contracts.
MiniPy, tracing, Pi, and HTTP supply provenance outside model-visible schemas;
memory persistence ignores client-authored provenance and scoped memories require a
runtime owner. Task-local trace binding prevents concurrent provenance cross-talk.
