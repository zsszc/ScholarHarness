# Offline benchmark report

This report describes one local microbenchmark run. It is evidence about the
repository's offline data paths, not an SLA and not a comparison with Pi or another
agent framework. Results vary with hardware, filesystem state, Python, and SQLite.

## Reproduce

Implementation commit: `3f2b576`

```bash
uv run scholar-harness benchmark \
  --papers 100 \
  --passages-per-paper 4 \
  --queries 100 \
  --trace-events 1000 \
  --json-output docs/benchmark.json
```

The default uses an isolated temporary SQLite database and removes it after the
report is produced. The checked-in machine-readable result is
[`docs/benchmark.json`](benchmark.json).

## Workload and result

Environment: macOS 26.6.2 x86_64, Python 3.12.2, SQLite 3.45.2.

| Path | Workload | Elapsed | Observed throughput |
| --- | ---: | ---: | ---: |
| Paper ingestion | 100 papers × 4 passages | 0.154860 s | 645.74 papers/s |
| Hybrid retrieval | 100 queries over 400 passages | 0.805197 s | 124.19 queries/s |
| Trace persistence | 1,000 events | 0.182992 s | 5,464.72 events/s |

All deterministic checks passed:

- retrieval returned valid paper and passage coordinates;
- result count matched the configured limit and corpus size;
- exactly 1,000 trace events were persisted;
- the benchmark run reached `completed`.

## Interpretation

The benchmark deliberately excludes model latency, network calls, PDF parsing, and
browser rendering. It measures code owned by ScholarHarness and can run in CI or on
an evaluator's laptop without credentials. The corpus is small; at larger scale the
exact Python vector scan should be replaced by a dedicated vector index, while FTS5
and the runtime-neutral repository contract can remain.
