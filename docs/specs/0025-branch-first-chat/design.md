# Design: branch-first research chat

## Projection

Keep MiniPy's append-only `AgentEvent` list as the source of truth. A pure Python
projector groups each `message(role=user)` into a turn. Its parent is the nearest
user ancestor, skipping context, assistant, tool and compaction entries. Its
continuation anchor is the last entry in the turn's own chain before another user
message. The active path is calculated by following the persisted active leaf's
parent links. The graph endpoint returns only projected public entry content;
provider configuration is not read or returned.

## UI

The graph appears before the composer. Nodes are laid out by depth and sibling
index using CSS, with explicit parent connectors and accessible buttons; this
bounded first milestone does not claim PiX's infinite canvas or parallel runtimes.
Clicking a node only changes the selected view. "Continue" calls the existing
fork command with the node's continuation anchor, whereas "Retry" forks at the
user entry. Both operations are explicit and server-authoritative. Browser chat
refreshes from the graph after reconnect, commands, and completed turns.

## Limits

This is a durable MiniPy interaction milestone. Pi RPC remains separately usable,
but this page does not claim to host Pi sessions. Concurrent independent branch
runtimes and side-by-side panes are future milestones.

