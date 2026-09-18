# Runtime parity reports verification

Status: Verified
Date: 2026-09-18

## Automated verification

```text
uv lock --check: resolved 33 packages
uv run ruff check .: all checks passed
uv run pytest: 138 passed, 2 upstream warnings in 1.59s
python -m compileall -q src: exit 0
uv run scholar-harness pi-smoke: pi_rpc=ok, extension=ok, entry_count=1
```

## Acceptance evidence

- **AC-PARITY-001**:
  `test_pi_and_minipy_shapes_project_to_semantic_parity` persists traces with
  different runtime/session/entry/tool-call ids, timestamps, provider fields, and
  Pi `text` versus MiniPy `delta` payloads, and different streaming chunk counts.
  Their semantic snapshots compare equal.
- **AC-PARITY-002**: The same test proves different assistant prose passes default
  output-presence comparison, is absent from the default report, and fails the
  named strict exact-output check with explicit observations.
- **AC-PARITY-003**:
  `test_parity_cli_json_exit_codes_and_unknown_runs` proves versioned JSON, exit 0,
  strict mismatch exit 1, and unknown-run usage exit 2.
- **AC-PARITY-004**:
  `test_parity_report_explains_tool_mismatch` changes only the tool name and proves
  the aggregate fails with left/right tool observations.
- **AC-PARITY-005**: Lock consistency, lint, all 138 tests, compilation, and the
  real offline Pi RPC/extension smoke passed.

## Boundary result

Persisted Pi and MiniPy runs can now be compared through one versioned behavioral
contract without coupling their execution loops. Reports are deterministic enough
for CI while avoiding false failures from volatile identity, timing, provider
payloads, or nondeterministic prose.
