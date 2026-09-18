# Evaluation suite workbench design

## Information architecture

```text
Evaluation Lab
  |-- Case mode (existing)
  `-- Suite mode
      |-- Suite definitions
      |-- Suite editor
      |   |-- available case selector + add
      |   `-- ordered membership rows (up/down/remove)
      |-- execute selected suite
      |-- suite-run history
      `-- aggregate and ordered item detail
```

The Suite workspace uses the existing two-column evaluation layout and collapses
through the current narrow breakpoint. Mode buttons toggle document sections rather
than navigating or discarding browser state.

## Browser state

The existing state gains `evaluationSuites`, `evaluationSuiteRuns`, `selectedSuite`,
`selectedSuiteRun`, and `suiteDraftCaseIds`. `loadEvaluationSuites()` fetches suite
definitions, suite runs, and cases in parallel so membership names can be rendered
without extra per-row requests.

Selecting a suite copies its `case_ids` into a draft array. Editor operations replace
that array immutably, then rerender the ordered list. Saving submits exactly the draft
order:

- no selected suite: `POST /evaluations/suites`;
- selected suite: `PUT /evaluations/suites/{suite_id}`.

Execution calls `POST /evaluations/suites/{suite_id}/execute`, refreshes suite data
and Overview, then selects the returned run id.

## Rendering

Suite definitions and runs use selection buttons consistent with case/result rows.
Aggregate detail uses a semantic definition list. Ordered items use `article`
elements whose content is created through `textContent`; identifiers use the
existing monospace style. Public `runtime_error` and `error` values are displayed as
categories and are never expanded into provider details.

History order follows backend response order. Numeric total/passed/failed/error
labels accompany visual pills, so no color or bar alone carries meaning.

## State and security

Every network operation drives the existing loading/ready/empty/error regions and
mutation controls are disabled until completion. The Workbench does not accept model
configuration, calculate aggregate pass state, or inspect persistence. All requests
remain same-origin public API calls.

## Trade-offs

The self-contained HTML remains intentionally dependency-free but increases the
single module's size. A component build system is still unjustified for this local
learning harness; once additional domains need rich editors, splitting static CSS
and JavaScript into tested modules will become the next maintainability milestone.
