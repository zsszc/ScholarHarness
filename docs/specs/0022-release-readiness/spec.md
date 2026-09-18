# Release readiness

Status: Verified
Date: 2026-09-18

## Problem

The portfolio is reproducible locally, but the repository documents GitHub Actions
without checking in a workflow and has no release history or packaging evidence. A
reviewer should see an executable credential-free CI baseline, installable build
artifacts, and an explicit statement of what version 0.1.0 contains.

## Requirements

- **RELEASE-001**: Check in a GitHub Actions workflow triggered by pushes and pull
  requests that uses the locked environment and runs lock validation, lint, tests,
  compilation, benchmark smoke, and package build.
- **RELEASE-002**: CI MUST require no model credentials, persisted databases, or
  external research data and MUST upload wheel/sdist artifacts only after all gates
  pass.
- **RELEASE-003**: CI action dependencies MUST be version-pinned and permissions
  MUST default to read-only repository contents.
- **RELEASE-004**: `pyproject.toml` MUST expose repository, documentation, and issue
  URLs plus Python/topic classifiers appropriate to the demonstrated package.
- **RELEASE-005**: A changelog MUST summarize version 0.1.0 by user-visible area and
  link claims to repository evidence without inventing release history.
- **RELEASE-006**: A release checklist MUST cover clean-tree verification, tests,
  benchmark interpretation, package build/inspection, secret/generated-data audit,
  version/tag consistency, and post-push verification.
- **RELEASE-007**: README MUST show the real CI workflow status and link the release
  evidence.
- **RELEASE-008**: Automated repository tests MUST catch missing local Markdown
  links, missing CI gates, inconsistent package/API versions, and absent release
  files.

## Acceptance criteria

- **AC-RELEASE-001**: Source tests inspect the workflow triggers, permissions,
  pinned actions, required credential-free commands, and artifact upload ordering.
  (RELEASE-001..003)
- **AC-RELEASE-002**: Repository metadata tests prove local Markdown links resolve,
  version declarations agree, project URLs/classifiers exist, and release artifacts
  are linked. (RELEASE-004, 007, 008)
- **AC-RELEASE-003**: `uv build` produces both wheel and sdist, and the wheel installs
  into an isolated environment where the CLI reports help and imports version
  0.1.0. (RELEASE-004)
- **AC-RELEASE-004**: Changelog and checklist review prove all required evidence and
  honest 0.1.0 scope are present. (RELEASE-005, 006)
- **AC-RELEASE-005**: Lock consistency, lint, all tests, compilation, Pi smoke,
  benchmark smoke, and package build pass from the final tree.

## Non-goals

- This milestone does not publish to PyPI or create a Git tag/release on the user's
  behalf.
- The credentialed model evaluation gate remains an opt-in workflow documented in
  `docs/ci.md`, separate from mandatory pull-request CI.
