# Worker-as-Function Architecture

**Status**: Approved
**Created**: 2025-12-04
**Updated**: 2025-12-04

## Overview

This specification describes a refactoring of llm-do around the analogy: **workers are functions, not programs**. Just as complex programs are composed of many focused functions, complex LLM workflows should compose many focused workers.

### Motivation

1. **Context limitation is critical** — LLMs perform dramatically better with focused, limited context. A worker trying to do too much is like a 500-line function.

2. **Composition over monolithic prompts** — Complex tasks should decompose into focused sub-workers, each with single responsibility.

3. **Clear project boundaries** — Currently, worker resolution is flat and registry-based. Projects need explicit boundaries with local workers, templates, and tools.

4. **Familiar mental model** — Developers understand programs with entry points, functions, and libraries. This maps naturally to LLM workflows.

### Core Analogy

| Programming Concept | llm-do Equivalent |
|---------------------|-------------------|
| Program | Project directory |
| `main()` function | `main.worker` |
| Function | Individual `.worker` file |
| Function call | `worker_call` tool |
| Module/package | Subdirectory with workers |
| Import statement | Library dependency |
| Arguments | Input payload |
| Return value | Structured output |
| Standard library | Built-in workers |

---

## Specification

### 1. Project Structure

#### 1.1 Canonical Layout

```
project_name/
│
├── main.worker              # REQUIRED: Entry point
│
├── project.yaml             # OPTIONAL: Project manifest
│
├── workers/                 # OPTIONAL: Additional workers
│   ├── simple.worker        #   Single-file worker
│   └── complex/             #   Directory-form worker
│       ├── worker.worker    #     Worker definition
│       ├── tools.py         #     Worker-specific tools
│       └── templates/       #     Worker-specific templates
│
├── tools/                   # OPTIONAL: Project-wide tools
│   ├── __init__.py
│   └── *.py
│
├── tools.py                 # OPTIONAL: Simple project tools
│                            #   (alternative to tools/ directory)
│
├── templates/               # OPTIONAL: Project-wide templates
│   └── *.jinja
│
├── schemas/                 # OPTIONAL: Output schemas (JSON Schema)
│   └── *.json
│
├── input/                   # CONVENTION: Input files
├── output/                  # CONVENTION: Output files
└── scratch/                 # CONVENTION: Working directory
```

#### 1.2 Progressive Complexity

Projects grow organically. Simple cases require minimal structure:

**Level 0: Single File (no project)**
```
task.worker
```
Direct file execution: `llm-do task.worker "input"`

**Level 1: Minimal Project**
```
my_project/
└── main.worker
```
Entry point is automatic: `llm-do my_project/ "input"`

**Level 2: With Custom Tools**
```
my_project/
├── main.worker
└── tools.py
```

**Level 3: Multiple Workers**
```
my_project/
├── main.worker
└── workers/
    ├── helper_a.worker
    └── helper_b.worker
```

**Level 4: With Templates**
```
my_project/
├── main.worker
├── templates/
│   └── shared.jinja
└── workers/
```

**Level 5: Complex Workers with Own Tools**
```
my_project/
├── main.worker
├── tools/
└── workers/
    └── specialist/
        ├── worker.worker
        └── tools.py
```

**Level 6: With Library Dependencies**
```
my_project/
├── main.worker
├── project.yaml          # Declares dependencies
└── workers/
```

#### 1.3 Naming Conventions

| Item | Convention | Example |
|------|------------|---------|
| Project directory | `kebab-case` | `my-project/` |
| Worker files | `snake_case.worker` | `data_processor.worker` |
| Worker directories | `snake_case/` | `complex_worker/` |
| Entry point | `main.worker` | — |
| Directory worker def | `worker.worker` | — |
| Tools file | `tools.py` | — |
| Tools package | `tools/` with `__init__.py` | — |
| Templates | `snake_case.jinja` | `base_template.jinja` |
| Library reference | `lib:worker` | `utils:summarizer` |
| Relative reference | `./path/worker` | `./workers/helper` |

---

### 2. Project Manifest (project.yaml)

Optional manifest for project-level configuration.

