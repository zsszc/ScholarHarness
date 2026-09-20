# Verification: interactive research graph canvas

Status: Verified
Date: 2026-09-20

## Automated evidence

- `uv run ruff check .`: passed.
- `uv run pytest`: 162 passed; two dependency deprecation warnings.
- `python -m compileall -q src`: passed.
- `uv run scholar-harness pi-smoke`: Pi RPC and extension passed.
- Embedded Workbench JavaScript parsed with Node `vm.Script`.
- Workbench regression checks cover pointer capture, click suppression, zoom
  bounds, session-specific storage key, fit/reset controls, and safe branch
  selection. No Pi bridge or HTTP boundary changed.

## Browser evidence

- In a two-turn local test session, dragged the first node; its rendered
  coordinates and SVG edge changed, while selection stayed on the second turn.
  Clicking the first turn then selected it normally; clicking the second
  restored the active path. (AC-CANVAS-001)
- Fit view showed both connected nodes; toolbar zoom changed the entire stage
  from 109% to 137%; dragging blank canvas changed stage translation; wheel
  zoom clamped at 40%. (AC-CANVAS-002)
- A reload restored the dragged coordinate and 137% scale/pan. Reset returned
  the first node to its automatic (20, 16) position and fitted the graph.
  Storage is keyed by session id and contains only visual coordinates. The
  per-session isolation is covered by the key construction regression check.
  (AC-CANVAS-003)
- Final page reload displayed two nodes with the new controls and no script
  errors; manual fit restored a readable view. (AC-CANVAS-004)
