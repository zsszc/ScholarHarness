# Release readiness verification

Status: Verified
Date: 2026-09-18

## Automated verification

```text
uv lock --check: resolved 33 packages
uv run ruff check .: all checks passed
uv run pytest: 155 passed, 2 upstream warnings in 1.79s
python -m compileall -q src: exit 0
uv run scholar-harness pi-smoke: pi_rpc=ok, extension=ok, entry_count=1
benchmark smoke: all four correctness checks true
uv build:
  dist/scholar_harness-0.1.0.tar.gz
  dist/scholar_harness-0.1.0-py3-none-any.whl
```

## Package installation evidence

The wheel was installed with all runtime dependencies into a new temporary Python
3.12 virtual environment outside the repository:

```text
scholar-harness --help: exit 0; all ten subcommands listed
python -c 'import scholar_harness; print(scholar_harness.__version__)': 0.1.0
wheel inspection: 54 files; py.typed and LICENSE present
database/session/cache/credential files: absent
```

The temporary environment was deleted after inspection. Build artifacts remain in
the Git-ignored `dist/` directory for local owner review.

## Acceptance evidence

- **AC-RELEASE-001**:
  `test_mandatory_ci_is_pinned_credential_free_and_complete` verifies push/PR
  triggers, read-only permissions, 40-character action SHAs, pinned Pi 0.85.1,
  every mandatory command, absence of secret references, and build-before-upload
  ordering.
- **AC-RELEASE-002**:
  `test_public_markdown_relative_links_resolve` validates maintained public docs.
  Metadata tests prove package/API/extension version parity, repository URLs,
  classifiers, and the PEP 561 marker. Release evidence tests prove README links and
  required checklist content.
- **AC-RELEASE-003**: `uv build` produced wheel and sdist. A clean environment
  installed the wheel from `dist/`, imported version 0.1.0, and ran CLI help. Archive
  inspection confirmed expected package files and excluded runtime data.
- **AC-RELEASE-004**: `CHANGELOG.md` records only the initial 0.1.0 implementation.
  `docs/release.md` covers clean-tree gates, build/install inspection, benchmark
  interpretation, secret/generated-data review, version/tag consistency, CI, and
  explicit owner-controlled publication.
- **AC-RELEASE-005**: The final tree passed lock consistency, lint, all 155 tests,
  compilation, real Pi RPC/extension smoke, benchmark smoke, and package build.

## Boundary result

The repository now matches its release claims: mandatory credential-free CI is
checked in, Python distributions build and install cleanly, public links and version
metadata are regression-tested, and owner-controlled release steps are documented.
No tag or external package publication was performed.
