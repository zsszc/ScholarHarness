# Design: Chinese guided workbench

## Approach

Keep the self-contained server-rendered Workbench and its existing public API
calls. Localize user-visible copy in place, add a seventh `guide` view, and use the
existing navigation function so the guide introduces no new frontend framework or
state model.

The guide is a static orientation surface with a numbered learning path and one
card per functional area. It deliberately preserves technical nouns that a job
candidate should be able to discuss while translating their surrounding meaning.

## Provider configuration

The service continues to read the existing OpenAI-compatible environment contract:
`OPENAI_MODEL`, `OPENAI_BASE_URL`, and `OPENAI_API_KEY`. A tracked `.env.example`
contains only placeholders. A real `.env` remains ignored and is loaded explicitly
when starting via `uv run --env-file .env ...`; no browser field or persisted API
record receives the secret.

## Trade-offs

- Static copy is intentionally simple and dependency-free, but is not a general
  internationalization framework.
- Backend status values remain their stable English wire values; the UI translates
  display labels without changing API semantics.

