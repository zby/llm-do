# Review: Runtime Core

Periodic review of runtime infrastructure for bugs, inconsistencies, and overengineering.

## Scope

- `llm_do/cli/main.py` - CLI entry point
- `llm_do/runtime/agent_runner.py` - Agent execution helpers
- `llm_do/runtime/call.py` - Call execution
- `llm_do/runtime/contracts.py` - Runtime contracts/interfaces
- `llm_do/runtime/deps.py` - Dependency resolution
- `llm_do/runtime/registry.py` - Toolset/agent registry
- `llm_do/runtime/manifest.py` - Manifest handling
- `llm_do/runtime/shared.py` - Shared runtime state
- `llm_do/runtime/args.py` - Argument parsing utilities
- `llm_do/runtime/schema_refs.py` - Schema reference handling
- `llm_do/runtime/approval.py` - Approval wrapping
- `llm_do/runtime/discovery.py` - Module discovery
- `llm_do/runtime/worker_file.py` - Agent file handling
- `llm_do/runtime/events.py` - Runtime event types
- `llm_do/runtime/event_parser.py` - Event stream parsing
- `llm_do/runtime/toolsets.py` - Runtime toolset handling

## Checklist

- [ ] Message history propagation is correct (top-level vs nested)
- [ ] Approval wrapping is consistent at boundaries
- [ ] Discovery avoids duplicate module loading
- [ ] Per-agent config doesn't mutate shared instances unexpectedly
- [ ] No duplicated registries or canonical source confusion
- [ ] Cyclic agent references handled appropriately
- [ ] Error messages are helpful

## Output

Record findings in `docs/notes/reviews/review-ctx-runtime.md`.

## Last Run

2026-01 (schema_in_ref re-execs modules, max-depth error context, runtime.call tool-name conflicts, python builtins use CWD for filesystem_project)
