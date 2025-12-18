# Remove Workshop Concept

## Goal

Remove the workshop abstraction entirely. Workers are invoked directly, tools are resolved via a load path.

## Background

Workshop was solving several problems awkwardly:
- Entry point (`main.worker`) - but you can just call any worker directly
- Config inheritance - but tool_path + per-worker config is cleaner
- Namespace - but that's just a directory

**Workers-as-tools is already implemented** (`AgentToolset` in `llm_do/agent_toolset.py`). This task focuses on:
1. Replacing the `toolsets:` config with a simpler `tools:` list
2. Adding tool_path resolution
3. Removing workshop machinery

## New Model

### Direct Worker Invocation

```bash
# Call any worker directly
llm-do code_reviewer "Review this PR"
llm-do ./workers/orchestrator "Do the thing"
llm-do ~/my-tools/summarizer "Summarize this"
```

### Workers Declare Their Tools

```yaml
# workers/code_reviewer.worker
---
name: code_reviewer
description: Reviews code for issues
tools:
  - read_file      # resolved via tool_path
  - shell          # built-in
  - summarizer     # another worker (becomes agent-tool via AgentToolset)
---
You are a code reviewer...
```

This replaces the current `toolsets:` config:
```yaml
# OLD - being removed
toolsets:
  shell: {}
  delegation:
    allow_workers: ["summarizer"]
```

### Tool Load Path

Like Python's `sys.path` or shell's `PATH`:

```bash
LLM_DO_TOOL_PATH=".:~/.llm-do/tools"
```

Resolution order for each tool name:
1. Entries in `LLM_DO_TOOL_PATH` (in order)
2. Built-ins (always available as fallback)

For each path entry, check:
1. `{path}/tools.py::{tool_name}` - Python function
2. `{path}/workers/{tool_name}.worker` - Worker file (simple form)
3. `{path}/workers/{tool_name}/worker.worker` - Worker directory form
4. `{path}/{tool_name}.worker` - Worker at path root

Default tool path: `".:~/.llm-do/tools"`

### Directory Structure

```
my-project/
├── workers/
│   ├── code_reviewer.worker
│   ├── summarizer.worker
│   └── orchestrator/
│       ├── worker.worker
│       └── tools.py          # local tools for this worker
└── tools.py                   # shared tools for this project
```

## What Gets Removed

| Component | Status |
|-----------|--------|
| `InvocationMode.WORKSHOP` | Remove |
| `InvocationMode.SINGLE_FILE` | Keep (direct file path) |
| `InvocationMode.SEARCH_PATH` | Rename to just "name resolution" |
| `WorkshopContext` | Remove |
| `WorkshopConfig` | Remove |
| `llm_do/workshop.py` | Remove |
| `workshop.yaml` detection | Remove |
| `main.worker` special handling | Remove |
| `WorkerRegistry.workshop_config` | Remove |
| `toolsets:` config in workers | Replace with `tools:` list |

## What Changes

### WorkerRegistry

- Remove `workshop_config` field
- Change `_get_search_paths()` to use `tool_path` instead of hardcoded paths
- Add `tool_path: list[Path]` field (from env var or constructor)
- Remove `_apply_workshop_config()` method

### CLI

- Remove workshop detection logic
- Simplify: argument is always a worker name or path
- Resolve via tool_path

### Tool Resolution (New)

New module or extend registry. Leverages existing `AgentToolset` for worker-as-tool wrapping:

```python
def resolve_tools(tool_names: list[str], tool_path: list[Path]) -> list[Tool]:
    """Resolve tool names to callable tools."""
    tools = []
    for name in tool_names:
        tool = resolve_single_tool(name, tool_path)
        tools.append(tool)
    return tools

def resolve_single_tool(name: str, tool_path: list[Path]) -> Tool:
    for path in tool_path:
        # Check tools.py
        if (tools_py := path / "tools.py").exists():
            if tool := load_from_tools_py(tools_py, name):
                return tool

        # Check workers - wrap via AgentToolset mechanism
        if (worker := find_worker(path, name)):
            return wrap_as_agent_tool(worker)

    # Check built-ins (shell, filesystem, etc.)
    if is_builtin(name):
        return load_builtin(name)

    raise UnknownToolError(f"Tool not found: {name}")
```

### Worker Definition

Replace `toolsets` with `tools`:

```python
class WorkerDefinition(BaseModel):
    # ... existing fields ...

    # REMOVE:
    # toolsets: Optional[Dict[str, Any]] = None

    # ADD:
    tools: Optional[List[str]] = Field(
        default=None,
        description="Tool names to load. Resolved via tool_path."
    )
```

## Tasks

### Phase 1: Add tool_path resolution

- [ ] Add `LLM_DO_TOOL_PATH` env var support
- [ ] Add `tool_path` field to `WorkerRegistry`
- [ ] Update `_get_search_paths()` to use tool_path
- [ ] Default tool_path: `[".", "~/.llm-do/tools"]`

### Phase 2: Worker declares tools

- [ ] Add `tools: List[str]` field to `WorkerDefinition`
- [ ] Implement tool resolution logic:
  - [ ] Load from `tools.py` (Python functions)
  - [ ] Load workers as tools (uses existing `AgentToolset` wrapping)
  - [ ] Load built-ins (shell, filesystem, etc.)
- [ ] Replace `toolsets:` config with `tools:` list in execution

### Phase 3: Remove workshop

- [ ] Remove `InvocationMode.WORKSHOP`
- [ ] Remove `WorkshopContext`, `WorkshopConfig` from types.py
- [ ] Remove `llm_do/workshop.py`
- [ ] Remove `workshop_config` from `WorkerRegistry`
- [ ] Remove `_apply_workshop_config()` method
- [ ] Update CLI to remove workshop detection
- [ ] Update tests

### Phase 4: Cleanup

- [ ] Remove `main.worker` special handling
- [ ] Remove `toolsets` field from `WorkerDefinition` (after migration)
- [ ] Update documentation
- [ ] Update examples

## Migration

Existing workers with `toolsets:` config:
```yaml
# OLD
toolsets:
  shell: {}
  delegation:
    allow_workers: ["helper"]
```

Becomes:
```yaml
# NEW
tools:
  - shell
  - helper   # worker resolved via tool_path
```

Existing workshops:
- `main.worker` becomes just another worker, called by name
- `workshop.yaml` settings are dropped (per-worker config only)
- Worker resolution via tool_path instead of workshop namespace

## Test Strategy

- Test tool_path resolution order
- Test tools.py loading
- Test worker-as-tool wrapping (integration with AgentToolset)
- Test built-in fallback
- Test unknown tool error
- Test env var parsing
- Update existing delegation tests to use new `tools:` syntax

## Completed Prerequisites

- **Workers-as-tools**: ✅ `AgentToolset` implemented in `llm_do/agent_toolset.py`
- **ToolContext Protocol**: ✅ in `llm_do/types.py`
- **Depth tracking**: ✅ in `llm_do/runtime.py`

## References

- AgentToolset (workers as tools): `llm_do/agent_toolset.py`
- Current workshop: `llm_do/workshop.py`
- Registry: `llm_do/registry.py`
- Types: `llm_do/types.py`
- Completed workers-as-tools: `docs/tasks/completed/workers-as-tools.md`