```yaml
# project.yaml

# Metadata
name: my-project
version: 1.0.0
description: A sample project

# Default model for all workers (overridable per-worker)
model: anthropic:claude-haiku-4-5

# Library dependencies
dependencies:
  - utils                      # Latest from ~/.llm-do/libs/
  - legal@2.0                  # Specific version
  - acme-internal              # Organization library

# Global sandbox configuration (inherited by all workers)
sandbox:
  paths:
    input:
      root: ./input
      mode: ro
    output:
      root: ./output
      mode: rw
  network_enabled: false

# Default toolsets for all workers (merged with worker-specific)
toolsets:
  filesystem: {}

# Exported workers (if this project is also a library)
exports:
  - main
  - workers/data_processor
  - workers/formatter
```

#### 2.1 Manifest Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Project identifier (used when published as library) |
| `version` | string | Semantic version |
| `description` | string | Human-readable description |
| `model` | string | Default model for all workers |
| `dependencies` | list[string] | Library dependencies |
| `sandbox` | SandboxConfig | Global sandbox configuration |
| `toolsets` | dict | Default toolsets for all workers |
| `exports` | list[string] | Workers exposed when used as library |

#### 2.2 Configuration Inheritance

Workers inherit from project manifest:

```
project.yaml (defaults)
    ↓ merge
worker.worker (overrides)
    ↓ result
effective configuration
```

**Merge rules:**
- Scalar values: worker overrides project
- `toolsets`: deep merge (worker toolsets add to project toolsets)
- `sandbox.paths`: deep merge (worker paths add to project paths)
- Lists: worker replaces project (no merge)

---

### 3. Worker Resolution

#### 3.1 Resolution Contexts

Workers are resolved differently based on context:

**From CLI (top-level invocation):**
```bash
llm-do ./my-project "input"           # Project with main.worker
llm-do ./task.worker "input"          # Single file
llm-do my-worker "input"              # Search LLM_DO_PATH
```

**From worker_call (delegation):**
```python
worker_call("helper")                  # Project-local first
worker_call("./workers/deep/nested")   # Explicit relative path
worker_call("utils:summarizer")        # Library reference
```

#### 3.2 Resolution Order

For unprefixed worker names within a project:

1. **Project-local**: `{project}/workers/{name}.worker`
2. **Project-local (directory)**: `{project}/workers/{name}/worker.worker`
3. **Library workers**: For each dependency, `{lib}/workers/{name}.worker`
4. **Built-in workers**: `llm_do/workers/{name}.worker`

For prefixed names (`lib:worker`):
1. Resolve library from dependencies
2. Search `{lib}/workers/{worker}.worker`

For explicit paths (`./path/to/worker`):
1. Resolve relative to calling worker's project root
2. No fallback search

#### 3.3 Resolution Algorithm

```python
def resolve_worker(name: str, context: ResolutionContext) -> Path:
    """
    Resolve worker name to file path.

    Args:
        name: Worker name, relative path, or library reference
        context: Resolution context (project root, dependencies)

    Returns:
        Absolute path to worker file

    Raises:
        WorkerNotFoundError: If worker cannot be resolved
    """
    # Library reference: "lib:worker"
    if ":" in name:
        lib_name, worker_name = name.split(":", 1)
        lib_path = resolve_library(lib_name, context.dependencies)
        return resolve_in_library(worker_name, lib_path)

    # Explicit relative path: "./workers/helper"
    # Note: "../" is not supported (see Design Decisions)
    if name.startswith("./"):
        path = context.project_root / name
        return resolve_worker_path(path)

    if name.startswith("../"):
        raise InvalidPathError("Parent directory references not allowed")

    # Unprefixed name: search in order
    for search_path in context.search_paths:
        # Try single-file form
        candidate = search_path / f"{name}.worker"
        if candidate.exists():
            return candidate

        # Try directory form
        candidate = search_path / name / "worker.worker"
        if candidate.exists():
            return candidate

    raise WorkerNotFoundError(name, context.search_paths)
```

#### 3.4 Search Path Construction

```python
def build_search_paths(project_root: Path, dependencies: list[str]) -> list[Path]:
    """Build ordered search paths for worker resolution."""
    paths = []

    # 1. Project workers directory
    paths.append(project_root / "workers")

    # 2. Library workers (in dependency order)
    for dep in dependencies:
        lib_path = resolve_library(dep)
        paths.append(lib_path / "workers")

    # 3. Built-in workers
    paths.append(BUILTIN_WORKERS_PATH)

    return paths
```

