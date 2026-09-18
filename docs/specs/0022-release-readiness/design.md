# Release readiness design

## Mandatory CI

`.github/workflows/ci.yml` is intentionally credential-free. It checks out the
repository, installs uv from a commit-pinned action, synchronizes the locked dev
environment, executes the same local gates, runs a small offline benchmark, builds
wheel/sdist artifacts, and uploads `dist/` only after success. Workflow permissions
are `contents: read`.

The model-backed `eval-gate` remains documented as an optional organization-specific
workflow because it needs a suite database and provider secrets. Keeping it out of
mandatory PR CI prevents forks from failing for unavailable credentials.

## Package and release evidence

Project metadata remains version 0.1.0 across package, FastAPI, and build metadata.
URLs point to the public repository. The changelog records the current initial
release without implying previous published versions.

`docs/release.md` is a human checklist rather than an automatic publisher. The
agent may verify local artifacts, but tagging and package publication remain an
explicit owner decision.

## Repository contract tests

Tests parse source text and TOML using the standard library. A small Markdown link
scanner validates relative file links in maintained top-level documents while
ignoring URLs, anchors, and code examples. Workflow source assertions avoid adding
a YAML dependency while still pinning the observable release contract.

## Trade-offs

Ubuntu CI validates the supported Python baseline but does not form a full OS/Python
matrix. This keeps the portfolio signal fast and understandable; a compatibility
matrix can be added when the package has external users.
