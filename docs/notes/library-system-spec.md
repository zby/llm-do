---
description: Specification for reusable agent and tool libraries that can be shared across projects
---

# Library System Specification

**Status**: Draft (updated 2026-02-19 to align with current architecture)

## Overview

Libraries are reusable collections of agents, tools, and toolsets that can be shared across projects. This specification defines how libraries are structured, discovered, resolved, and used.

## Goals

1. **Reusability**: Share agents across projects without copy-paste
2. **Versioning**: Support multiple versions of the same library
3. **Composability**: Libraries can depend on other libraries
4. **Discoverability**: Simple CLI for managing libraries

## Non-Goals (Future)

- Git-based installation (`git+https://...`)
- Package registry (like npm/pypi)
- Automatic dependency resolution from remote sources

---

## 1. Library Structure

```
~/.llm-do/libs/
└── library_name/
    │
    ├── lib.json              # REQUIRED: Library manifest
    │
    ├── agents/               # Exported agents (.agent files)
    │   ├── summarizer.agent
    │   └── reviewer/
    │       ├── reviewer.agent
    │       └── tools.py
    │
    └── tools/                # Shared tools and toolsets (available to all agents)
        └── *.py
```

### 1.1 Minimal Library

```
my-lib/
├── lib.json
└── agents/
    └── helper.agent
```

### 1.2 Library with Shared Tools

```
utils/
├── lib.json
├── agents/
│   ├── summarizer.agent
│   └── translator.agent
└── tools/
    ├── __init__.py
    └── text_utils.py
```

---

## 2. Library Manifest (lib.json)

```json
{
  "name": "utils",
  "version": "2.1.0",
  "description": "Common utility agents",
  "exports": ["summarizer", "translator"],
  "dependencies": [
    "text-processing",
    "formatting@1.0"
  ]
}
```

### 2.1 Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Library identifier (used in `lib:agent` references) |
| `version` | No | Semantic version string |
| `description` | No | Human-readable description |
| `exports` | No | List of exported agents (empty = all) |
| `dependencies` | No | List of library dependencies |

---

## 3. Library Resolution

### 3.1 Search Paths

Libraries are resolved from (in order):

1. `LLM_DO_LIBS` environment variable (colon-separated paths)
2. `~/.llm-do/libs/` (default location)

### 3.2 Version Resolution

```
# Unversioned: ~/.llm-do/libs/utils/
lib:utils/summarizer

# Versioned: ~/.llm-do/libs/utils@2.0/
lib:utils@2.0/summarizer
```

### 3.3 Resolution Algorithm

```python
def resolve_library(spec: str) -> Path:
    """
    Resolve library specification to path.

    Args:
        spec: "name" or "name@version"

    Returns:
        Path to library directory

    Raises:
        LibraryNotFoundError: If library not found
    """
    name, version = parse_spec(spec)  # Split on @

    for search_path in get_search_paths():
        # Try versioned path first
        if version:
            versioned = search_path / f"{name}@{version}"
            if versioned.exists():
                return versioned

        # Try unversioned
        unversioned = search_path / name
        if unversioned.exists():
            return unversioned

    raise LibraryNotFoundError(spec)
```

---

## 4. Using Libraries

### 4.1 Project Dependencies

Declare library dependencies in `project.json`:

```json
{
  "version": 1,
  "dependencies": ["utils", "legal@2.0"],
  "runtime": { ... },
  "entry": { ... }
}
```

### 4.2 Referencing Library Agents

Use `lib:` prefix to reference agents from libraries:

```yaml
# In .agent file toolsets section
toolsets:
  - lib:utils/summarizer      # Agent from utils library as toolset
  - lib:legal@2.0/reviewer    # From specific version
  - local_agent                # From project's own .agent files
```

In Python code:
```python
result = await runtime.call_agent("lib:utils/summarizer", {"input": "..."})
```

### 4.3 Library Tools

