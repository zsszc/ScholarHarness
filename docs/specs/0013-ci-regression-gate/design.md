# CI regression gate design

## Command flow

```text
eval-gate arguments
  -> run_configured_evaluation_suite
  -> completed EvaluationSuiteRun
  -> stdout JSON
  -> optional atomic JSON report
  -> optional atomic JUnit report
  -> exit 0 when run.passed else 1

configuration / lookup failure
  -> argparse error on stderr
  -> exit 2, no artifacts
```

The new command reuses suite orchestration without adding model, session, or tool
logic. It deliberately does not catch the final `SystemExit(1)` as an operational
error.

## Report boundary

`evaluations/reports.py` owns pure serialization and atomic path writing:

- JSON uses `EvaluationSuiteRun.model_dump_json(indent=2)` plus a final newline.
- JUnit uses `xml.etree.ElementTree`, never string interpolation, so names, prompts,
  and categories are escaped correctly.
- A temporary file is created in the target directory, flushed and replaced with
  `os.replace`; cleanup removes the temporary file if serialization or replacement
  fails.

The JUnit root is `<testsuites>` containing one `<testsuite>`. Each item becomes one
ordered `<testcase>`. Deterministic non-passing results receive `<failure>` with the
public score/threshold context. Items with `error` receive `<error>` containing only
the stable category. Properties carry suite/run/case/result/trace ids and counts.

## Exit semantics

| Outcome | Exit |
| --- | ---: |
| Completed suite, every item passed | 0 |
| Completed suite, any failed/error item | 1 |
| Missing provider configuration | 2 |
| Unknown suite or invalid CLI usage | 2 |

This distinguishes product quality failure from a gate that could not be configured
or invoked.

## CI documentation

`docs/ci.md` shows environment setup, the gate command, and GitHub Actions steps.
The execution step has an id and `continue-on-error: true`; artifact upload uses
`if: always()`, followed by a final step that propagates the captured gate outcome.
This ensures reports survive a quality failure without masking it.
