# Observability workbench design

## Information architecture

```text
Workbench shell
  |-- Overview: metric cards + recent runs
  |-- Runs: run list -> event timeline + tool inspector
  |-- Memory: status filters -> evidence/provenance -> confirm/reject
  `-- Library: paper catalog + lexical/hybrid passage search
```

## Backend additions

`PaperSummary` is a response model owned by the papers domain. `PaperRepository`
adds `list(limit)`:

- in-memory storage sorts by `(title.casefold(), id)` and counts passages;
- SQLite performs one grouped query and the same deterministic ordering;
- `GET /papers?limit=` exposes the summaries.

All other workbench operations reuse existing APIs. No UI-only database access or
duplicated memory policy is introduced.

## Frontend structure

`workbench.py` owns a constant HTML document returned by FastAPI. Its embedded ES
module uses a small state object and these request helpers:

- `loadOverview()` fetches runs, memories, papers, and selected tool lists;
- `loadRuns()` and `selectRun(id)` load run metadata, events, and tools;
- `loadMemories(status)` renders review cards and calls confirm/reject endpoints;
- `loadLibrary()` fetches papers and submits `search_papers`.

Navigation toggles `hidden` sections and updates `aria-current`. Data renderers
construct elements and set `textContent`; they never concatenate backend fields into
`innerHTML`. Fixed application chrome is part of the static HTML document.

## Visual system

- dark ink background with warm paper panels and a cyan/lime status accent;
- monospaced coordinates and event payloads, humanist system font for prose;
- left rail on desktop, top-wrapped navigation below 820 px;
- compact status pills for completed/running/failed/aborted and memory states;
- reduced-motion preference disables transitions.

## Error and state handling

Each panel owns a `[data-state]` element. `setPanelState(panel, kind, message)`
represents loading, empty, and error without replacing navigation or controls.
Requests parse FastAPI error detail and retain a retry button or a navigable control.

Mutation buttons are disabled during memory review actions, then the memory panel and
overview are refreshed. Backend policy remains authoritative.

## Security boundary

The workbench is intended for localhost in this milestone. It adds no authentication
and must not be exposed publicly. DOM APIs prevent stored paper, memory, and trace
content from becoming markup. Existing trace redaction remains the source of truth
for secret fields.
