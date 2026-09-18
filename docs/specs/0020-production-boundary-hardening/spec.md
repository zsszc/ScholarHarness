# Production boundary hardening

Status: Approved
Date: 2026-09-18

## Problem

The Pi bridge currently treats localhost provenance headers as trusted, and each
repository configures SQLite independently. Localhost alone does not authenticate a
caller, while concurrent API, chat, evaluation, and Pi writes need one explicit
locking policy. The final technical baseline needs secure provenance transport and
predictable SQLite contention behavior without making local development difficult.

## Requirements

- **HARDEN-001**: When `SCHOLAR_HARNESS_BRIDGE_TOKEN` is configured, any internal
  tool request carrying runtime provenance headers MUST provide the identical token
  in `X-Scholar-Bridge-Token`.
- **HARDEN-002**: Missing or invalid bridge credentials MUST return the same 401
  response without executing the tool or disclosing whether a token was close.
- **HARDEN-003**: Token comparison MUST be constant-time, tokens MUST not enter tool
  arguments, results, traces, logs, or public schemas, and blank configured values
  MUST behave as disabled development mode.
- **HARDEN-004**: The Pi extension MUST read the token from its environment and add
  it only to provenance-bearing execution headers; no token literal may be bundled.
- **HARDEN-005**: Unauthenticated health checks and provenance-free read-only tool
  calls MUST remain available for local Workbench and operational checks.
- **HARDEN-006**: Every SQLite repository MUST use one shared connection policy with
  foreign keys enabled, a bounded busy timeout, and row access by name.
- **HARDEN-007**: Repository initialization MUST enable WAL journal mode and normal
  synchronous durability for file databases so readers and serialized writers can
  overlap predictably.
- **HARDEN-008**: Concurrent writes within the busy-timeout window MUST complete
  without leaking `database is locked`; transactions that fail for other reasons
  MUST retain their existing rollback behavior.
- **HARDEN-009**: In-memory SQLite databases MUST remain supported without assuming
  WAL is available.

## Acceptance criteria

- **AC-HARDEN-001**: API tests prove valid, missing, invalid, disabled, and
  provenance-free bridge behavior, including no tool execution on 401.
  (HARDEN-001..003, 005)
- **AC-HARDEN-002**: Extension source tests prove environment-only token forwarding
  and absence from model-visible schemas. (HARDEN-003, 004)
- **AC-HARDEN-003**: Shared-connection tests cover every repository and verify
  foreign keys, busy timeout, WAL/normal mode, row access, and in-memory fallback.
  (HARDEN-006, 007, 009)
- **AC-HARDEN-004**: A deterministic lock-contention test proves a second repository
  writer waits and succeeds after the first transaction commits. (HARDEN-008)
- **AC-HARDEN-005**: Lock consistency, lint, all tests, compilation, Pi smoke, and
  authenticated live bridge smoke pass.

## Non-goals

- This milestone does not expose ScholarHarness to the public internet or add user
  accounts, TLS termination, or multi-tenant authorization.
- Provenance-free calls can only exercise existing tool trust rules; they cannot
  create scoped trusted provenance.
