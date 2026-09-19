# Branch-first research chat

Status: Approved
Date: 2026-09-19

## Problem

The current Workbench hides its durable MiniPy session tree behind a dropdown and
an append-only chat log. A fork changes model context but the visible transcript
does not follow that branch, making the interaction misleading. PiX's central
interaction is a graph whose selected path determines the conversation.

## Requirements

- **GRAPH-001**: Project a session's persisted entries into one turn node per
  user message, connecting each node to its nearest user-message ancestor.
- **GRAPH-002**: Each turn MUST contain its user prompt, subsequent assistant/tool
  content on its path before the next user turn, a stable continuation entry id,
  and whether it lies on the active leaf's ancestry.
- **GRAPH-003**: The browser MUST display the turn graph as the primary chat
  navigation, distinguish selected and active nodes, and show only the selected
  turn's ancestor-path conversation.
- **GRAPH-004**: Selecting a node MUST be read-only. Explicit actions MUST allow
  continuing from that turn's completed context or retrying its user prompt from
  before the answer; neither may silently erase another branch.
- **GRAPH-005**: A successful fork MUST refresh the graph, selected path, and
  active leaf. A completed turn or reconnect MUST do the same.
- **GRAPH-006**: The selected turn's inspector MUST show its tool calls/results and
  metadata without interpreting model-controlled content as HTML.
- **GRAPH-007**: The UI MUST clearly label the graph as MiniPy-backed, not Pi-native.

## Acceptance criteria

- **AC-GRAPH-001**: Projection tests cover a linear history, sibling forks,
  context/tool entries, active leaf and historical selection. (GRAPH-001, 002)
- **AC-GRAPH-002**: API tests prove the graph contract contains no credentials,
  session mutations or incorrect cross-branch messages. (GRAPH-001, 003, 004)
- **AC-GRAPH-003**: Browser QA proves selecting and switching branches changes the
  transcript, and explicit fork/continuation changes the active leaf. (GRAPH-003..007)
- **AC-GRAPH-004**: Full repository quality gates and Pi bridge smoke pass.

