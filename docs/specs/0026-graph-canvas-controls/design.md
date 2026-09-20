# Design: interactive research graph canvas

Use a fixed-height viewport and a single transformed graph stage. Nodes and SVG
edges share logical coordinates; a `translate(x, y) scale(s)` transform moves and
scales both together. Pointer deltas for node dragging divide by `s`.

Keep layout overrides in browser localStorage under a session-specific key. This
is a visual preference, not server session data; no prompts, answers or provider
credentials are stored. A malformed or unavailable storage entry falls back to
automatic layout. Preserve graph state during re-renders and reset when changing
session. A reset clears node overrides, then fits the auto layout.

Pointer capture keeps drags stable outside the node. A small movement threshold
separates click from drag. Panning starts on empty viewport/stage space. Zoom uses
the pointer or viewport center as its anchor, clamped to 40–250%. A fit action
uses node bounds with padding. Toolbar buttons make zoom accessible without a
wheel/gesture device.

The change is confined to the Workbench HTML/CSS/JS. The Pi bridge and HTTP graph
contract stay unchanged.
