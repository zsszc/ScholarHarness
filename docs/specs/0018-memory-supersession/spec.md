# Auditable memory supersession

Status: Approved
Date: 2026-09-18

## Problem

Confirmed long-term memories can become duplicated or outdated, but the current
lifecycle only offers rejection or an unaudited `superseded` status. A reviewer
needs a safe consolidation primitive that preserves the old record, identifies its
replacement, and cannot silently cross a memory trust boundary.

## Requirements

- **SUPERSEDE-001**: A confirmed memory MAY be superseded only by a distinct,
  active confirmed memory.
- **SUPERSEDE-002**: Source and replacement MUST have the same kind and scope; for
  session or branch scope they MUST also have the same owning session.
- **SUPERSEDE-003**: Supersession MUST atomically set the source status to
  `superseded`, record the replacement id, and update its timestamp without deleting
  content, evidence, or provenance.
- **SUPERSEDE-004**: A replacement that is itself superseded MUST be rejected so
  replacement chains and cycles cannot be introduced.
- **SUPERSEDE-005**: Repeating the same supersession MUST be idempotent, while a
  different replacement for an already superseded memory MUST be rejected.
- **SUPERSEDE-006**: Public memory representations MUST expose
  `superseded_by_id`; existing databases MUST migrate additively.
- **SUPERSEDE-007**: The HTTP API MUST offer an explicit reviewer-only lifecycle
  operation and return stable 404 errors for missing ids and 409 errors for invalid
  transitions.
- **SUPERSEDE-008**: Recall and automatic context MUST continue to select only
  active confirmed memories.

## Acceptance criteria

- **AC-SUPERSEDE-001**: Repository tests prove atomic valid and idempotent
  transitions while preserving source data. (SUPERSEDE-001, 003, 005, 006)
- **AC-SUPERSEDE-002**: Invalid-state tests cover self replacement, inactive source
  or target, kind/scope/owner mismatch, and attempts to create chains. (SUPERSEDE-001,
  002, 004, 005)
- **AC-SUPERSEDE-003**: API tests prove successful transition and stable 404/409
  behavior. (SUPERSEDE-007)
- **AC-SUPERSEDE-004**: Recall tests prove the old memory disappears while the
  replacement remains eligible. (SUPERSEDE-008)
- **AC-SUPERSEDE-005**: Lock consistency, lint, all tests, compilation, and Pi smoke
  pass.

## Non-goals

- The harness will not ask a model to choose a replacement or automatically mutate
  trust state in this milestone.
- Evidence is not merged into a new synthetic memory; both immutable source records
  remain independently inspectable.
