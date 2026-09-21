# Resume narrative and handbook retrieval metrics

Status: Approved
Date: 2026-09-21

## Problem

The portfolio resume section leads with a dual-runtime implementation detail rather
than the Pi-based product story, while the standalone handbook does not yet contain
the newly verified retrieval ablation or its limitations.

## Requirements

- **NARRATIVE-001**: The Chinese resume description MUST lead with ScholarHarness
  as a Pi-based literature research Agent harness and position MiniPy as a Python
  reference/test runtime rather than a second production product.
- **NARRATIVE-002**: The resume description MUST cover project summary, stack,
  responsibilities and concise technical highlights suitable for direct reuse.
- **NARRATIVE-003**: Quantitative retrieval claims MUST match the checked-in report,
  identify the 20-query dataset as controlled/offline and avoid attributing the
  vector-derived gain solely to RRF.
- **HANDBOOK-METRIC-001**: The standalone HTML MUST add an accessible embedded
  comparison of BM25, vector and hybrid Recall@5/MRR@5/nDCG@5 with source links.
- **HANDBOOK-METRIC-002**: The HTML MUST explain the exact-token/related-word-form
  split, Hybrid-versus-Vector tie, latency trade-off and safe interview wording.
- **HANDBOOK-METRIC-003**: The updated HTML MUST remain one offline file without
  external assets, credentials or network calls.

## Acceptance criteria

- **AC-NARRATIVE-001**: Review confirms the resume text is Pi-led, technically
  accurate, concise and contains only report-backed metrics. (001..003)
- **AC-HANDBOOK-METRIC-001**: Static tests find seven accessible diagrams, metric
  values, report/dataset links and the limitation language. (001..003)
- **AC-HANDBOOK-METRIC-002**: Browser inspection confirms the chart, labels and
  surrounding resume guidance remain readable with no page-level overflow.
- **AC-NARRATIVE-002**: Repository lint, tests, compilation and Pi smoke pass.
