# ScholarHarness Development Contract

## Spec-driven development

All non-trivial changes follow the repository SDD workflow in `docs/sdd/README.md`.

1. Create or update a feature specification before implementation.
2. Give every observable requirement a stable requirement id.
3. Record architecture and trade-offs in `design.md`.
4. Track implementation and tests in `tasks.md`.
5. Do not mark a feature verified until its acceptance criteria have evidence in
   `verification.md`.
6. When implementation changes behavior, update the specification in the same
   commit.

Small bug fixes may use a short specification, but must still state the expected
behavior and regression test.

## Verification

Run before committing:

```bash
uv run ruff check .
uv run pytest
python -m compileall -q src
uv run scholar-harness pi-smoke
```

Run `uv run scholar-harness pi-smoke --check-service` when changing the Pi bridge
or HTTP tool boundary.

## Commit policy

- Commit at verified, independently understandable milestones.
- Use imperative Conventional Commit subjects such as `feat: persist agent traces`.
- Keep generated databases, credentials, local sessions, caches, and virtual
  environments out of Git.
- Do not combine unrelated refactors with a feature implementation.
