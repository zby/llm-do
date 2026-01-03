# OAuth / Model Selector UI

## Idea
Add a unified TUI selector for OAuth providers, model selection, and optional reasoning presets.

## Why
Current OAuth login/status is CLI-only; the Textual UI lacks any selector surfaces. A unified selector would reduce friction and keep configuration in one place.

## Rough Scope
- New Textual screen/modal for provider login/status (OAuth)
- Model selector integrated with model compatibility rules
- Optional reasoning presets (if supported by model)
- Hook into existing approval workflow without conflating approvals with input prompts

## Why Not Now
UI work needs a cohesive selector pattern; also requires additional UX design for inputs (e.g., `code#state` paste).

## Trigger to Activate
When we decide to add interactive selectors to the TUI (providers + models) and finalize reasoning UX.
