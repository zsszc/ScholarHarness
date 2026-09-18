# Durable browser sessions

Status: Verified
Date: 2026-09-18

## Problem

Browser chat traces are durable, but the interactive MiniPy session tree exists
only in process memory. Restarting the API loses prompts, tool messages, context
entries, forks, compaction nodes, the active leaf, and the ability to continue a
conversation. A harness should distinguish durable session state from a live model
connection and recover safely after ordinary restarts.

## Requirements

- **SESSION-001**: Persist browser-session identity, creation/update timestamps,
  active leaf, last trace-run id, and every append-only entry in SQLite.
- **SESSION-002**: A checkpoint MUST atomically replace one session snapshot so
  metadata and ordered entries cannot describe different revisions.
- **SESSION-003**: Checkpoint after session creation, every completed/failed/aborted
  turn, compaction, fork, and graceful close.
- **SESSION-004**: MiniPy MUST restore validated append-only entries and an active
  leaf before start, preserving ids, parents, data, timestamps, and branch order.
- **SESSION-005**: Restore MUST reject duplicate/missing ids, foreign session ids,
  forward/dangling parents, and unknown active leaves without partially loading.
- **SESSION-006**: A new manager over the same database MUST list persisted sessions
  without creating provider adapters and lazily hydrate a session on first access.
- **SESSION-007**: Hydrated sessions MUST report `busy=false` and `connected=false`,
  retain original `created_at` and `last_run_id`, and continue from the saved leaf.
- **SESSION-008**: Graceful application shutdown MUST close live adapters without
  deleting durable sessions; explicit session DELETE MUST remove both live state and
  its durable snapshot.
- **SESSION-009**: If model configuration is unavailable, persisted sessions MUST
  remain listable and intact; attempts to activate them MUST return a stable
  configuration error.
- **SESSION-010**: Corrupt snapshots MUST fail closed with a stable category and
  MUST NOT prevent healthy sessions or non-chat API routes from operating.
- **SESSION-011**: Evaluation-created temporary sessions and explicitly injected
  test managers MUST remain ephemeral unless given a session repository.
- **SESSION-012**: Persisted data and public metadata MUST not contain provider URLs,
  API keys, adapter objects, or environment configuration.

## Acceptance criteria

- **AC-SESSION-001**: Repository tests prove atomic round trips, deterministic
  ordering, replacement, deletion, and additive initialization. (SESSION-001, 002)
- **AC-SESSION-002**: MiniPy restoration tests prove exact replay/branch continuation
  and reject every corrupt-tree class. (SESSION-004, 005)
- **AC-SESSION-003**: Manager restart tests prove lazy adapter creation, metadata
  fidelity, continued model context, checkpoints for all mutations, and shutdown
  retention. (SESSION-003, 006..008)
- **AC-SESSION-004**: Missing-provider and corrupt-snapshot tests prove stable
  failure isolation and intact durable rows. (SESSION-009, 010)
- **AC-SESSION-005**: API/WebSocket tests prove list, reconnect, continuation, and
  explicit durable deletion across manager/application restart. (SESSION-006..009)
- **AC-SESSION-006**: Existing evaluation isolation and secret-free metadata tests
  remain green. (SESSION-011, 012)
- **AC-SESSION-007**: Lock consistency, lint, all tests, compilation, Pi smoke, live
  HTTP bridge smoke, and browser QA pass.

## Decisions

- This milestone persists browser-owned MiniPy sessions, not CLI REPL or Pi-owned
  sessions. Pi already owns its session files; cross-runtime import is later parity
  work.
- Session rows are eagerly listed but runtime/adapters are lazily hydrated. Merely
  opening the Workbench therefore creates no model clients.
- Checkpoints contain complete small session trees. Incremental event storage can be
  introduced after profiling; atomic full replacement is easier to reason about.
- Corruption is isolated per session and surfaced only when that session is opened.
