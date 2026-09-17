# Hybrid retrieval design

## Components

```text
search_papers
     |
SQLitePaperRepository
     |-- FTS5 lexical candidates
     |-- exact cosine vector candidates
     `-- reciprocal-rank fusion
              |
       citable passage results

EmbeddingProvider <--- HashingEmbeddingProvider (offline default)

validate_citation ---> exact passage read ---> normalized quote check
```

## Embedding boundary

`EmbeddingProvider` exposes a stable provider id, dimensions, and `embed(texts)`.
The repository owns batching and persistence. Provider metadata is stored beside
each vector so switching models cannot accidentally compare incompatible vectors.

The default hashing provider maps normalized word and character n-gram features to
signed dimensions using a stable cryptographic digest, then L2-normalizes the
vector. Character features give the offline baseline limited robustness to related
word forms. Production adapters may call local sentence-transformers or hosted
embedding APIs through the same interface.

## Storage and migration

`passage_embeddings` uses `(paper_id, passage_id, provider)` as its primary key and
references `passages` with cascading deletion. Each row includes dimensions and a
float32 BLOB. Schema creation is additive for existing databases.

Paper import remains one transaction: passage rows, FTS rows, and embeddings are
replaced together. A provider failure therefore cannot leave partially indexed
paper state.

## Ranking

Lexical candidates come from FTS5 BM25. Vector candidates are all compatible stored
vectors ordered by cosine similarity. Each list is assigned a one-based rank and
combined with RRF. Ties use `(paper_id, passage_id)` for reproducibility.

Lexical mode retains the existing BM25 behavior. Hybrid results add:

```json
{
  "score": 0.0325,
  "retrieval_mode": "hybrid",
  "lexical_rank": 1,
  "vector_rank": 2
}
```

## Citation policy

`validate_citation` accepts `paper_id`, `passage_id`, and `quote`. It collapses
Unicode whitespace in both quote and passage and then performs a case-sensitive
substring check. It returns structured failure reasons for empty quotes, unknown
coordinates, and quote mismatches.

## Failure modes and trade-offs

- Exact vector scan is linear and intended for a personal corpus baseline.
- Feature hashing is reproducible and dependency-free but materially weaker than a
  trained semantic embedding model.
- Strict quotation checking rejects paraphrases by design; this prevents an agent
  from presenting generated prose as a direct quotation.
