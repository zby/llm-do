# Custom Tool Context Injection (Opt-in)

## Prerequisites
- [ ] none

## Goal
Allow tools in `tools.py` to opt into receiving context so they can call LLM workers, without complicating simple tools.

## Tasks
- [x] Define an opt-in decorator for custom tools (e.g., `@tool_context`) that marks a function as context-aware
- [x] Update custom tool schema generation to ignore injected context parameters
- [x] Inject context when calling marked tools (support sync + async tools)
- [x] Add tests covering schema omission + context injection behavior
- [x] Update docs/notes if needed to explain the opt-in path

## Current State
Implemented `@tool_context` with schema omission and runtime injection. Added tests and updated README.

## Notes
- Keep simple tools unchanged; only marked tools receive context.
- Context parameter should not appear in JSON schema exposed to the LLM.