---

### 4. Template Resolution

#### 4.1 Template Search Order

Templates use Jinja2's loader chain:

1. **Worker-local**: `{worker_dir}/templates/` (for directory-form workers)
2. **Project templates**: `{project}/templates/`
3. **Library templates**: `{lib}/templates/` for each dependency
4. **Built-in templates**: `llm_do/templates/`

#### 4.2 Template References

```jinja2
{# Local to worker #}
{% include 'header.jinja' %}

{# Explicit library reference #}
{% include 'legal:disclaimer.jinja' %}

{# Subdirectory #}
{% include 'partials/footer.jinja' %}
```

#### 4.3 Template Inheritance

Base templates define blocks; specialized templates extend:

```jinja2
{# templates/base_report.jinja #}
# {{ title }}

{% block summary %}{% endblock %}

## Analysis
{% block analysis %}{% endblock %}

## Conclusion
{% block conclusion %}{% endblock %}
```

```jinja2
{# templates/financial_report.jinja #}
{% extends 'base_report.jinja' %}

{% block summary %}
Financial summary for {{ period }}...
{% endblock %}
```

#### 4.4 Dynamic Template Selection

Templates can be selected at runtime using variables:

```jinja2
{# Worker instructions #}
{% include 'locales/' + locale + '.jinja' %}
{% include 'personas/' + persona_type + '.jinja' %}
```

---

### 5. Tool Resolution

#### 5.1 Tool Search Order

Tools are aggregated (not shadowed) from multiple sources:

1. **Worker-local**: `{worker_dir}/tools.py` or `{worker_dir}/tools/`
2. **Project tools**: `{project}/tools.py` or `{project}/tools/`
3. **Library tools**: `{lib}/tools/` for each dependency

All discovered tools are available to the worker. Name conflicts are resolved by priority (worker-local wins).

#### 5.2 Tool Discovery

```python
def discover_tools(worker_path: Path, project_root: Path,
                   dependencies: list[str]) -> dict[str, Callable]:
    """
    Discover all tools available to a worker.

    Returns dict mapping tool name to callable.
    Later sources override earlier (worker-local has highest priority).
    """
    tools = {}

    # 3. Library tools (lowest priority)
    for dep in reversed(dependencies):
        lib_path = resolve_library(dep)
        tools.update(load_tools_from(lib_path / "tools"))

    # 2. Project tools
    tools.update(load_tools_from(project_root / "tools.py"))
    tools.update(load_tools_from(project_root / "tools"))

    # 1. Worker-local tools (highest priority)
    worker_dir = worker_path.parent
    tools.update(load_tools_from(worker_dir / "tools.py"))
    tools.update(load_tools_from(worker_dir / "tools"))

    return tools
```

#### 5.3 Tool Packages

For complex tools organized as packages:

```
tools/
├── __init__.py          # Exports: from .module import tool_func
├── database.py          # def query_database(...): ...
├── analytics.py         # def calculate_metrics(...): ...
└── internal/            # NOT exported (no public functions)
    └── helpers.py
```

**Export convention**: Only functions decorated or listed in `__all__` are exposed as tools.

```python
# tools/__init__.py
from .database import query_database, list_tables
from .analytics import calculate_metrics

__all__ = ['query_database', 'list_tables', 'calculate_metrics']
```

---

### 6. Library System

#### 6.1 Library Structure

```
~/.llm-do/libs/
└── library_name/
    │
    ├── lib.yaml             # REQUIRED: Library manifest
    │
    ├── workers/             # Exported workers
    │   ├── worker_a.worker
    │   └── worker_b/
    │       ├── worker.worker
    │       └── tools.py
    │
    ├── tools/               # Shared tools
    │   └── *.py
    │
    └── templates/           # Shared templates
        └── *.jinja
```

#### 6.2 Library Manifest (lib.yaml)

```yaml
# lib.yaml

name: utils
version: 2.1.0
description: Common utility workers for text processing

# Workers exported by this library
exports:
  - summarizer
  - translator
  - json_fixer

# Dependencies on other libraries
dependencies:
  - text-processing@1.0
```

#### 6.3 Library Resolution

Libraries are resolved from:

1. `~/.llm-do/libs/{name}/` — User-installed libraries
2. `~/.llm-do/libs/{name}@{version}/` — Versioned libraries
3. Environment variable `LLM_DO_LIBS` — Additional library paths

