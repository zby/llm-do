---
description: Periodic review findings for UI controllers.
---

# UI Controllers Review

## Context
Review of UI controller components for bugs, inconsistencies, and overengineering.

## Review 2026-02-01

### Findings
- No correctness issues found; controllers are small and single-purpose (approval workflow queue, input history, exit confirmation, agent runner).
- `AgentRunner` maintains `message_history`, but runtime currently ignores it, so history remains UI-only. (See UI review for details.)

### Open Questions
- Should `AgentRunner` own more of the chat state, or should it stay thin while runtime handles history?
- Do we need a controller-level guard that prevents input submission while an agent task is running (rather than relying on UI checks)?

### Conclusion
Controllers are small and composable; the only gap is that message_history is not consumed downstream.
