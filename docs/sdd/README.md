# Spec-driven development

ScholarHarness uses a lightweight spec-driven development workflow. Specifications
are the source of truth for observable behavior; code is an implementation of an
accepted specification.

## Feature directory

Each non-trivial feature lives in `docs/specs/NNNN-feature-name/`:

```text
spec.md          user-visible behavior, requirements, acceptance criteria
design.md        architecture, data model, failure modes, trade-offs
tasks.md         implementation checklist mapped to requirement ids
verification.md  commands and evidence proving the acceptance criteria
```

## Status lifecycle

```text
Draft -> Approved -> Implementing -> Verified -> Superseded
```

- **Draft**: requirements are still being shaped; implementation must not begin.
- **Approved**: scope and acceptance criteria are stable enough to implement.
- **Implementing**: code and tests are in progress.
- **Verified**: every acceptance criterion has recorded evidence.
- **Superseded**: a newer specification replaces this behavior.

Approval can be explicit user approval or an implementation request whose scope is
already unambiguous. Material scope changes return the specification to Draft.

## Requirement format

Requirements use stable ids:

```text
RUNTIME-001: The service MUST correlate each Pi RPC response with its request id.
```

Use MUST for required behavior, SHOULD for a deliberate default, and MAY for an
optional capability. Acceptance criteria reference these ids so that tests and
implementation decisions remain traceable.

## Commit boundary

A normal feature produces at least two logical checkpoints when its size warrants
it:

1. `docs: specify <feature>` after the specification is approved.
2. `feat: implement <feature>` after verification passes.

For the initial repository baseline, the retrospective foundation specification and
its already-verified implementation are committed together.
