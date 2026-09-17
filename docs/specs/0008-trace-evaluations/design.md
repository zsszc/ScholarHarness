# Deterministic trace evaluations design

## Domain model

```text
EvaluationCase
  id, name, prompt, expectations, pass_threshold, created_at, updated_at

EvaluationResult
  id, case_id, run_id, case snapshot, runtime/run snapshot,
  checks[], score, passed, previous_score, score_delta, regression, evaluated_at

EvaluationCheck
  id, passed, message, expected, observed
```

`EvaluationExpectations` is a typed JSON document. Lists are normalized by Pydantic
validation and stored as compact JSON. At least one non-null/non-empty expectation
is required. Required and forbidden tool sets may not overlap.

## Storage

`SQLiteEvaluationRepository` owns two tables in the shared database:

- `evaluation_cases` stores editable case definitions;
- `evaluation_results` stores one row per `(case_id, run_id)` with the full case
  snapshot and check payload.

Results order by evaluation time and id. Before upsert, the evaluator reads the most
recent result for the same case excluding the current run to compute comparison
fields. Updating a case never rewrites result snapshots.

## Evaluation pipeline

```text
case + terminal AgentRun
        |
        +-- ordered TraceEvent payloads -> answer text
        `-- correlated ToolExecution[] -> names, errors, citation result
                                 |
                         deterministic checks
                                 |
                    score + baseline comparison
                                 |
                         immutable result row
```

Check ids are stable:

- `run_status`
- `required_tool:<name>`
- `forbidden_tool:<name>`
- `tool_call_limit`
- `duration_limit`
- `citation_validation`
- `answer_contains:<normalized substring>`

A required tool passes only when at least one correlated execution exists and one
execution completed without error. Forbidden tools fail on any execution, whether
successful or not. Citation validation requires a successful `validate_citation`
execution whose result contains `valid: true`.

Answer reconstruction concatenates non-empty `delta` values from ordered
`message_update` events. Substring comparison is Unicode case-folded.

## Service composition

The FastAPI factory constructs the evaluation repository over the same default
database as traces, or accepts an injected repository for tests. Endpoints translate
unknown resources to 404, running-run rejection to 409, and validation to 422.

The CLI `eval` command accepts `--case`, `--run`, and `--database`. It constructs the
repositories, evaluates once, prints `EvaluationResult.model_dump(mode="json")`,
and lets argument/domain errors produce a concise non-zero exit.

## Failure modes and trade-offs

- A failed tool remains evidence and can fail required-tool success while also
  counting toward tool-call limits.
- If no earlier different run exists, comparison fields are null/false.
- Same-pair replacement recomputes the comparison against the previous different
  run, avoiding self-comparison.
- Equal check weights prioritize transparency over configurable scoring complexity.
- This layer grades observable behavior, not factual semantic quality. Citation and
  answer substring checks provide deterministic proxies until judge evaluators are
  specified.
