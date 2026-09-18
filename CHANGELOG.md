# Changelog

All notable user-visible changes to ScholarHarness are documented here. The project
uses semantic versioning beginning with the portfolio baseline.

## 0.1.0 — 2026-09-18

Initial local-first reference implementation.

### Agent runtimes

- Added asynchronous Pi JSONL RPC integration and a thin TypeScript tool bridge.
- Added the inspectable MiniPy model/tool loop with abort, branch, compaction,
  context injection, durable snapshots, and validated restart recovery.
- Added versioned trace-based Pi/MiniPy behavioral parity reports.

### Literature and memory

- Added page-aware PDF ingestion, SQLite FTS5, deterministic hashing embeddings,
  reciprocal-rank-fused hybrid retrieval, and exact citation validation.
- Added evidence-backed memory candidates, explicit trust review, runtime-owned
  provenance, bounded automatic context, and auditable supersession.

### Observability and quality

- Added redacted traces, correlated tool executions, a local Workbench, evaluation
  cases/suites, regression deltas, and JSON/JUnit CI gates.
- Added a credential-free offline benchmark and checked-in reproducibility report.
- Added 150+ automated tests and requirement-level SDD verification records for all
  major milestones.

### Operational boundaries

- Added authenticated Pi provenance transport, SQLite WAL/foreign-key/busy-timeout
  policy, bounded uploads, failure isolation, and persistent browser sessions.
- Added pinned credential-free GitHub Actions CI and wheel/sdist build evidence.

Known limitations and next steps are maintained in
[`docs/portfolio.md`](docs/portfolio.md#已知限制与下一步).
