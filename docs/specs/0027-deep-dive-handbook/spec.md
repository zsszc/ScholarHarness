# Standalone ScholarHarness deep-dive handbook

Status: Verified
Date: 2026-09-20

## Problem

The project has thorough source and SDD evidence but no single, visual,
interview-ready Chinese reference that can be opened without running a server.

## Requirements

- **GUIDE-001**: Deliver one self-contained HTML file that opens locally and
  covers purpose, boundaries, setup, usage, architecture, data models, control
  and data flows, algorithms, safety, tests, operations, limitations and roadmap.
- **GUIDE-002**: Visualize at least runtime ownership, one complete chat/tool
  turn, ingestion/retrieval, memory trust, branch semantics, and evaluation/CI.
- **GUIDE-003**: Claims about implemented behavior MUST cite repository paths
  and distinguish current code from proposals or interview-level theory.
- **GUIDE-004**: Include substantial interview questions with layered answers,
  trade-offs and follow-ups across Python/backend, databases, retrieval/RAG,
  Agent/tool calling/memory, observability/evaluation, security and architecture.
- **GUIDE-005**: The HTML MUST work offline without external scripts, fonts,
  images or service calls and MUST contain no credentials or local secrets.

## Acceptance criteria

- **AC-GUIDE-001**: The local HTML opens in a browser with functional navigation,
  diagrams and question interactions. (GUIDE-001, 002, 005)
- **AC-GUIDE-002**: A source audit verifies core flows, factual boundaries and
  code references against this checkout. (GUIDE-003, 004)
- **AC-GUIDE-003**: Repository verification gates pass; a secret scan of the
  new artifact finds no credential values. (GUIDE-005)
