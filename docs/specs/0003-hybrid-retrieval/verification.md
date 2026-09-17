# Hybrid retrieval verification

Verified: 2026-09-17

## Automated evidence

```bash
uv run ruff check .
# All checks passed

uv run pytest
# 31 passed

python -m compileall -q src
# exit 0

uv run scholar-harness pi-smoke
# pi_rpc=ok, extension=ok

SCHOLAR_HARNESS_URL=http://127.0.0.1:8766 \
  uv run scholar-harness pi-smoke --check-service
# pi_rpc=ok, extension=ok, tool_service=ok
```

## Acceptance mapping

- **AC-RETRIEVAL-001**:
  `test_hybrid_search_finds_related_word_form_and_explains_ranking` proves that a
  query absent from FTS can retrieve a related word form through vector ranking.
- **AC-RETRIEVAL-002**: `test_hybrid_search_fuses_lexical_and_vector_ranks` verifies
  deterministic RRF scoring and both inspectable component ranks.
- **AC-RETRIEVAL-003**: `test_reimport_replaces_old_passages` and the reopen step in
  the hybrid test verify persistence and cascading stale-vector removal.
- **AC-RETRIEVAL-004**: `test_search_returns_citable_coordinates` and
  `test_search_accepts_explicit_lexical_mode` verify the compatible tool contract.
- **AC-CITATION-001**:
  `test_validate_citation_checks_coordinate_and_normalized_quote` covers valid,
  altered, unknown-coordinate, and empty quotations.
- **AC-RETRIEVAL-005**: static checks, compilation, all automated tests, real Pi
  extension loading, and the live Python service bridge all pass.

## Known limitations

- Feature hashing captures token and word-form similarity but not general semantic
  equivalence. A trained embedding provider is the intended production adapter.
- Exact vector scan is linear in passage count and is aimed at a personal corpus.
- Citation validation covers direct quotations, not paraphrase entailment.
