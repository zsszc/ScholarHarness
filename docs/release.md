# Release checklist

Use this checklist before creating a tag or publishing a package. Publication and
tagging remain explicit repository-owner actions.

## Verify the tree

- [ ] `git status --short --branch` is clean and synchronized with `origin/main`.
- [ ] `uv lock --check`, `uv run ruff check .`, and `uv run pytest` pass.
- [ ] `python -m compileall -q src` and `uv run scholar-harness pi-smoke` pass.
- [ ] The offline benchmark correctness checks are all true; performance changes are
      interpreted on comparable hardware rather than treated as universal gates.

## Build and inspect

- [ ] `uv build` produces one `.whl` and one `.tar.gz` under `dist/`.
- [ ] Install the wheel into a fresh temporary virtual environment.
- [ ] `scholar-harness --help` works and `scholar_harness.__version__` matches the
      intended tag, `pyproject.toml`, the FastAPI version, and Pi extension version.
- [ ] Wheel/sdist contents exclude `.env`, databases, WAL files, caches, sessions,
      credentials, benchmark scratch data, and virtual environments.

## Review evidence

- [ ] `CHANGELOG.md` describes only shipped behavior.
- [ ] README, portfolio, architecture, benchmark, and SDD verification links resolve.
- [ ] `docs/benchmark.json` identifies the implementation commit and all correctness
      checks pass.
- [ ] Search tracked files for secrets and generated user data before tagging.
- [ ] Mandatory CI is green; credentialed evaluation gates are reviewed separately
      when configured.

## Publish

- [ ] Commit any deliberate version/changelog update.
- [ ] Create a signed `v0.1.0` tag only after the version checks above pass.
- [ ] Push the tag, verify GitHub Actions, inspect uploaded artifacts, and create the
      release notes from the matching changelog section.
- [ ] Publish to a package index only after an owner explicitly chooses credentials,
      target index, and provenance policy.
