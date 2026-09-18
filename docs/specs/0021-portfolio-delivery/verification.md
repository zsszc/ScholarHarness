# Portfolio delivery verification

Status: Verified
Date: 2026-09-18

## Automated verification

```text
uv lock --check: resolved 33 packages
uv run ruff check .: all checks passed
uv run pytest: 151 passed, 2 upstream warnings in 1.82s
python -m compileall -q src: exit 0
uv run scholar-harness pi-smoke: pi_rpc=ok, extension=ok, entry_count=1
uv run scholar-harness benchmark --papers 5 --passages-per-paper 2
  --queries 3 --trace-events 10: all four correctness checks true
```

Full checked-in benchmark on implementation commit `3f2b576`:

```text
100 papers x 4 passages, 100 hybrid queries, 1000 trace events
paper ingestion: 645.74 papers/s
hybrid retrieval: 124.19 queries/s
trace persistence: 5464.72 events/s
all four correctness checks: true
```

## Acceptance evidence

- **AC-PORTFOLIO-001**:
  `test_offline_benchmark_is_correct_and_cleans_temporary_database` proves versioned
  metrics, workload validation, deterministic checks, positive throughput, and
  cleanup. CLI tests prove argument rejection, stdout JSON, atomic file output, and
  exact stdout/artifact parity.
- **AC-PORTFOLIO-002**: `docs/benchmark.json` was produced by the documented command
  from commit `3f2b576`; `test_checked_in_portfolio_evidence_is_consistent` validates
  the schema, commit, correctness flags, and Markdown metric values.
- **AC-PORTFOLIO-003**: `docs/portfolio.md` contains the three-minute evaluator path,
  architecture and trust-boundary narrative, evidence map, Chinese and English
  resume bullets, interview prompts, and adjacent limitations. Its required sections
  are regression-tested; README and architecture link the final evidence.
- **AC-PORTFOLIO-004**: The final credential-free path passed lock consistency,
  lint, all 151 tests, compilation, real Pi RPC/extension smoke, and benchmark smoke.

## Boundary result

ScholarHarness is now deliverable as a truthful, reproducible engineering
portfolio. An evaluator can understand the design in minutes, run the core evidence
without credentials, inspect every major requirement and verification record, and
distinguish demonstrated capabilities from explicitly documented future work.