```python
def resolve_library(spec: str) -> Path:
    """
    Resolve library specification to path.

    Specs: "name", "name@version", "git+https://..."
    """
    if "@" in spec:
        name, version = spec.rsplit("@", 1)
        path = LIB_ROOT / f"{name}@{version}"
    else:
        path = LIB_ROOT / spec

    if not path.exists():
        raise LibraryNotFoundError(spec)

    return path
```

#### 6.4 Library Installation

```bash
# Install from directory
llm-do lib install ./path/to/library

# Install from git (future)
llm-do lib install git+https://github.com/org/workers.git

# List installed libraries
llm-do lib list

# Remove library
llm-do lib remove utils
```

---

### 7. CLI Changes

#### 7.1 Primary Invocation

```bash
# Run project (finds main.worker automatically)
llm-do ./my-project "input message"
llm-do ./my-project --input '{"key": "value"}'

# Run with explicit entry point
llm-do ./my-project --entry workers/specific "input"

# Run single worker file directly (no project)
llm-do ./standalone.worker "input"

# Run worker from LLM_DO_PATH
llm-do my-worker "input"
```

#### 7.2 New Arguments

| Argument | Description |
|----------|-------------|
| `--entry WORKER` | Override entry point (default: `main`) |
| `--lib PATH` | Add library search path |
| `--no-project` | Treat argument as worker file, not project |

#### 7.3 Project Initialization

```bash
# Create minimal project
llm-do init my-project

# Create from template
llm-do init my-project --template pipeline
llm-do init my-project --template research-agent

# Available templates
llm-do init --list-templates
```

**Generated structure (minimal):**
```
my-project/
├── main.worker
├── input/
└── output/
```

**Generated structure (pipeline template):**
```
my-project/
├── main.worker           # Orchestrator
├── project.yaml
├── workers/
│   ├── stage_1.worker
│   ├── stage_2.worker
│   └── stage_3.worker
├── input/
└── output/
```

#### 7.4 Library Commands

```bash
llm-do lib install <path-or-url>    # Install library
llm-do lib list                      # List installed libraries
llm-do lib remove <name>             # Remove library
llm-do lib info <name>               # Show library details
```

---

### 8. Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_DO_PATH` | Colon-separated paths to search for workers | `~/.llm-do/workers` |
| `LLM_DO_LIBS` | Colon-separated paths to search for libraries | `~/.llm-do/libs` |
| `LLM_DO_MODEL` | Default model | (none) |
| `LLM_DO_PROJECT` | Default project directory | (none) |

---

### 9. Sandbox Behavior

#### 9.1 Path Resolution

All sandbox paths are relative to project root:

```yaml
# In project.yaml or worker.worker
sandbox:
  paths:
    input:
      root: ./input      # Resolves to {project}/input
      mode: ro
```

#### 9.2 Inheritance

Workers inherit project sandbox configuration:

```yaml
# project.yaml
sandbox:
  paths:
    input: {root: ./input, mode: ro}
    output: {root: ./output, mode: rw}

# workers/processor.worker
sandbox:
  paths:
    scratch: {root: ./scratch, mode: rw}  # Added
    # input and output inherited from project
```

#### 9.3 Isolation

Each worker execution gets its own sandbox instance. Workers cannot access paths outside their declared sandbox, even when calling other workers.

---

### 10. Delegation Behavior

#### 10.1 Context Propagation

When `worker_call` delegates to another worker:

```python
@dataclass
class DelegationContext:
    # Inherited from caller
    project_root: Path
    dependencies: list[str]
    approval_controller: ApprovalController

    # Fresh for callee
    sandbox: Sandbox  # Built from callee's config
    attachments: list[AttachmentPayload]  # Passed explicitly
```

#### 10.2 Attachment Handling

Attachments passed via `worker_call` are:
1. Validated against caller's attachment policy
2. Validated against callee's attachment policy
3. Made available in callee's sandbox (if file-based)

#### 10.3 Return Values

Delegated workers return structured output:

```python
result = worker_call("analyzer", {"data": "..."})
# result is the callee's output (string or structured)
```

---

### 11. Backward Compatibility

#### 11.1 Migration Path

