# Workbench state resilience design

The shared helper first queries the existing `[data-state]` node. When absent, it
looks up a same-id host such as `run-detail`, creates a normal `.state` element,
assigns the requested state key, and prepends it. A missing host is treated as a
no-op because status presentation must not crash otherwise successful data loading.

This keeps individual renderers unchanged and covers every detail panel that
replaces its initial placeholder.
