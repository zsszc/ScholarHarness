# Verification: Chinese guided workbench

Status: Verified
Date: 2026-09-19

## Automated evidence

- `uv run ruff check .`: passed.
- `uv run pytest`: 156 passed with two upstream deprecation warnings.
- `python -m compileall -q src`: passed.
- `uv run scholar-harness pi-smoke`: Pi RPC and extension passed.
- `uv run scholar-harness pi-smoke --check-service`: Pi RPC, extension, and HTTP
  tool service passed.
- Workbench source regressions assert the guide route, Chinese primary labels,
  Chinese connection states, technical terms, and all prior safe-DOM/API contracts.

## Browser evidence

- Reloaded `/workbench` and confirmed Chinese navigation, overview metrics, status
  labels, and the responsive guide view.
- Opened **使用指南** and confirmed the five-stage workflow plus cards for
  literature, chat, memory trust, traces, Case, and Suite.
- Opened **Agent 对话**, created a fresh persistent MiniPy session, and completed a
  real browser turn through DeepSeek. The answer, trace id, normalized lifecycle
  events, and empty memory-context decision rendered successfully.

## Credential evidence

- `.env` is matched by `.gitignore` and has mode `0600` locally.
- `git status` exposes only `.env.example`; the real credential is not staged or
  tracked.
- A minimal CLI request using `uv run --env-file .env scholar-harness chat` returned
  the expected DeepSeek response.
