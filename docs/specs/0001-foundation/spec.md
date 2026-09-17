# ScholarHarness foundation

Status: Verified
Date: 2026-09-17

## Problem

A personal literature agent needs reliable paper ingestion, evidence-preserving
retrieval, controlled long-term memory, and a production-capable agent runtime.
Business knowledge must remain in Python while Pi remains replaceable as the live
agent runtime.

## Goals

- Integrate Pi without coupling domain storage to its TypeScript internals.
- Import digitally readable PDFs with stable page coordinates.
- Expose paper retrieval as reusable tools.
- Prevent unverified model output from becoming trusted long-term memory.
- Keep runtime behavior testable without model credentials.

## Non-goals

- OCR for image-only PDFs.
- Embedding or neural reranking.
- Multi-user authentication and remote deployment.
- A production graphical workbench.
- A complete Python reimplementation of Pi.

## Requirements

### Runtime

- **FOUND-001**: The system MUST communicate with Pi through strict JSONL RPC over
  stdin/stdout and correlate responses by request id.
- **FOUND-002**: The runtime adapter MUST expose prompt streaming, abort, compact,
  fork, session entry retrieval, and normalized events.
- **FOUND-003**: A streamed prompt MUST remain active until Pi emits
  `agent_settled`, not merely `agent_end`.
- **FOUND-004**: Runtime code MUST be testable with a fake subprocess and without
  provider credentials.

### Tool boundary

- **FOUND-010**: Python MUST be the authority for papers, memories, and tool
  validation.
- **FOUND-011**: The Pi extension MUST remain a thin adapter that forwards named
  tools to the localhost Python service.
- **FOUND-012**: The repository MUST provide a reproducible smoke check for Pi RPC,
  extension loading, and optional HTTP bridge health.

### Literature

- **FOUND-020**: The API MUST accept digitally readable PDFs up to 50 MiB.
- **FOUND-021**: Extracted passages MUST retain stable paper, passage, and one-based
  page identifiers.
- **FOUND-022**: Papers and passages MUST persist in SQLite and be searchable through
  FTS5.
- **FOUND-023**: Empty, encrypted, corrupted, and image-only PDFs MUST fail with an
  explicit client-facing error instead of indexing empty content.
- **FOUND-024**: `search_papers` and `read_passage` MUST return citable evidence
  coordinates.

### Memory

- **FOUND-030**: `save_memory` MUST create a `candidate`; an agent tool MUST NOT
  create a confirmed memory directly.
- **FOUND-031**: Every tool-created memory MUST include at least one paper passage
  and a verbatim quote that the service verifies against stored text.
- **FOUND-032**: Evidence page numbers MUST come from canonical paper storage rather
  than model-provided values.
- **FOUND-033**: `recall_memory` MUST search only confirmed memories.
- **FOUND-034**: Candidate confirmation and rejection MUST require explicit API
  actions, while rejected records remain auditable.

## Acceptance criteria

- **AC-001**: A fake Pi process proves request correlation, event streaming, and
  session-entry normalization for FOUND-001 through FOUND-004.
- **AC-002**: A real installed Pi process loads the ScholarHarness extension and the
  HTTP health command reaches the Python service.
- **AC-003**: Importing a readable PDF produces page-aware passages; an invalid or
  textless file is rejected.
- **AC-004**: Reopening the SQLite repository preserves papers and FTS results.
- **AC-005**: A fabricated evidence quote is rejected.
- **AC-006**: A candidate is absent from recall, then appears after explicit
  confirmation with canonical evidence coordinates.
- **AC-007**: Static checks, compilation, and the automated test suite pass.
