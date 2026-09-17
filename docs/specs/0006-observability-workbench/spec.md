# Observability workbench

Status: Approved
Date: 2026-09-17

## Problem

ScholarHarness now has interview-worthy runtime, retrieval, memory, and tracing
internals, but they are visible only through CLI output and raw OpenAPI endpoints.
A local workbench should make agent behavior inspectable in one browser view without
introducing a frontend build chain or hiding the underlying API contracts.

## Requirements

- **UI-001**: Serve a self-contained workbench at `GET /workbench` with no external
  JavaScript, CSS, font, image, or CDN dependency.
- **UI-002**: The workbench MUST present four navigable areas: overview, runtime
  runs, memory review, and library search.
- **UI-003**: Overview MUST summarize loaded runs, tool executions, candidate
  memories, confirmed memories, and papers from API data.
- **UI-004**: Run inspection MUST show status, runtime type, timestamps, active leaf,
  ordered event timeline, and correlated tool calls with arguments, results, error
  state, and duration.
- **UI-005**: Memory review MUST filter candidate/confirmed/rejected records and
  allow explicit candidate confirmation or rejection through existing trust-boundary
  APIs.
- **UI-006**: Library MUST list paper metadata and passage counts, execute hybrid or
  lexical search, and render citable result coordinates plus component ranks.
- **UI-007**: User-controlled or persisted data MUST be inserted through DOM text
  properties rather than interpreted as HTML.
- **UI-008**: Every data panel MUST have explicit loading, empty, and error states,
  and retry after navigation or refresh.
- **UI-009**: The layout MUST remain usable on narrow screens and provide visible
  keyboard focus states, semantic buttons, labels, and status text.
- **UI-010**: Add a read-only paper catalog API returning id, title, authors, year,
  and passage count in deterministic order.
- **UI-011**: Paper catalog behavior MUST work for both in-memory tests and SQLite,
  and existing repository callers MUST remain compatible.
- **UI-012**: The service home page MUST link directly to the workbench while
  retaining OpenAPI and health links.

## Decisions

- This milestone is an observability and review surface, not a browser runtime host.
  Browser chat and long-lived runtime session ownership require a separate lifecycle
  specification.
- The page is server-served semantic HTML with embedded CSS and a small ES module.
  This avoids Node/build dependencies and keeps the Python-focused repository easy
  to run for interviews.
- The UI consumes the same public/local HTTP endpoints a future frontend would use;
  it does not read SQLite directly.
- Run events and tool results are rendered as formatted JSON text after the backend's
  existing redaction and size bounding.
- Visual design uses a restrained research-console theme, responsive CSS grid, and
  no generated raster assets.
- Paper catalog defaults to 100 rows and caps requests at 500.

## Acceptance criteria

- **AC-UI-001**: `/workbench` returns a complete page with all four areas, embedded
  assets, semantic navigation, and no external resource URLs. (UI-001, UI-002,
  UI-009)
- **AC-UI-002**: A run seeded with events and a tool execution is available through
  the APIs used by the workbench in stable order. (UI-003, UI-004)
- **AC-UI-003**: Candidate memory list/confirm/reject flows remain functional and
  are wired to workbench controls. (UI-005)
- **AC-UI-004**: The paper catalog returns deterministic summaries for in-memory and
  persistent repositories; hybrid/lexical search retains inspectable coordinates
  and ranks. (UI-006, UI-010, UI-011)
- **AC-UI-005**: Automated source assertions prove persisted fields are rendered via
  safe DOM text APIs and that every panel defines loading, empty, and error handling.
  (UI-007, UI-008)
- **AC-UI-006**: The home page links to `/workbench`. (UI-012)
- **AC-UI-007**: Static checks, compilation, all tests, Pi smoke, and live HTTP
  service smoke verification pass.
