# Portfolio delivery design

## Offline benchmark

`scholar-harness benchmark` creates a temporary directory unless `--database` is
provided. It generates deterministic papers and passages, measures repository
ingestion, repeated hybrid retrieval, and trace-event append throughput with
`time.perf_counter`, then validates expected result coordinates and event counts.
The JSON schema is versioned independently of package version.

Durations and operations per second are rounded for readable artifacts. Correctness
checks are stable booleans; performance values are descriptive. Platform, Python,
SQLite, workload, and the optional Git commit environment supplied by the caller
make reports interpretable without pretending hardware neutrality.

Atomic report writing reuses the existing delivery-safe text writer. The temporary
directory lives through all repository connections and is removed on return.

## Portfolio narrative

`docs/portfolio.md` is the evaluator entry point. It leads with a short demo and
then explains the split between Pi as the production runtime, MiniPy as the learning
runtime, and Python-owned domain policy. Resume bullets cite concrete commands,
tests, or specifications. Limitations remain adjacent to claims.

`docs/benchmark.md` records one actual run and links its machine-readable JSON.
The README points to these artifacts rather than duplicating the full narrative.

## Trade-offs

Microbenchmarks emphasize local storage paths, not end-to-end LLM latency. This is
intentional: model latency and quality depend on credentials and providers, while
the measured paths are owned by this repository and reproducible offline.
