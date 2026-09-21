# Verification: retrieval ablation evaluation

Status: Verified
Date: 2026-09-21

## Controlled evaluation evidence

Implementation commit `d6087d6` was evaluated with:

```bash
uv run scholar-harness retrieval-eval \
  --dataset benchmarks/retrieval-ablation-v1.json \
  --k 5 \
  --json-output docs/retrieval-evaluation.json
```

The dataset has SHA-256
`156b5c4af956c928fcdc2cd4170e3a988004ee0bea85952d58b7b9f9cb0208f2`,
15 passages and 20 labelled queries split evenly between exact-token and
related-word-form cases. The checked report records:

| Mode | Recall@5 | MRR@5 | nDCG@5 |
| --- | ---: | ---: | ---: |
| lexical | 50.0% | 50.0% | 50.0% |
| vector | 95.0% | 79.3% | 83.2% |
| hybrid | 95.0% | 79.3% | 83.2% |

Hybrid therefore changes the three metrics by +45.0, +29.3 and +33.2 percentage
points against lexical. It has zero quality delta against vector-only on this
fixture; the narrative states that plainly and does not attribute the entire gain
to RRF. Per-category evidence shows exact-token queries at 100% for every mode and
the related-word-form improvement supplied by hashing features.

## Automated evidence

- `test_ranking_metrics_cover_hits_misses_and_multiple_relevant_items` verifies
  Recall, reciprocal rank and normalized DCG formulas.
- Dataset validation rejects dangling relevance, duplicate identities and invalid
  cutoffs before indexing.
- Service and CLI tests prove lexical/vector/hybrid execution, deterministic
  rankings, dataset hashing, isolated temporary cleanup and atomic JSON output.
- The checked-artifact test binds the report to the dataset hash and implementation
  commit, and verifies that every aggregate value appears in the limitations-adjacent
  Markdown report.

## Repository gates

- `uv run ruff check .`: passed.
- `uv run pytest`: 171 passed; two dependency deprecation warnings.
- `python -m compileall -q src`: passed.
- `uv run scholar-harness pi-smoke`: Pi RPC and extension passed.

All acceptance criteria are satisfied. The report remains a small controlled
offline regression fixture, not evidence of public-corpus or answer-quality gains.
