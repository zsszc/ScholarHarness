# Observability workbench verification

Verified: 2026-09-17

## Automated evidence

```bash
uv lock --check
# Resolved 33 packages; lock is current

uv run ruff check .
# All checks passed

uv run pytest
# 58 passed

python -m compileall -q src
# exit 0

uv run scholar-harness pi-smoke
# pi_rpc=ok, extension=ok

SCHOLAR_HARNESS_URL=http://127.0.0.1:8768 \
  uv run scholar-harness pi-smoke --check-service
# pi_rpc=ok, extension=ok, tool_service=ok

curl -fsS http://127.0.0.1:8768/workbench
# 200; complete self-contained HTML document

curl -fsS 'http://127.0.0.1:8768/papers?limit=2'
# 200; deterministic paper summary JSON
```

## Acceptance mapping

- **AC-UI-001**: `test_workbench_contains_all_areas_and_no_external_assets`
  verifies all four pages, navigation, CSP, and the absence of external scripts,
  stylesheets, and URLs. Browser QA verified the responsive research-console shell.
- **AC-UI-002**: Existing trace API tests plus live overview and run-panel requests
  verify stable run, event, and tool data contracts.
- **AC-UI-003**: Existing memory API workflow tests and workbench source assertions
  verify candidate filtering and explicit confirm/reject endpoints.
- **AC-UI-004**: `test_in_memory_catalog_is_deterministic_and_limited`,
  `test_paper_catalog_is_deterministic_and_limited`, and `test_health_and_tool_flow`
  verify both repository implementations and HTTP catalog. Live browser QA executed
  hybrid search and displayed paper/passage/page plus lexical/vector ranks.
- **AC-UI-005**: `test_workbench_uses_safe_dom_and_explicit_panel_states` proves
  persisted content uses `textContent`/`replaceChildren`, not `innerHTML`, and checks
  loading/empty/error state definitions.
- **AC-UI-006**: `test_home_page_and_invalid_pdf` verifies the home link and
  workbench response.
- **AC-UI-007**: lock consistency, static checks, compilation, all 58 tests, real Pi
  loading, live service bridge, HTTP smoke, and browser interaction pass.

## Manual browser evidence

- Desktop layout rendered at 1280×720 without overflow or missing assets.
- Navigation switched from Overview to Library without page reload.
- The catalog displayed the seeded paper and passage count.
- A `tools schemas` hybrid query returned a citable passage with both component
  ranks.
- Browser accessibility state exposed semantic navigation, buttons, labels, form
  fields, headings, and result text.

## Known limitations

- The workbench is localhost-only and has no authentication or public deployment
  hardening.
- Browser chat/session hosting is deliberately deferred to a separate lifecycle
  milestone.
- Overview computes tool totals from loaded runs, which is appropriate for a
  personal corpus but will later need an aggregate endpoint for large histories.
