# Integrate llm-do Workers into TunaCode

## Idea
Expose llm-do workers as a TunaCode tool so TunaCode provides the TUI while llm-do handles worker execution.

## Why
Avoid duplicating TUI features in llm-do and gain a richer interactive shell experience.

## Rough Scope
- Add an integration module for global worker context and approval callbacks.
- Implement a TunaCode tool that calls llm-do workers.
- Wire initialization and tool registration in TunaCode.
- Optional: streaming progress callbacks.

## Why Not Now
Requires coordination with TunaCode and validation of its plugin API stability.

## Trigger to Activate
A concrete request to ship a TunaCode integration or decision to focus on external TUI adoption.
