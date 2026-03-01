# Simplify: modules (batched)

Periodic simplification review of core modules using subagents. Each module is reviewed independently, then summarized.

## Scope

### CLI
- `llm_do/cli/main.py` -> `project_claw/code-reviews/simplify-cli-main.md` - CLI entrypoint

### Core models
- `llm_do/models.py` -> `project_claw/code-reviews/simplify-models.md` - shared models

### Runtime (core)
- `llm_do/runtime/agent_runner.py` -> `project_claw/code-reviews/simplify-runtime-agent-runner.md` - agent execution flow
- `llm_do/runtime/approval.py` -> `project_claw/code-reviews/simplify-runtime-approval.md` - approval workflow
- `llm_do/runtime/args.py` -> `project_claw/code-reviews/simplify-runtime-args.md` - runtime args
- `llm_do/runtime/call.py` -> `project_claw/code-reviews/simplify-runtime-call.md` - call orchestration
- `llm_do/runtime/context.py` -> `project_claw/code-reviews/simplify-runtime-context.md` - runtime context
- `llm_do/runtime/contracts.py` -> `project_claw/code-reviews/simplify-runtime-contracts.md` - runtime contracts
- `llm_do/runtime/events.py` -> `project_claw/code-reviews/simplify-runtime-events.md` - event stream/types
- `llm_do/runtime/runtime.py` -> `project_claw/code-reviews/simplify-runtime-runtime.md` - runtime entrypoint
- `llm_do/runtime/tooling.py` -> `project_claw/code-reviews/simplify-runtime-tooling.md` - runtime-owned tool type aliases

### Project (linker/manifest)
- `llm_do/project/agent_file.py` -> `project_claw/code-reviews/simplify-project-agent-file.md` - agent file handling
- `llm_do/project/discovery.py` -> `project_claw/code-reviews/simplify-project-discovery.md` - discovery logic
- `llm_do/project/entry_resolver.py` -> `project_claw/code-reviews/simplify-project-entry-resolver.md` - entry resolution
- `llm_do/project/host_toolsets.py` -> `project_claw/code-reviews/simplify-project-host-toolsets.md` - host toolset assembly
- `llm_do/project/input_model_refs.py` -> `project_claw/code-reviews/simplify-project-input-model-refs.md` - input model refs
- `llm_do/project/manifest.py` -> `project_claw/code-reviews/simplify-project-manifest.md` - manifest handling
- `llm_do/project/path_refs.py` -> `project_claw/code-reviews/simplify-project-path-refs.md` - path reference resolution
- `llm_do/project/registry.py` -> `project_claw/code-reviews/simplify-project-registry.md` - registry logic
- `llm_do/project/tool_resolution.py` -> `project_claw/code-reviews/simplify-project-tool-resolution.md` - tool resolution helpers

### Toolsets
- `llm_do/toolsets/agent.py` -> `project_claw/code-reviews/simplify-toolsets-agent.md` - agent toolset
- `llm_do/toolsets/approval.py` -> `project_claw/code-reviews/simplify-toolsets-approval.md` - approval toolsets
- `llm_do/toolsets/builtins.py` -> `project_claw/code-reviews/simplify-toolsets-builtins.md` - builtin toolsets
- `llm_do/toolsets/dynamic_agents.py` -> `project_claw/code-reviews/simplify-toolsets-dynamic-agents.md` - dynamic agent toolset
- `llm_do/toolsets/filesystem.py` -> `project_claw/code-reviews/simplify-toolsets-filesystem.md` - filesystem toolsets
- `llm_do/toolsets/loader.py` -> `project_claw/code-reviews/simplify-toolsets-loader.md` - toolset loader
- `llm_do/toolsets/validators.py` -> `project_claw/code-reviews/simplify-toolsets-validators.md` - toolset validators
- `llm_do/toolsets/shell/` -> `project_claw/code-reviews/simplify-toolsets-shell.md` - shell toolset package

### UI
- `llm_do/ui/app.py` -> `project_claw/code-reviews/simplify-ui-app.md` - UI app wrapper
- `llm_do/ui/adapter.py` -> `project_claw/code-reviews/simplify-ui-adapter.md` - UI adapter
- `llm_do/ui/display.py` -> `project_claw/code-reviews/simplify-ui-display.md` - UI display/layout
- `llm_do/ui/events.py` -> `project_claw/code-reviews/simplify-ui-events.md` - UI event handling
- `llm_do/ui/formatting.py` -> `project_claw/code-reviews/simplify-ui-formatting.md` - UI formatting
- `llm_do/ui/parser.py` -> `project_claw/code-reviews/simplify-ui-parser.md` - UI parsing helpers
- `llm_do/ui/runner.py` -> `project_claw/code-reviews/simplify-ui-runner.md` - UI runner
- `llm_do/ui/controllers/` -> `project_claw/code-reviews/simplify-ui-controllers.md` - UI controllers package
- `llm_do/ui/widgets/` -> `project_claw/code-reviews/simplify-ui-widgets.md` - UI widgets package

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
- [ ] Each subagent writes findings to the mapped `project_claw/code-reviews/simplify-*.md` file for that module
- [ ] Main agent writes a cross-module summary with prioritized candidates and themes

## Output

Record the summary in `project_claw/code-reviews/simplify-summary.md` (reviews directory).
