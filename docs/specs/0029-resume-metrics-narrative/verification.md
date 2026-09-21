# Verification: resume narrative and handbook retrieval metrics

Status: Verified
Date: 2026-09-21

## Narrative review

- `docs/resume-project-description.zh-CN.md` provides both complete and one-page
  Chinese variants. Both lead with Pi and describe MiniPy only as a Python
  Reference Runtime for learning and deterministic tests.
- Retrieval claims match `docs/retrieval-evaluation.json`: on the controlled
  20-query offline fixture, Recall@5 is 50% → 95% and MRR@5 is 50% → 79.3%.
- The resume and handbook explicitly state that Hybrid ties Vector-only on all
  three quality metrics, so the gain is not attributed to RRF alone.

## Static and browser evidence

- `uv run pytest -q tests/test_deep_dive_handbook.py tests/test_retrieval_evaluation.py`
  passed 10 focused tests before the full gate.
- Browser inspection served the file over loopback with a cache-busting URL.
  At a 1280×720 viewport the document reported seven accessible `svg[role=img]`
  diagrams, `scrollWidth == clientWidth == 1280`, and the metric chart, resume
  section, exact values and limitation language were present.
- Visual inspection confirmed direct numeric labels for BM25, Vector and Hybrid,
  plus readable explanation and evidence links without horizontal overflow.

## Repository gates

The repository-required verification command passed:

```text
uv run ruff check .
uv run pytest                    # 172 passed, 2 dependency deprecation warnings
python -m compileall -q src
uv run scholar-harness pi-smoke # pi_rpc=ok, extension=ok, entry_count=2
```

`pi-smoke --check-service` was not required because this feature changes only
documentation and static documentation tests, not the Pi bridge or HTTP boundary.
