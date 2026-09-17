# Hybrid retrieval and citation validation

Status: Verified
Date: 2026-09-17

## Problem

FTS5 retrieves exact terms well but misses semantically related wording. Research
agents also need a machine-checkable way to prove that a quoted claim is present at
the cited paper coordinate before returning it to a user.

## Requirements

- **RETRIEVAL-001**: The paper repository MUST support lexical and hybrid search
  without changing the existing citable passage coordinates.
- **RETRIEVAL-002**: Hybrid search MUST combine independent lexical and vector
  rankings with deterministic reciprocal-rank fusion (RRF).
- **RETRIEVAL-003**: Embedding generation MUST be behind a replaceable provider
  interface. The default provider MUST run locally, require no credentials, and
  produce deterministic vectors for tests and development.
- **RETRIEVAL-004**: SQLite MUST persist passage embeddings with provider identity
  and dimensions, and MUST replace stale embeddings when a paper is re-imported.
- **RETRIEVAL-005**: Search results MUST expose the final score plus lexical rank,
  vector rank, and retrieval mode so ranking decisions are inspectable.
- **RETRIEVAL-006**: The tool boundary MUST allow callers to choose `lexical` or
  `hybrid`; the default MUST be `hybrid` while preserving the existing query and
  limit inputs.
- **CITATION-001**: A citation validator MUST verify that a non-empty quote occurs
  in the exact referenced passage after whitespace normalization.
- **CITATION-002**: Citation validation MUST return an explicit valid/invalid result
  and a reason, and MUST not expose an unhandled error for an unknown coordinate.
- **CITATION-003**: Citation validation MUST be available through the common Python
  tool registry so Pi and future runtimes use the same policy.

## Decisions

- RRF uses `1 / (60 + rank)` for each contributing ranking. It is stable across
  incomparable BM25 and cosine score scales.
- Vector candidates below cosine similarity `0.05` are discarded so an exact scan
  does not turn every unrelated passage into a search result.
- The built-in embedding provider uses signed feature hashing over normalized word
  and character n-gram features. It is an educational/offline baseline, not a claim
  of state-of-the-art semantic quality.
- Embeddings are stored as compact little-endian float arrays rather than JSON.
- Vector search is exact over the local collection. Approximate indexes and hosted
  embedding models are later performance adapters, not part of this milestone.
- Whitespace-normalized substring matching is deliberately strict. Paraphrase
  entailment is outside citation validation for this milestone.

## Acceptance criteria

- **AC-RETRIEVAL-001**: A semantic-style query with no useful exact-term overlap can
  retrieve the intended passage through vector ranking. (RETRIEVAL-001..003)
- **AC-RETRIEVAL-002**: A result present in lexical and vector rankings receives a
  deterministic fused score and exposes both component ranks. (RETRIEVAL-002,
  RETRIEVAL-005)
- **AC-RETRIEVAL-003**: Reopening SQLite retains embeddings; re-importing a paper
  removes embeddings for deleted passages. (RETRIEVAL-004)
- **AC-RETRIEVAL-004**: `search_papers` defaults to hybrid and accepts an explicit
  lexical mode without breaking existing callers. (RETRIEVAL-006)
- **AC-CITATION-001**: Exact and whitespace-varied quotes validate at a known
  coordinate, while altered quotes and unknown coordinates return invalid reasons.
  (CITATION-001..003)
- **AC-RETRIEVAL-005**: Static checks, compilation, all automated tests, and Pi
  bridge smoke verification pass.
