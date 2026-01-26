# Dynamic Agents

## Status
ready for implementation

## Goal
Enable agents to create and invoke other agents at runtime, supporting bootstrapping and iterative refinement workflows.

## Context
- Relevant files: `llm_do/runtime/manifest.py`, `llm_do/runtime/worker_file.py`, `llm_do/runtime/registry.py`, `llm_do/runtime/context.py`, `llm_do/runtime/tools.py`
- Design note: `docs/notes/dynamic-workers-runtime-design.md`
- Previous implementation: `delegation` toolset (removed in commit 7667980)
- Example use case: `examples/pitchdeck_eval/` - orchestrator creating specialized evaluator agents

## Decision Record
- Decision: output directory configured via manifest field `generated_agents_dir`
- Rationale: manifest already handles path resolution; natural place for project config
- Decision: generated agents are NOT auto-discovered on subsequent runs
- Rationale: user should explicitly promote agents by copying to project and adding to `agent_files`; keeps human in the loop
- Decision: agents callable only within the session that created them
- Rationale: session-scoped registry avoids complexity of runtime registry mutation
- Decision: toolset name `dynamic_agents`
- Decision: adding tools during a session is acceptable (but removing tools is not)
- Rationale: expanding tool availability doesn't break interpretation of past messages; removing tools would
  invalidate previously logged tool calls

## Tasks
- [ ] Add `generated_workers_dir: str | None` field to `ProjectManifest`
- [ ] Create `dynamic_agents` toolset with:
  - [ ] `agent_create(name, instructions, description, model?)` - write `.agent` file
  - [ ] `agent_call(agent, input, attachments?)` - invoke created agent
- [ ] Session-scoped registry for created agents (in toolset instance)
- [ ] Parse created agents via existing `load_worker_file()` / `build_worker_definition()`
- [ ] Resolve toolsets via existing `resolve_toolset_specs()`
- [ ] Invoke via existing agent execution path
- [ ] Error if `generated_workers_dir` not configured when `agent_create` called
- [ ] Tests for create/call lifecycle
- [ ] Update/create bootstrapping example

## Implementation Notes

### Manifest Addition
```python
class ProjectManifest(BaseModel):
    # ... existing ...
    generated_workers_dir: str | None = None
```

### Toolset Structure
```python
class DynamicAgentsToolset(FunctionToolset):
    def __init__(self, generated_dir: Path, runtime: Runtime):
        self._generated_dir = generated_dir
        self._runtime = runtime
        self._created_agents: dict[str, AgentSpec] = {}  # session-scoped

    def agent_create(self, name: str, instructions: str, description: str, model: str | None = None) -> str:
        # Write .agent file to generated_dir
        # Parse and build AgentSpec
        # Register in _created_agents
        # Return name

    async def agent_call(self, agent: str, input: str, attachments: list[str] | None = None) -> str:
        # Look up in _created_agents (error if not found)
        # Call via runtime.call_agent() or equivalent
        # Return result
```

### Toolset Resolution for Created Agents
Created agents can only use toolsets already registered in the project. The `agent_create` tool should validate that any toolsets referenced in the agent spec exist.

### Tool Schema Injection
Calling a newly generated agent by name requires the orchestrator to have the tool schema for that agent injected into the message history. Adding tools mid-session is acceptable, but removing tools is not because it would impair the model's ability to interpret past tool calls. The dynamic agent flow should:
- Extend the tool registry in the runtime context after `agent_create`.
- Ensure subsequent turns include the updated tool schema when the orchestrator calls `agent_call`.

### Approval Considerations
- `agent_create` may need approval (creates code)
- Created agent's tool calls go through normal approval flow
- `agent_call` itself probably doesn't need approval (just invocation)

## Open Questions
- Should `agent_call` also work for static agents (convenience) or only dynamic ones (strict separation)?
- What toolsets can created agents access? All project toolsets, or a restricted set?

## Verification
- Create a bootstrapping example where orchestrator creates a specialized agent
- Agent should be written to `generated/` directory
- Agent should be callable within same session
- Agent should NOT be discovered on next run without manual promotion
