# Auditable memory supersession design

## Data model

An additive nullable `memories.superseded_by_id` column records the direct
replacement. It is returned on `Memory` and retained with the superseded record.
SQLite migration remains compatible with databases created by earlier milestones.

## Transition service

`SQLiteMemoryRepository.supersede(source_id, replacement_id)` owns validation and
the single transaction. Both rows are loaded inside that transaction. The source
must be active confirmed unless it already points to the same replacement; the
replacement must be active confirmed and cannot equal the source. Kind, scope, and
the effective owner must match. Global records have no owner requirement; scoped
records compare `source_session_id`.

Only an active confirmed record can be a target, so the graph has depth one and
cycles are impossible. A repeated identical operation returns the stored source
without another write.

## HTTP boundary

`POST /memories/{id}/supersede` accepts a strict body containing
`replacement_id`. Missing records map to 404 and invalid transitions to 409. The
operation is intentionally absent from model tools: trust mutation remains a human
or administrative action.

## Failure and safety properties

Validation occurs before the update in one SQLite transaction. A failed operation
therefore changes neither status nor relation. Recall already filters on
`status='confirmed'`, so a successful transition immediately removes the old record
without changing retrieval code.

## Trade-offs

This is a transparent consolidation primitive, not semantic deduplication. A future
stage can rank duplicate or conflicting candidates, but applying a proposal should
still use this deterministic reviewed transition.
