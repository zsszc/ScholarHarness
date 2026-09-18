# Portfolio delivery

Status: Verified
Date: 2026-09-18

## Problem

ScholarHarness has substantial implementation evidence, but a recruiter or
interviewer should not need to reconstruct its story from twenty specifications.
The repository needs a concise, reproducible delivery layer that demonstrates the
system without paid model access, quantifies local data-path performance without
marketing claims, and makes limitations and design ownership explicit.

## Requirements

- **PORTFOLIO-001**: Provide an offline benchmark command for paper ingestion,
  hybrid retrieval, and trace-event persistence using a temporary isolated database
  by default.
- **PORTFOLIO-002**: Benchmark inputs MUST be validated and configurable; output
  MUST be versioned JSON containing workload sizes, elapsed durations, throughput,
  environment metadata, and deterministic correctness checks.
- **PORTFOLIO-003**: Benchmark output MAY be written atomically to a requested path
  and MUST leave no default database artifact behind.
- **PORTFOLIO-004**: Benchmark metrics MUST be descriptive rather than pass/fail
  thresholds and documentation MUST state that results are machine-specific.
- **PORTFOLIO-005**: Provide a portfolio guide with a three-minute demo, architecture
  narrative, key engineering decisions, interview questions, and truthful resume
  bullets linked to repository evidence.
- **PORTFOLIO-006**: Provide an explicit limitations and next-steps section covering
  deployment, OCR, embeddings, model nondeterminism, security scope, and scale.
- **PORTFOLIO-007**: The README MUST identify the project as portfolio-ready, link
  directly to the demo/benchmark/architecture/SDD evidence, and offer a fast
  evaluator path.
- **PORTFOLIO-008**: The checked-in benchmark report MUST record the exact command,
  workload, environment, results, and verification commit without claiming
  cross-machine comparability.

## Acceptance criteria

- **AC-PORTFOLIO-001**: Unit and CLI tests prove validation, deterministic checks,
  versioned JSON, atomic output, and temporary cleanup. (PORTFOLIO-001..004)
- **AC-PORTFOLIO-002**: A real benchmark run produces a checked-in report whose
  values match its JSON artifact and identifies the implementation commit.
  (PORTFOLIO-004, 008)
- **AC-PORTFOLIO-003**: Documentation review confirms the demo, architecture story,
  resume bullets, interview prompts, evidence links, and limitations are internally
  consistent. (PORTFOLIO-005..007)
- **AC-PORTFOLIO-004**: A clean evaluator path runs lock check, lint, all tests,
  compilation, Pi smoke, and the benchmark without external model credentials.

## Non-goals

- Benchmark numbers are not service-level objectives or comparisons with unrelated
  frameworks.
- Delivery documents do not claim production multi-tenancy, autonomous scientific
  correctness, or experience not demonstrated in this repository.
