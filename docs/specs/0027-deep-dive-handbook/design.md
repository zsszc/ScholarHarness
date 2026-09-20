# Design: standalone deep-dive handbook

The deliverable is `docs/scholar-harness-deep-dive.html`, a single UTF-8 HTML file
with embedded CSS, SVG and a small progressive-enhancement script. `<details>`
keeps question answers readable without JavaScript. No fetch, CDN or server API.

The main narrative runs from system boundary to one turn, then down into domain
subsystems and up to deployment/evaluation. Diagrams are manually authored SVG
with accessible labels and HTML fallbacks. A compact flow stepper may highlight
the chat path; CSS respects reduced motion. A sticky table of contents and search
filter make the long file usable on desktop and mobile.

Use current repository source and tests as the authoritative evidence. Link to
relative source files for readers who opened the file from the checkout. Mark
algorithms such as RRF and exact vector scan precisely. Avoid importing claims
from current provider marketing, PiX, or unstated production deployments.

Do not embed `.env`, database content, traces, chat prompts, or API keys. The
report is source-derived, not a snapshot of private runtime state.
