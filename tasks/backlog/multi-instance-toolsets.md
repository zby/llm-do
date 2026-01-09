# Multi-Instance Toolsets

## Goal
Support multiple instances of the same toolset type with different configurations (e.g., two filesystem toolsets with different base paths).

## Current Behavior (Limitation)

**You cannot use two toolsets that provide tools with the same name.** For example, you cannot use both `filesystem_cwd` and `filesystem_project` in the same worker because they both provide `read_file`, `write_file`, and `list_files`.

The error comes from pydantic-ai's `CombinedToolset.get_tools()` at runtime:

```
UserError: FileSystemToolset defines a tool whose name conflicts with existing tool from FileSystemToolset: 'read_file'. ...
```

See: `.venv/.../pydantic_ai/toolsets/combined.py:70-74`

Note: llm-do also has partial duplicate detection in `registry.py:117-120` for Python toolsets, but this is redundant with pydantic-ai's check.

## Use Cases
- Two filesystem toolsets with different `base_path` configs (e.g., one for source, one for docs)
- Multiple shell toolsets with different rule sets
- Parallel browser toolsets with different profiles

## Potential Solutions

### 1. Automatic Prefixing on Conflict
Prefix tool names only when conflicts exist:
- If no conflict: `read_file` (unprefixed for simplicity)
- If conflict: `filesystem_cwd.read_file`, `filesystem_project.read_file`

Pros: Simpler tool names when no conflict
Cons: Tool names change depending on other toolsets in worker

### 2. Always Prefix When Named
If a toolset is declared with an explicit instance name, always prefix:
```yaml
toolsets:
  - src_fs: filesystem(base_path: ./src)  # Tools become src_fs.read_file, etc.
  - docs_fs: filesystem(base_path: ./docs)
```

Pros: Predictable, explicit
Cons: Requires new worker file syntax

### 3. Toolset-Level Name Configuration
Allow toolsets to specify a prefix in their config:
```python
FileSystemToolset(config={"base_path": "./src", "tool_prefix": "src_"})
```

Pros: No worker file syntax change
Cons: Awkward, prefix logic lives in config

## Tasks
- [ ] Decide on prefixing approach
- [ ] Implement tool name prefixing in pydantic-ai or llm-do layer
- [ ] Update worker file parser if new syntax needed
- [x] Remove redundant duplicate check from registry.py (rely on pydantic-ai)
- [ ] Add tests for multi-instance scenarios
- [ ] Document the feature

## Current State
Not started. The limitation exists and affects real use cases (can't use multiple filesystem toolsets).
