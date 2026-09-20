# Interactive research graph canvas

Status: Approved
Date: 2026-09-20

## Problem

The Agent chat graph uses a fixed layout in a scroll box. Users cannot arrange turns
or scale the graph to inspect a large conversation.

## Requirements

- **CANVAS-001**: A pointer drag on a turn node MUST move only that node, update
  its connected edges during the drag, and MUST NOT select or fork the turn.
- **CANVAS-002**: A click or keyboard activation on a turn node MUST still select
  that turn without moving it or changing the active model branch.
- **CANVAS-003**: The graph MUST support whole-canvas zoom, background panning,
  a fit-to-view action, and a visible zoom percentage. Zoom MUST be bounded.
- **CANVAS-004**: Node coordinates and viewport zoom/pan MUST survive graph refresh
  and page reload for the same session, without leaking across sessions. A reset
  action MUST restore automatic node placement.
- **CANVAS-005**: The controls MUST be labeled in Chinese, remain usable with
  keyboard buttons, and preserve safe text rendering and existing chat actions.

## Acceptance criteria

- **AC-CANVAS-001**: Browser interaction confirms drag repositions a node and
  edge, but does not select it; click still selects. (CANVAS-001, 002)
- **AC-CANVAS-002**: Browser interaction confirms zoom buttons, wheel, background
  pan and fit action affect the entire graph; zoom respects bounds. (CANVAS-003)
- **AC-CANVAS-003**: Refresh/reload restores saved positions and viewport per
  session; reset restores automatic layout. (CANVAS-004)
- **AC-CANVAS-004**: Regression checks and repository quality gates pass.
  (CANVAS-001..005)
