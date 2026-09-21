# Retrieval ablation evaluation design

## Dataset and isolation

The evaluator loads a Pydantic-validated JSON dataset. Every relevant coordinate
must resolve to a declared passage and every case must contain at least one
relevant coordinate. A canonical SHA-256 of the parsed dataset identifies the
exact evaluation input. Papers are indexed into a temporary SQLite database by
default so the command neither reads nor mutates personal data.

The checked-in corpus deliberately mixes exact-token queries, related word forms
and distractors. This makes the offline hashing baseline's strengths and limits
visible. It is a controlled regression fixture, not a representative scientific
retrieval benchmark.

## Retrieval modes

The evaluator calls the repository's lexical and vector component rankings and
the existing public hybrid search. Component results receive the same coordinate
and rank metadata as hybrid results. This evaluation-only access does not add a
vector-only option to the Agent tool schema or Workbench.

Each query is timed independently with `perf_counter_ns`. Latencies are reported
in milliseconds at P50 and P95. They are descriptive and machine-specific.

## Metrics

For binary relevance and cutoff `k`:

- `Recall@k = relevant retrieved in top k / total relevant`;
- `RR@k = 1 / rank` for the first relevant result, otherwise zero; MRR is the
  arithmetic mean over cases;
- `DCG@k = sum(rel_i / log2(i + 1))`; nDCG divides by the ideal DCG for the number
  of relevant items available at `k`.

Aggregate values are macro averages across cases. Hybrid deltas are absolute
percentage-point changes for bounded quality metrics, not relative percentages.

## Report and failure modes

JSON contains the schema version, dataset metadata/hash, environment, cutoff,
per-mode aggregates and per-case ranked coordinates. Invalid JSON, duplicate IDs,
dangling relevance or non-positive cutoff fail before indexing. Requested output
uses the existing atomic text writer. Documentation renders values from the real
checked-in artifact and keeps limitations adjacent to resume wording.
