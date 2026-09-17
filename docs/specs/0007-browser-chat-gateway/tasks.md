# Browser chat session gateway tasks

Status: Planned

- [x] Define session lifecycle, server-owned configuration, protocol, failure
  modes, and acceptance criteria.
- [x] Approve requirements for implementation.
- [ ] Implement `ChatSession` and concurrency-safe session manager. (CHAT-001,
  CHAT-008, CHAT-009)
- [ ] Add server-only adapter configuration and explicit unavailable behavior.
  (CHAT-002, CHAT-012)
- [ ] Add session REST endpoints and application shutdown cleanup. (CHAT-003,
  CHAT-008)
- [ ] Add ordered WebSocket command/event gateway. (CHAT-004..007)
- [ ] Build the workbench Chat page, state model, controls, and safe renderers.
  (CHAT-010, CHAT-011)
- [ ] Add manager, API, WebSocket, lifecycle, configuration, and workbench tests.
- [ ] Update architecture and usage documentation.
- [ ] Record verification evidence and mark the specification Verified.
