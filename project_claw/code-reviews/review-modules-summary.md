---
description: Summary of the 2026-02-01 modules bug/inconsistency review.
---

# Review Modules Summary (2026-02-01)

## Highlights
- Chat mode remains effectively stateless because message history is not forwarded to entry agents; the UI shows a conversation but the runtime only sees the latest prompt.
- `allow_cli_input=false` does not block piped stdin, so manifests cannot fully forbid CLI-supplied input.
- Shell metacharacter blocking relies on the approval wrapper; direct toolset calls can bypass the block.

## Coverage Check
- All paths listed in `tasks/recurring/review-modules.md` exist as of 2026-02-01.
- Potential gaps: `llm_do/providers/*` (provider wrappers) are not covered by the batched review.
- `llm_do/runtime/path_refs.py` is part of the runtime but is not listed in the batched scope; consider adding it so entry/path resolution helpers are reviewed together.
- Notes updated: `docs/notes/reviews/review-ctx-runtime.md`, `docs/notes/reviews/review-toolsets.md`, `docs/notes/reviews/review-ui.md`, `docs/notes/reviews/review-ui-controllers.md`, `docs/notes/reviews/review-config-auth.md`.

## Suggested Follow-ups
- Decide whether message history should be owned by the runtime and forwarded to depth-0 agents.
- Decide whether stdin should respect `allow_cli_input=false` (or rename the flag for clarity).
- Add defense-in-depth metacharacter checks in shell execution, not only in approval decisions.
