# Review: modules (batched)

Periodic review of core modules for bugs, inconsistencies, overengineering, and other issues. Each module is reviewed independently, then summarized.

## Scope

### CLI
- `llm_do/cli/main.py` -> `docs/notes/reviews/review-ctx-runtime.md` - CLI entrypoint
- `llm_do/cli/oauth.py` -> `docs/notes/reviews/review-config-auth.md` - OAuth CLI

### Core models + auth
- `llm_do/models.py` -> `docs/notes/reviews/review-config-auth.md` - model selection and compatibility
- `llm_do/oauth/` -> `docs/notes/reviews/review-config-auth.md` - OAuth flow + storage

### Runtime (core)
- `llm_do/runtime/agent_runner.py` -> `docs/notes/reviews/review-ctx-runtime.md` - agent execution flow
- `llm_do/runtime/approval.py` -> `docs/notes/reviews/review-ctx-runtime.md` - approval workflow
- `llm_do/runtime/args.py` -> `docs/notes/reviews/review-ctx-runtime.md` - runtime args
- `llm_do/runtime/call.py` -> `docs/notes/reviews/review-ctx-runtime.md` - call orchestration
- `llm_do/runtime/context.py` -> `docs/notes/reviews/review-ctx-runtime.md` - runtime context
- `llm_do/runtime/contracts.py` -> `docs/notes/reviews/review-ctx-runtime.md` - runtime contracts
- `llm_do/runtime/events.py` -> `docs/notes/reviews/review-ctx-runtime.md` - event stream/types
- `llm_do/runtime/runtime.py` -> `docs/notes/reviews/review-ctx-runtime.md` - runtime entrypoint
- `llm_do/runtime/tooling.py` -> `docs/notes/reviews/review-ctx-runtime.md` - runtime-owned tool type aliases

### Project (linker/manifest)
- `llm_do/project/agent_file.py` -> `docs/notes/reviews/review-project.md` - agent file handling
- `llm_do/project/discovery.py` -> `docs/notes/reviews/review-project.md` - discovery logic
- `llm_do/project/entry_resolver.py` -> `docs/notes/reviews/review-project.md` - entry resolution
- `llm_do/project/host_toolsets.py` -> `docs/notes/reviews/review-project.md` - host toolset assembly
- `llm_do/project/input_model_refs.py` -> `docs/notes/reviews/review-project.md` - input model refs
- `llm_do/project/manifest.py` -> `docs/notes/reviews/review-project.md` - manifest handling
- `llm_do/project/path_refs.py` -> `docs/notes/reviews/review-project.md` - path reference resolution
- `llm_do/project/registry.py` -> `docs/notes/reviews/review-project.md` - registry logic
- `llm_do/project/tool_resolution.py` -> `docs/notes/reviews/review-project.md` - tool resolution helpers

### Toolsets
- `llm_do/toolsets/agent.py` -> `docs/notes/reviews/review-toolsets.md` - agent toolset
- `llm_do/toolsets/approval.py` -> `docs/notes/reviews/review-toolsets.md` - approval toolsets
- `llm_do/toolsets/builtins.py` -> `docs/notes/reviews/review-toolsets.md` - builtin toolsets
- `llm_do/toolsets/dynamic_agents.py` -> `docs/notes/reviews/review-toolsets.md` - dynamic agent toolset
- `llm_do/toolsets/filesystem.py` -> `docs/notes/reviews/review-toolsets.md` - filesystem toolsets
- `llm_do/toolsets/loader.py` -> `docs/notes/reviews/review-toolsets.md` - toolset loader
- `llm_do/toolsets/validators.py` -> `docs/notes/reviews/review-toolsets.md` - toolset validators
- `llm_do/toolsets/shell/` -> `docs/notes/reviews/review-toolsets.md` - shell toolset package

### UI
- `llm_do/ui/app.py` -> `docs/notes/reviews/review-ui.md` - UI app wrapper
- `llm_do/ui/adapter.py` -> `docs/notes/reviews/review-ui.md` - UI adapter
- `llm_do/ui/display.py` -> `docs/notes/reviews/review-ui.md` - UI display/layout
- `llm_do/ui/events.py` -> `docs/notes/reviews/review-ui.md` - UI event handling
- `llm_do/ui/formatting.py` -> `docs/notes/reviews/review-ui.md` - UI formatting
- `llm_do/ui/parser.py` -> `docs/notes/reviews/review-ui.md` - UI parsing helpers
- `llm_do/ui/runner.py` -> `docs/notes/reviews/review-ui.md` - UI runner
- `llm_do/ui/widgets/` -> `docs/notes/reviews/review-ui.md` - UI widgets package

### UI controllers
- `llm_do/ui/controllers/` -> `docs/notes/reviews/review-ui-controllers.md` - UI controllers package

## Context Gathering

1. Read the target module or package in full
2. Identify imports from within the project (`llm_do.*` only, skip stdlib/third-party)
3. Read relevant parts of those internal dependencies for context

Focus analysis on the target module, but use imported code to spot inconsistencies, overengineering, and correctness gaps. Proposed changes may span multiple files if warranted.

## Review Prompt

Analyze for:
1. **Logic correctness** - edge cases, state ownership, and async ordering
2. **Inconsistent semantics** - mismatched behavior across callers or layers
3. **Overengineering** - abstractions not paying for themselves
4. **Unsafe defaults** - surprising behavior without clear opt-in
5. **Error handling** - silent failures, unclear messages, or missing guards

Prioritize: correctness, security boundaries, and clarity.

## Checklist

- [ ] Spawn a subagent per module in Scope (batch if needed) and run the review prompt
- [ ] Each subagent writes findings to the mapped `docs/notes/reviews/review-*.md` file for that module group
- [ ] Main agent writes a cross-module summary with prioritized candidates and themes

## Output

Record the summary in `docs/notes/reviews/review-modules-summary.md`.
