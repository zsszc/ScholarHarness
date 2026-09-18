# CI regression gate

Status: Approved
Date: 2026-09-18

## Problem

`eval-suite-run` executes and prints a suite run, but a CI system cannot distinguish
a completed failing regression gate from success by process status, and common test
report viewers cannot ingest the result. ScholarHarness needs a stable automation
command that preserves its structured evidence while speaking conventional CI exit
codes and JUnit XML.

## Requirements

- **CIGATE-001**: Add `scholar-harness eval-gate --suite ... --database ...` that
  executes the persisted suite through the existing configured suite runner.
- **CIGATE-002**: A completed passing suite MUST exit 0; a completed suite with a
  failed or error item MUST exit 1; invalid configuration, unknown resources, and
  command usage MUST exit 2.
- **CIGATE-003**: The command MUST print the complete persisted suite-run JSON to
  stdout before returning a completed-suite exit status.
- **CIGATE-004**: Optional `--json-output PATH` MUST write the same suite-run JSON as
  stdout using UTF-8 and create missing parent directories.
- **CIGATE-005**: Optional `--junit-output PATH` MUST write standards-compatible
  JUnit XML with one testcase per ordered suite item, aggregate tests/failures/errors
  counts, suite timing, and identifying properties.
- **CIGATE-006**: A deterministic evaluation failure MUST map to a JUnit `<failure>`;
  an orchestration error MUST map to `<error>`; a passing item MUST contain neither.
- **CIGATE-007**: Report files MUST be replaced atomically so readers never observe
  a partially written artifact.
- **CIGATE-008**: JSON, XML, stderr, and exit behavior MUST NOT reveal provider API
  keys, base URLs, or raw provider errors beyond already-safe public categories.
- **CIGATE-009**: Report ordering MUST match the persisted suite item positions and
  XML content MUST correctly escape suite/case/user-authored text.
- **CIGATE-010**: Document a copyable local command and GitHub Actions pattern,
  including artifact publication even when the gate fails.
- **CIGATE-011**: Existing `eval-suite-run` behavior MUST remain backward compatible.

## Decisions

- `eval-gate` is a separate command instead of changing `eval-suite-run`; interactive
  users and existing scripts keep the current zero-on-completed-run behavior.
- Stdout always contains JSON so CI logs retain evidence even when no output paths
  are configured. Human summaries can be derived by `jq` rather than introducing a
  second output mode.
- Python's standard XML library produces JUnit, avoiding another runtime dependency.
- Reports are written only for a completed suite run. Configuration and lookup
  failures use argparse's error path and do not create misleading artifacts.

## Acceptance criteria

- **AC-CIGATE-001**: CLI tests prove passing and failing suite runs return 0 and 1
  respectively while printing parseable persisted JSON. (CIGATE-001..003)
- **AC-CIGATE-002**: Configuration, lookup, and parser tests prove exit code 2 and
  absence of report artifacts. (CIGATE-002, CIGATE-008)
- **AC-CIGATE-003**: Report tests verify UTF-8 JSON parity, parent creation, atomic
  replacement, and no temporary files after success. (CIGATE-004, CIGATE-007)
- **AC-CIGATE-004**: JUnit tests cover pass/failure/error items, aggregate counts,
  timing, stable ordering, identifiers, and XML escaping. (CIGATE-005, CIGATE-006,
  CIGATE-009)
- **AC-CIGATE-005**: Existing suite CLI tests continue to pass unchanged.
  (CIGATE-011)
- **AC-CIGATE-006**: README/CI documentation contains runnable local and GitHub
  Actions examples with always-published JSON/JUnit artifacts. (CIGATE-010)
- **AC-CIGATE-007**: Lock consistency, lint, all tests, compilation, Pi smoke, and
  live HTTP bridge smoke pass.
