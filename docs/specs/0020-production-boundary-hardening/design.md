# Production boundary hardening design

## Authenticated provenance

`create_app` resolves an explicitly injected bridge token or
`SCHOLAR_HARNESS_BRIDGE_TOKEN`. Empty strings normalize to disabled development
mode. The internal tool endpoint detects whether any runtime provenance header is
present. If provenance exists and a token is configured, `secrets.compare_digest`
validates `X-Scholar-Bridge-Token` before constructing `ToolExecutionContext` or
calling the registry.

The Pi extension reads the same environment variable and appends the token only in
`executionHeaders`. Health and provenance-free retrieval retain their current local
behavior. Production guidance requires setting the same high-entropy value for the
API and Pi process.

## SQLite connection policy

`storage.sqlite` centralizes connection construction. Connections use named rows,
foreign keys, and a 5-second SQLite busy timeout. Repository initialization calls a
separate database policy helper that requests WAL plus `synchronous=NORMAL` for file
databases. SQLite may return another journal mode for `:memory:`; this is accepted.

Repositories retain ownership of schemas and transactions. The helper changes
contention behavior, not domain persistence semantics. Existing explicit
`BEGIN IMMEDIATE`, commit, and rollback boundaries remain intact.

## Failure behavior

Bridge authentication fails before tool lookup so unknown tool names cannot become
an oracle for unauthenticated provenance callers. Both absent and incorrect tokens
return `401 Invalid bridge credentials`.

SQLite waits only for the configured timeout. A longer lock still raises the native
operational failure rather than retrying forever, preserving bounded request time.

## Trade-offs

The shared secret protects trusted local provenance but is not a replacement for
network isolation or TLS. WAL improves mixed read/write concurrency and recovery at
the cost of sidecar files; those files remain runtime data and are ignored by Git.
