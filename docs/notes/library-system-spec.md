# Library System Specification

**Status**: Draft
**Prerequisite**: Worker-function architecture (Phases 1-4) - Completed

## Overview

Libraries are reusable collections of workers, tools, and templates that can be shared across projects. This specification defines how libraries are structured, discovered, resolved, and used.

## Goals

1. **Reusability**: Share workers across projects without copy-paste
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
    ├── lib.yaml             # REQUIRED: Library manifest
    │
    ├── workers/             # Exported workers
    │   ├── worker_a.worker
    │   └── worker_b/
    │       ├── worker.worker
    │       └── tools.py
    │
    ├── tools/               # Shared tools (available to all workers)
    │   └── *.py
    │
    └── templates/           # Shared templates
        └── *.jinja
```

### 1.1 Minimal Library

```
my-lib/
├── lib.yaml
└── workers/
    └── helper.worker
```

### 1.2 Library with Shared Tools

```
utils/
├── lib.yaml
├── workers/
│   ├── summarizer.worker
│   └── translator.worker
└── tools/
    ├── __init__.py
    └── text_utils.py
```

---

## 2. Library Manifest (lib.yaml)

```yaml
# lib.yaml - REQUIRED

name: utils                    # REQUIRED: Library identifier
version: 2.1.0                 # Optional: Semantic version
description: Common utilities  # Optional: Human-readable description

# Workers exported by this library (empty = export all)
exports:
  - summarizer
  - translator

# Dependencies on other libraries
dependencies:
  - text-processing           # Latest version
  - formatting@1.0            # Specific version
```

### 2.1 Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Library identifier (used in `lib:worker` references) |
| `version` | No | Semantic version string |
| `description` | No | Human-readable description |
| `exports` | No | List of exported workers (empty = all) |
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

Declare library dependencies in `project.yaml`:

```yaml
# project.yaml
name: my-project
dependencies:
  - utils
  - legal@2.0
```

### 4.2 Referencing Library Workers

Use `lib:` prefix to reference workers from libraries:

```yaml
# In worker definition
toolsets:
  delegation:
    allow_workers:
      - lib:utils/summarizer      # From utils library
      - lib:legal@2.0/reviewer    # From specific version
      - local_worker              # From project's workers/
```

In delegation calls:
```python
worker_call(worker="lib:utils/summarizer", input_data={...})
```

### 4.3 Library Templates

Include templates from libraries:

```jinja2
{% include 'lib:utils/report_header.jinja' %}
```

### 4.4 Library Tools

Library tools are automatically available when the library is a dependency.

Search order (worker-local wins):
1. Worker directory `tools.py`
2. Project root `tools.py`
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
# utils          2.1.0   Common utility workers
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
# Description: Common utility workers
#
# Exported workers:
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

```yaml
# utils/lib.yaml
dependencies:
  - text-processing

# text-processing/lib.yaml
dependencies:
  - formatting
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
C depends on A  ← Error: Circular dependency detected
```

---

## 7. Export Control

### 7.1 Default: Export All

If `exports` is empty or omitted, all workers in `workers/` are exported:

```yaml
# lib.yaml
name: utils
# exports: not specified = all workers exported
```

### 7.2 Explicit Exports

List specific workers to export (others are internal):

```yaml
# lib.yaml
name: utils
exports:
  - summarizer
  - translator
  # helper worker exists but is NOT exported
```

Attempting to use unexported worker:
```
Error: Worker 'helper' is not exported by library 'utils'
```

---

## 8. Implementation Plan

Work tracking lives in `docs/tasks/backlog/library-system.md`.

### Phases (high level)
1. Core types (LibraryConfig model, resolution helpers, exceptions)
2. Registry integration (lib: resolution, templates, tools)
3. CLI commands (install, list, info, remove)
4. Testing and polish (tests, example library, docs)

---

## 9. Open Questions

1. **Tool aggregation**: Should library tools be aggregated or should only the first match win?
   - Current thinking: Aggregate (all library tools available), name conflicts use priority

2. **Config inheritance**: Should libraries be able to specify default model?
   - Current thinking: No, keep libraries simple (just workers/tools/templates)

3. **Private dependencies**: Can a library have dependencies that aren't exposed to users?
   - Current thinking: All dependencies are transitive (simpler model)
