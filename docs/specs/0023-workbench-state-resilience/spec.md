# Workbench state resilience

Status: Verified
Date: 2026-09-19

## Bug

Detail renderers replace their initial `data-state` placeholder. A later refresh
calls `setPanelState` for that detail before rendering, receives no matching node,
and throws while reading `dataset`. The enclosing loader then displays a false list
failure even though API data loaded successfully.

## Requirements

- **UISTATE-001**: `setPanelState` MUST recreate a missing state node inside the
  same-id panel host before updating it.
- **UISTATE-002**: If neither state node nor host exists, the helper MUST return
  safely without masking the caller's real operation.
- **UISTATE-003**: Repeated run-list refresh and detail selection MUST not display a
  false JavaScript error.

## Acceptance criteria

- **AC-UISTATE-001**: Source regression tests verify missing-node recreation and
  null-safe fallback. (UISTATE-001, 002)
- **AC-UISTATE-002**: Browser QA refreshes the run list after a rendered detail and
  shows loaded runs without the prior error. (UISTATE-003)
- **AC-UISTATE-003**: Full repository verification and Pi smoke pass.
