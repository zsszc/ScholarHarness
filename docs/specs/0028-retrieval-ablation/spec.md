# Retrieval ablation evaluation

Status: Verified
Date: 2026-09-21

## Problem

ScholarHarness measures local throughput but has no labelled quality benchmark.
Consequently the portfolio can describe BM25, hashing vectors and RRF, but cannot
truthfully quantify whether hybrid retrieval changes ranking quality.

## Requirements

- **RETRIEVAL-EVAL-001**: Provide a versioned, human-readable offline dataset
  containing papers, passages, queries and explicit relevant passage coordinates.
- **RETRIEVAL-EVAL-002**: Evaluate lexical-only, vector-only and RRF-hybrid
  retrieval over the same indexed corpus without model or network access.
- **RETRIEVAL-EVAL-003**: Report Recall@k, MRR@k and nDCG@k using documented
  binary-relevance formulas, plus descriptive P50/P95 query latency for each mode.
- **RETRIEVAL-EVAL-004**: Output versioned JSON with dataset identity and SHA-256,
  environment metadata, per-query rankings, aggregate metrics and hybrid deltas
  against both component baselines.
- **RETRIEVAL-EVAL-005**: The CLI MUST validate positive `k`, reject malformed or
  dangling relevance coordinates, write requested output atomically and use an
  isolated temporary database by default.
- **RETRIEVAL-EVAL-006**: Check in one real report generated from the transparent
  controlled dataset and document its command, interpretation and limitations.
- **RETRIEVAL-EVAL-007**: Resume-facing documentation MUST use only values present
  in the checked-in report and MUST identify the benchmark as controlled/offline.

## Acceptance criteria

- **AC-RETRIEVAL-EVAL-001**: Metric unit tests cover hits, misses, multiple
  relevant passages and ranking order for Recall, MRR and nDCG. (001..003)
- **AC-RETRIEVAL-EVAL-002**: Service and CLI tests prove three-mode evaluation,
  deterministic rankings, validation, dataset hashing, atomic JSON output and
  temporary cleanup. (001..005)
- **AC-RETRIEVAL-EVAL-003**: A checked-in JSON/Markdown report is internally
  consistent and states that the controlled corpus is not a production-quality
  or cross-dataset claim. (004, 006, 007)
- **AC-RETRIEVAL-EVAL-004**: Repository lint, tests, compilation and Pi smoke pass
  after the feature is implemented.

## Non-goals

- This benchmark does not measure answer correctness, hallucination, model
  latency, PDF parsing, ANN scalability or performance on a public IR dataset.
- Hashing vectors are not described as neural semantic embeddings.
- No target improvement is prescribed before the experiment runs.