**Phase 1**: Both models supported
- Existing flat registry continues to work
- New project-based model available
- CLI auto-detects based on argument

**Phase 2**: Deprecation warnings
- Flat registry usage emits deprecation warning
- Documentation emphasizes project model

**Phase 3**: Flat registry removed
- Only project model supported
- Migration tool provided

#### 11.2 Detection Logic

```python
def detect_invocation_mode(arg: str) -> InvocationMode:
    """Detect whether argument is project, worker file, or worker name."""
    path = Path(arg)

    if path.is_file() and path.suffix == ".worker":
        return InvocationMode.SINGLE_FILE

    if path.is_dir():
        if (path / "main.worker").exists():
            return InvocationMode.PROJECT
        if (path / "project.yaml").exists():
            return InvocationMode.PROJECT
        raise InvalidProjectError(f"No main.worker in {path}")

    # Assume worker name, search LLM_DO_PATH
    return InvocationMode.SEARCH_PATH
```

---

### 12. Implementation Phases

#### Phase 1: Foundation
- [ ] Add `project.yaml` parsing
- [ ] Implement project detection in CLI
- [ ] Add `main.worker` convention
- [ ] Update `WorkerRegistry` for project-scoped resolution

#### Phase 2: Resolution
- [ ] Implement template search paths
- [ ] Implement tool aggregation
- [ ] Add library reference syntax (`lib:worker`)
- [ ] Add explicit path syntax (`./workers/helper`)

#### Phase 3: Libraries
- [ ] Define `lib.yaml` schema
- [ ] Implement library resolution
- [ ] Add `llm-do lib` commands
- [ ] Support versioned libraries

#### Phase 4: CLI Enhancement
- [ ] Add `--entry` flag
- [ ] Add `llm-do init` command
- [ ] Add project templates
- [ ] Update help text and documentation

#### Phase 5: Polish
- [ ] Migration guide
- [ ] Update all examples to project structure
- [ ] Performance optimization (caching)
- [ ] Error message improvements

---

## Design Decisions

Resolved decisions that shaped this specification.

### 1. Project Manifest Optional

**Decision:** `project.yaml` is optional.

The entry point (`main.worker`) is sufficient to define a project boundary. Manifest only needed when you need:
- Library dependencies
- Default model/sandbox for all workers
- Exporting as a library

Simple projects remain simple.

### 2. Circular Dependencies Error at Load Time

**Decision:** Detect and error immediately when circular dependencies are found.

```
Error: Circular dependency detected: lib-a → lib-b → lib-a
```

Rationale:
- Simple, predictable behavior
- Forces clean architecture
- Cycles indicate poor design—if `lib-a` needs `lib-b` and vice versa, they should be one library or refactored

### 3. No Parent Directory Imports

**Decision:** Workers cannot use `../` to access parent directories.

Workers can only access:
- Their own directory (for directory-form workers)
- Project-level resources (`templates/`, `tools/`)
- Library resources (via `lib:` prefix)

Rationale:
- Forces clean architecture
- Shared resources belong at project level
- Cross-worker access should use `worker_call`, not file sharing
- Prevents brittle path dependencies

### 4. Version Conflicts Error

**Decision:** Error on version conflict between dependencies.

```
Error: Version conflict for lib-a
  - my-project requires lib-a@2.0
  - lib-b@1.0 requires lib-a@1.0
```

Rationale:
- LLM workers are not npm packages—deep dependency trees unlikely
- Conflicts should be rare; when they occur, human decision is appropriate
- Explicit resolution documents intent
- Can evolve to semver later if needed

### 5. Generated Workers in /tmp

**Decision:** Keep generated workers in `/tmp/llm-do/generated/`.

Generated workers are session-specific artifacts, not project resources.

### 6. Colon Syntax for Library References

**Decision:** Use colon separator for all library references.

```python
worker_call("utils:summarizer")           # Worker from library
```

```jinja2
{% include 'utils:disclaimer.jinja' %}    # Template from library
```

Rationale:
- Consistent syntax across workers and templates
- Mental model: `library:resource` works everywhere
- Clear visual distinction from local paths

---

## References

- Current architecture: `docs/architecture.md`
- Worker delegation: `docs/worker_delegation.md`
- Single-file workers: `docs/notes/single_file_workers.md`
- Example multi-worker project: `examples/pitchdeck_eval/`