Library tools are automatically available when the library is a dependency.

Search order (agent-local wins):
1. Agent directory `tools.py`
2. Project Python files (from `python_files` in manifest)
3. Library `tools/` directories (in dependency order)

---

## 5. CLI Commands

### 5.1 Install Library

```bash
# Install from local directory
llm-do lib install ./path/to/library

# Install with specific name
llm-do lib install ./path/to/library --name custom-name

# Install specific version
llm-do lib install ./path/to/library --version 2.0.0
```

### 5.2 List Libraries

```bash
# List all installed libraries
llm-do lib list

# Output:
# utils          2.1.0   Common utility agents
# legal          1.0.0   Legal document processing
# formatting     -       Text formatting helpers
```

### 5.3 Show Library Info

```bash
# Show library details
llm-do lib info utils

# Output:
# Name: utils
# Version: 2.1.0
# Path: ~/.llm-do/libs/utils
# Description: Common utility agents
#
# Exported agents:
#   - summarizer
#   - translator
#
# Dependencies:
#   - text-processing
```

### 5.4 Remove Library

```bash
# Remove library
llm-do lib remove utils

# Remove specific version
llm-do lib remove utils@1.0
```

---

## 6. Dependency Resolution

### 6.1 Transitive Dependencies

Libraries can depend on other libraries. Dependencies are resolved transitively.

```json
// utils/lib.json
{ "dependencies": ["text-processing"] }

// text-processing/lib.json
{ "dependencies": ["formatting"] }
```

When using `utils`, both `text-processing` and `formatting` are available.

### 6.2 Version Conflicts

If two libraries require different versions of the same dependency:

```
my-project
├── depends on: utils (requires text-processing@2.0)
└── depends on: legal (requires text-processing@1.0)
```

**Resolution**: Error with clear message. User must resolve manually.

### 6.3 Circular Dependencies

Circular dependencies are detected and rejected:

```
A depends on B
B depends on C
C depends on A  <- Error: Circular dependency detected
```

---

## 7. Export Control

### 7.1 Default: Export All

If `exports` is empty or omitted, all agents in `agents/` are exported:

```json
{
  "name": "utils"
}
```

### 7.2 Explicit Exports

List specific agents to export (others are internal):

```json
{
  "name": "utils",
  "exports": ["summarizer", "translator"]
}
```

Attempting to use unexported agent:
```
Error: Agent 'helper' is not exported by library 'utils'
```

---

## 8. Integration Points

### 8.1 Registry Integration

Library agents are registered in `AgentRegistry` during project setup, namespaced by library:

- Library agent `summarizer` from `utils` registers as `lib:utils/summarizer`
- Project agents take precedence over library agents with the same name
- Library tools and toolsets are discoverable through the standard `discovery.py` module loading

### 8.2 Agent File Resolution

The existing `agent_file.py` parser handles `.agent` files from libraries identically to project agents. Library agents can reference:
- Tools from their own library's `tools/` directory
- Tools from dependent libraries
- Built-in toolsets (same as project agents)

### 8.3 Manifest Extension

The `ProjectManifest` schema gains an optional `dependencies` field:

```python
class ProjectManifest(BaseModel):
    # ... existing fields ...
    dependencies: list[str] = Field(default_factory=list)
```

---

## 9. Open Questions

1. **Tool aggregation**: Should library tools be aggregated or should only the first match win?
   - Current thinking: Aggregate (all library tools available), name conflicts use priority

2. **Config inheritance**: Should libraries be able to specify default model?
   - Current thinking: No, keep libraries simple (just agents/tools)

3. **Private dependencies**: Can a library have dependencies that aren't exposed to users?
   - Current thinking: All dependencies are transitive (simpler model)

4. **Toolset sharing**: Should library toolsets (Python classes implementing `AbstractToolset`) be first-class exports alongside agents and tools?
   - Current thinking: Yes, toolsets are a natural library export since they encapsulate reusable tool bundles
