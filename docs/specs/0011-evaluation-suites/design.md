# Evaluation suites design

## Domain model

```text
EvaluationSuite
  id, name, ordered case_ids, created_at, updated_at

EvaluationSuiteRun
  id, suite_id, suite_name, case_ids, items
  total_count, passed_count, failed_count, error_count, passed
  started_at, ended_at

EvaluationSuiteItem
  position, case snapshot
  execution/result identifiers and metadata OR public error category
```

The case snapshot reuses `EvaluationCaseInput`: name, prompt, expectations, and
threshold. It is embedded in the persisted item JSON along with result identifiers
instead of depending on a mutable case row when history is read.

## Persistence

`evaluation_suites` stores definition metadata. `evaluation_suite_cases` stores
ordered membership with unique `(suite_id, case_id)` and `(suite_id, position)`
constraints plus foreign keys to cases. Replacing a suite validates every case in
one transaction and replaces membership atomically.

`evaluation_suite_runs` stores the immutable definition snapshot, aggregate counts,
and ordered item JSON. Suite runs intentionally do not cascade when a definition is
edited. Existing evaluation results remain the detailed check authority; each
successful item embeds the result id and summary plus its case snapshot.

## Orchestration

`EvaluationSuiteRunner.execute(suite_id)` reads the ordered suite and snapshots all
cases before creating the suite-run id. It invokes the existing
`EvaluationRunner.execute(case_id)` sequentially. A returned execution becomes a
result item. A known execution/configuration/conflict failure becomes a stable
`execution_error` item and processing continues. `CancelledError` is never
converted; the active `EvaluationRunner` performs session cleanup before the
cancellation escapes.

The complete aggregate is persisted once all items reach an outcome. Cancellation
does not write a misleading partial terminal suite run in this milestone.

## Public boundaries

```text
POST /evaluations/suites
PUT  /evaluations/suites/{suite_id}
GET  /evaluations/suites
GET  /evaluations/suites/{suite_id}
POST /evaluations/suites/{suite_id}/execute
GET  /evaluations/suite-runs
GET  /evaluations/suite-runs/{run_id}
```

The execution endpoint accepts no provider or prompt body. The CLI composes the
same tools, repositories, chat manager, case runner, and suite runner over one
database, then closes all residual sessions in `finally`.

## Trade-offs

Persisting item JSON keeps the first suite milestone inspectable and migration-light
while retaining immutable snapshots. It is less queryable than normalized item
rows; a later analytics milestone can introduce a projection table without changing
the public model. Sequential execution is slower than bounded parallel execution but
provides deterministic order and avoids surprising provider bursts.
