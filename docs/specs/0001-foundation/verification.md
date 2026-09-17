# Foundation verification

Verified: 2026-09-17

## Automated evidence

```bash
uv run ruff check .
# All checks passed

uv run pytest
# 18 passed

python -m compileall -q src
# exit 0

uv run scholar-harness pi-smoke
# pi_rpc=ok, extension=ok
```

Coverage includes:

- request/response correlation and event streaming against a fake Pi process;
- session tree projection and branching paths;
- SQLite paper persistence, replacement, and FTS retrieval;
- PDF validation, normalization, page coordinates, and chunk bounds;
- API paper upload and tool execution;
- rejection of fabricated memory evidence;
- candidate invisibility before confirmation and confirmed-only recall;
- persistence of memory status and evidence.

## Integration evidence

Pi `0.85.1` was installed from `@earendil-works/pi-coding-agent`. With the Python
API running, the real RPC command `/scholar-health` loaded the extension and returned
`ScholarHarness Python service is healthy` after an HTTP 200 response.

## Known limitations

- Full model-driven tool selection was not verified because no Pi provider credential
  was configured in the development environment.
- FastAPI's test client emits two dependency deprecation warnings; they do not affect
  behavior or test results.
