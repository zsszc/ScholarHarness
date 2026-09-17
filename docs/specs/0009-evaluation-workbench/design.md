# Evaluation workbench design

## Information architecture

```text
Evaluation Lab
  |-- Case list
  |-- Case editor (new/update)
  |-- Terminal run selector + evaluate action
  |-- Selected result summary + check evidence
  `-- Case score history + regression markers
```

The left workspace column contains case selection and the editor. The right column
contains evaluation execution, score history, and result detail. At the existing
narrow breakpoint the columns collapse and retain document order.

## State and API flow

The browser state gains `evaluationCases`, `evaluationResults`, `evaluationRuns`,
`selectedCase`, and `selectedResult`.

`loadEvaluations()` fetches cases, results, and runs in parallel. It renders case
buttons, populates the run selector with terminal runs, restores the selected case
when possible, and selects the newest result. Selecting a case filters results
client-side from the already loaded bounded result list, fills the editor, and
updates history.

Case save behavior is determined by `selectedCase`:

- null: `POST /evaluations/cases`;
- existing id: `PUT /evaluations/cases/{id}`.

Evaluation calls `POST /evaluations/cases/{case_id}/runs/{run_id}`, refreshes
overview/evaluation data, and selects the returned result.

## Input normalization

`parseList(value)` splits on commas, trims each token, removes empty tokens, and
preserves the first occurrence of every value. Blank numeric inputs become omitted
fields rather than zero. Terminal status blank means no status expectation.

The form always produces at least one expectation or lets the backend's 422 response
explain the invariant. Browser code does not reproduce Pydantic validation or score
rules.

## Rendering and accessibility

Cases and results use buttons with selected styling. Result summaries use semantic
definition lists. Each check is an article with a pass/fail pill and two JSON `pre`
blocks created with `textContent`. History rows expose case name, score percentage,
delta, and regression text outside the visual bar.

Mutation buttons are disabled while requests are pending. Status regions use the
existing `data-state` system. Labels are explicitly associated with inputs; focus
styles already cover buttons, inputs, selects, and textareas.

## Security boundary

No evaluation field is assigned to `innerHTML`. The page calls only same-origin
evaluation, run, and overview endpoints. Scoring and evidence derivation remain in
Python; the browser only renders returned snapshots and submits case definitions.
