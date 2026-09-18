# CI regression gates

`eval-gate` executes a persisted Evaluation Suite and maps its outcome to standard
CI semantics:

| Exit code | Meaning |
| --- | --- |
| `0` | Every suite item passed |
| `1` | The suite completed, but at least one item failed or errored |
| `2` | Configuration, lookup, report-writing, or command usage error |

## Local gate

```bash
export OPENAI_MODEL="your-model-id"
export OPENAI_API_KEY="your-key"

uv run scholar-harness eval-gate \
  --suite SUITE_ID \
  --database data/scholar_harness.db \
  --json-output artifacts/evaluation-gate.json \
  --junit-output artifacts/evaluation-gate.xml
```

The complete persisted suite run is always printed to stdout after a completed
execution. Report parent directories are created automatically. A quality failure
still writes both reports before exiting 1; an operational error exits 2 without
creating reports.

## GitHub Actions

The example assumes `vars.SCHOLAR_EVAL_SUITE_ID`, a base64-encoded persisted database
in `secrets.SCHOLAR_EVAL_DATABASE_B64`, provider variables, and an optional API key.
The database is restored at runtime because generated research state stays out of
Git.

```yaml
name: ScholarHarness regression gate

on:
  workflow_dispatch:
  pull_request:

jobs:
  evaluation-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - name: Install uv
        uses: astral-sh/setup-uv@bec219d24cd3e171d82865faccec33120bb574f4 # v10.1.0

      - name: Install project
        run: uv sync --locked

      - name: Restore evaluation database
        env:
          DATABASE_B64: ${{ secrets.SCHOLAR_EVAL_DATABASE_B64 }}
        run: |
          mkdir -p data
          printf '%s' "$DATABASE_B64" | base64 --decode > data/ci-evaluations.db

      - name: Run evaluation gate
        id: gate
        continue-on-error: true
        env:
          OPENAI_MODEL: ${{ vars.OPENAI_MODEL }}
          OPENAI_BASE_URL: ${{ vars.OPENAI_BASE_URL }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          uv run scholar-harness eval-gate \
            --suite "${{ vars.SCHOLAR_EVAL_SUITE_ID }}" \
            --database data/ci-evaluations.db \
            --json-output artifacts/evaluation-gate.json \
            --junit-output artifacts/evaluation-gate.xml

      - name: Upload evaluation evidence
        if: always()
        uses: actions/upload-artifact@v7
        with:
          name: scholar-harness-evaluation
          path: artifacts/
          if-no-files-found: warn

      - name: Enforce evaluation result
        if: steps.gate.outcome == 'failure'
        run: exit 1
```

`continue-on-error` applies only to the gate step so artifact upload still runs. The
final step restores the captured failure and prevents the job from falsely passing.
For GitHub Enterprise Server, select artifact action versions supported by the
installed runner; current `upload-artifact@v4+` releases target GitHub.com.
