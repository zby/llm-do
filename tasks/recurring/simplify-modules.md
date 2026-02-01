# Simplify: modules (batched)

Periodic simplification review of core modules using subagents. Each module is reviewed independently, then summarized.

## Scope

### CLI
- `llm_do/cli/main.py` -> `docs/notes/reviews/simplify-cli-main.md` - CLI entrypoint

### Core models
- `llm_do/models.py` -> `docs/notes/reviews/simplify-models.md` - shared models

### Runtime
- `llm_do/runtime/agent_file.py` -> `docs/notes/reviews/simplify-runtime-agent-file.md` - agent file handling
- `llm_do/runtime/agent_runner.py` -> `docs/notes/reviews/simplify-runtime-agent-runner.md` - agent execution flow
- `llm_do/runtime/approval.py` -> `docs/notes/reviews/simplify-runtime-approval.md` - approval workflow
- `llm_do/runtime/args.py` -> `docs/notes/reviews/simplify-runtime-args.md` - runtime args
- `llm_do/runtime/call.py` -> `docs/notes/reviews/simplify-runtime-call.md` - call orchestration
- `llm_do/runtime/context.py` -> `docs/notes/reviews/simplify-runtime-context.md` - runtime context
- `llm_do/runtime/contracts.py` -> `docs/notes/reviews/simplify-runtime-contracts.md` - runtime contracts
- `llm_do/runtime/discovery.py` -> `docs/notes/reviews/simplify-runtime-discovery.md` - discovery logic
- `llm_do/runtime/entry_resolver.py` -> `docs/notes/reviews/simplify-runtime-entry-resolver.md` - entry resolution
- `llm_do/runtime/events.py` -> `docs/notes/reviews/simplify-runtime-events.md` - event stream/types
- `llm_do/runtime/input_model_refs.py` -> `docs/notes/reviews/simplify-runtime-input-model-refs.md` - input model refs
- `llm_do/runtime/manifest.py` -> `docs/notes/reviews/simplify-runtime-manifest.md` - manifest handling
- `llm_do/runtime/registry.py` -> `docs/notes/reviews/simplify-runtime-registry.md` - registry logic
- `llm_do/runtime/runtime.py` -> `docs/notes/reviews/simplify-runtime-runtime.md` - runtime entrypoint

### Toolsets
- `llm_do/toolsets/agent.py` -> `docs/notes/reviews/simplify-toolsets-agent.md` - agent toolset
- `llm_do/toolsets/approval.py` -> `docs/notes/reviews/simplify-toolsets-approval.md` - approval toolsets
- `llm_do/toolsets/builtins.py` -> `docs/notes/reviews/simplify-toolsets-builtins.md` - builtin toolsets
- `llm_do/toolsets/dynamic_agents.py` -> `docs/notes/reviews/simplify-toolsets-dynamic-agents.md` - dynamic agent toolset
- `llm_do/toolsets/filesystem.py` -> `docs/notes/reviews/simplify-toolsets-filesystem.md` - filesystem toolsets
- `llm_do/toolsets/loader.py` -> `docs/notes/reviews/simplify-toolsets-loader.md` - toolset loader
- `llm_do/toolsets/validators.py` -> `docs/notes/reviews/simplify-toolsets-validators.md` - toolset validators
- `llm_do/toolsets/shell/` -> `docs/notes/reviews/simplify-toolsets-shell.md` - shell toolset package

### UI
- `llm_do/ui/app.py` -> `docs/notes/reviews/simplify-ui-app.md` - UI app wrapper
- `llm_do/ui/adapter.py` -> `docs/notes/reviews/simplify-ui-adapter.md` - UI adapter
- `llm_do/ui/display.py` -> `docs/notes/reviews/simplify-ui-display.md` - UI display/layout
- `llm_do/ui/events.py` -> `docs/notes/reviews/simplify-ui-events.md` - UI event handling
- `llm_do/ui/formatting.py` -> `docs/notes/reviews/simplify-ui-formatting.md` - UI formatting
- `llm_do/ui/parser.py` -> `docs/notes/reviews/simplify-ui-parser.md` - UI parsing helpers
- `llm_do/ui/runner.py` -> `docs/notes/reviews/simplify-ui-runner.md` - UI runner
- `llm_do/ui/controllers/` -> `docs/notes/reviews/simplify-ui-controllers.md` - UI controllers package
- `llm_do/ui/widgets/` -> `docs/notes/reviews/simplify-ui-widgets.md` - UI widgets package

## Context Gathering

1. Read the target module in full
2. Identify imports from within the project (`llm_do.*` only, skip stdlib/third-party)
3. Read relevant parts of those internal dependencies for context

Focus analysis on the target module, but use imported code to spot simplifications—duplicate logic, underused abstractions, replaceable inline code. Proposed changes may span multiple files if warranted.

## Simplification Prompt

Analyze for:
1. **Redundant validation** - Checks already handled by dependencies
2. **Unused flexibility** - Options/config never actually used
3. **Redundant parameters** - Values accessible via other parameters
4. **Duplicated derived values** - Same computed value in multiple places
5. **Over-specified interfaces** - Multiple primitives when one object would do
6. **Reorder operations** - Move resolutions/lookups before guards when the resolved value will be needed anyway; simplifies both checks and subsequent logic

Prioritize: Remove code, reduce concept duplication, make bugs impossible.

## Checklist

- [ ] Spawn a subagent per module in Scope (batch if needed) and run the simplification prompt
- [ ] Each subagent writes findings to the mapped `docs/notes/reviews/simplify-*.md` file for that module
- [ ] Main agent writes a cross-module summary with prioritized candidates and themes

## Output

Record the summary in `docs/notes/reviews/simplify-summary.md` (reviews directory).
