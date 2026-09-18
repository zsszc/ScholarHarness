# Chinese guided workbench

Status: Verified
Date: 2026-09-19

## Problem

The Workbench exposes the full harness, but its mixed Chinese/English copy assumes
that the reader already understands the internal architecture. A Chinese-speaking
learner needs a clear path from importing papers to chatting, reviewing memory,
inspecting traces, and running evaluations.

## Requirements

- **ZHUI-001**: The Workbench MUST use Chinese for navigation, headings, actions,
  status messages, empty states, detail labels, and explanations, while retaining
  necessary technical terms such as Agent, Runtime, Tool Calling, Prompt, Case,
  Suite, OpenAPI, and identifiers.
- **ZHUI-002**: The Workbench MUST provide an in-product usage guide that explains
  the recommended end-to-end workflow and the purpose of every main area.
- **ZHUI-003**: The guide MUST explain the trust boundary between candidate and
  confirmed memory, and the relationship between chat, traces, tools, and
  deterministic evaluation.
- **ZHUI-004**: Existing routes, API contracts, safe DOM rendering, responsive
  behavior, and no-external-assets policy MUST remain unchanged.
- **ZHUI-005**: Local provider configuration MUST be documented using ignored
  environment files without including real credentials in tracked files.

## Acceptance criteria

- **AC-ZHUI-001**: Source assertions cover Chinese navigation, guide content, and
  localized connection/state labels. (ZHUI-001, ZHUI-002)
- **AC-ZHUI-002**: The guide describes literature, chat, trace, memory, Case, and
  Suite workflows plus the candidate/confirmed boundary. (ZHUI-002, ZHUI-003)
- **AC-ZHUI-003**: Existing Workbench contract tests and full repository gates pass.
  (ZHUI-004)
- **AC-ZHUI-004**: A credential-free example documents DeepSeek-compatible local
  configuration and `.env` remains ignored. (ZHUI-005)
