# Resume narrative and handbook retrieval metrics design

## Narrative hierarchy

The title and opening sentence present the user-facing value and Pi integration.
Pi remains the primary runtime direction. MiniPy appears once as an inspectable
Python reference implementation used for deterministic tests and learning. The
resume avoids claiming that the current browser graph is Pi-native.

The long resume block follows the sample's hierarchy: title, stack, project
summary, responsibilities and evidence-backed highlights. The compact block keeps
four to five bullets for a one-page resume.

## Metric visualization

The existing offline handbook receives a seventh inline SVG in the retrieval
chapter. Three horizontal small-multiple groups compare Recall@5, MRR@5 and nDCG@5
on one 0-100% scale. BM25 is neutral; Vector and Hybrid retain distinct, labelled
marks even though their values tie. Direct numeric labels make the chart usable
without relying on color.

Below the chart, prose explains that all modes score 100% on exact-token cases,
that the improvement comes from hashing features on related word forms, and that
Hybrid adds latency without a measured quality gain over Vector-only in this
fixture. Links resolve to the checked report, JSON and dataset.

## Verification

Static HTML tests pin the diagram count and required evidence strings. Existing
offline/link/secret/interaction checks remain unchanged. Browser inspection uses
the local document through a temporary loopback static server and checks viewport
overflow plus visual label readability.
