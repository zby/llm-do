# Reintroduce --all-tools (Controlled)

## Idea
Bring back a safe, predictable `--all-tools` flag that exposes discovered toolsets to the entry worker without reloading or dropping configuration.

## Why
The escape-hatch is convenient for ad-hoc runs, but the earlier implementation could silently drop worker config and reload toolsets inconsistently.

## Rough Scope
- Define the desired behavior (toolset reuse, config preservation, approval wrapping).
- Update runtime code to preserve worker fields when expanding toolsets.
- Add tests covering toolset instance reuse and config retention.
- Update CLI docs and help text.

## Why Not Now
We need a clearer design for instance reuse and field preservation to avoid regressions.

## Trigger to Activate
Agreement on the intended semantics and a test plan for the edge cases.
