# Worker-as-Function User Stories

**Purpose**: Test cases for the worker-function architecture design. Each story should be implementable and testable.

**Status**: Extracted from `worker-function-architecture.md`

---

## Part 1: Core Features (Implement Now)

### 1.1 Single File Execution

**Story**: Run a standalone worker file without any project structure.

```bash
# Create a single worker file
cat > task.worker << 'EOF'
---
name: task
---
You are a helpful assistant. Answer the user's question.
EOF

# Run it directly
llm-do task.worker "What is 2+2?"
llm-do ./path/to/task.worker "What is 2+2?"
```

---

### 1.2 Minimal Project

**Story**: Run a project directory with just `main.worker`.

```
my-project/
└── main.worker
```

```bash
llm-do ./my-project "Hello"
llm-do my-project/ "Hello"
```

The CLI auto-detects project mode when directory contains `main.worker`.

---

### 1.3 Project with Custom Tools

**Story**: Project with shared tools available to all workers.

```
my-project/
├── main.worker
└── tools.py          # Project-wide tools
```

```python
# tools.py
def get_current_time() -> str:
    """Return the current time."""
    from datetime import datetime
    return datetime.now().isoformat()
```

```yaml
# main.worker
---
name: main
toolsets:
  custom:
    tools: [get_current_time]
---
You have access to get_current_time. Use it when asked about time.
```

```bash
llm-do ./my-project "What time is it?"
```

---

### 1.4 Multiple Workers with Delegation

**Story**: Main worker delegates to helper workers.

```
my-project/
├── main.worker
└── workers/
    ├── analyzer.worker
    └── formatter.worker
```

```yaml
# main.worker
---
name: main
toolsets:
  worker_call: {}
---
You orchestrate analysis tasks.
1. Call the "analyzer" worker to analyze the input
2. Call the "formatter" worker to format the results
```

```yaml
# workers/analyzer.worker
---
name: analyzer
---
Analyze the provided text and extract key points.
```

```bash
llm-do ./my-project "Analyze this document..."
```

**Verification**: Main worker can call `worker_call("analyzer")` and `worker_call("formatter")`.

---

### 1.5 Project-Level Templates

**Story**: Workers share templates from project `templates/` directory.

```
my-project/
├── main.worker
├── templates/
│   └── system_prompt.jinja
└── workers/
    └── helper.worker
```

```jinja2
{# templates/system_prompt.jinja #}
You are a professional assistant for {{ company_name }}.
Always be polite and helpful.
```

```yaml
# main.worker
---
name: main
---
{% include 'system_prompt.jinja' %}

Help the user with their request.
```

```bash
llm-do ./my-project "Help me"
```

**Verification**: Template is found in project `templates/` directory.

---

### 1.6 Worker-Local Templates Override Project

**Story**: Directory-form worker has its own templates that override project templates.

```
my-project/
├── main.worker
├── templates/
│   └── header.jinja           # "Project Header"
└── workers/
    └── specialist/
        ├── worker.worker
        └── header.jinja       # "Specialist Header" (wins)
```

```yaml
# workers/specialist/worker.worker
---
name: specialist
---
{% include 'header.jinja' %}

Do specialized work.
```

**Verification**: When loading `specialist`, the worker-local `header.jinja` is used ("Specialist Header"), not the project one.

---

### 1.7 Worker-Local Tools

**Story**: Directory-form worker has its own tools.

```
my-project/
├── main.worker
├── tools.py                   # Project tools
└── workers/
    └── calculator/
        ├── worker.worker
        └── tools.py           # Calculator-specific tools
```

```python
# workers/calculator/tools.py
def calculate(expression: str) -> float:
    """Evaluate a math expression."""
    return eval(expression)  # simplified
```

```yaml
# workers/calculator/worker.worker
---
name: calculator
toolsets:
  custom:
    tools: [calculate]
---
You are a calculator. Use the calculate tool.
```

**Verification**: Calculator worker has access to its local `calculate` tool.

---

### 1.8 Explicit Path References

**Story**: Worker calls another worker using explicit relative path.

```
my-project/
├── main.worker
└── workers/
    └── deep/
        └── nested/
            └── helper.worker
```

```yaml
# main.worker
---
name: main
toolsets:
  worker_call: {}
---
Call the helper using explicit path: worker_call("./workers/deep/nested/helper")
```

**Verification**: `worker_call("./workers/deep/nested/helper")` resolves correctly.

---

### 1.9 Project Configuration Inheritance

**Story**: Workers inherit model and sandbox config from `project.yaml`.

```yaml
# project.yaml
name: my-project
model: anthropic:claude-haiku-4-5
sandbox:
  paths:
    input:
      root: ./input
      mode: ro
    output:
      root: ./output
      mode: rw
```

```yaml
# workers/processor.worker
---
name: processor
sandbox:
  paths:
    scratch:
      root: ./scratch
      mode: rw
    # input and output inherited from project
---
Process files from input/, write to output/, use scratch/ for temp files.
```

**Verification**:
- Processor gets model from project.yaml
- Processor has `input`, `output` (inherited) AND `scratch` (local)

---

### 1.10 Entry Point Override

**Story**: Run a project starting from a non-main worker.

```
my-project/
├── main.worker
└── workers/
    ├── stage1.worker
    └── stage2.worker
```

```bash
# Run from specific entry point
llm-do ./my-project --entry stage2 "input"
llm-do ./my-project --entry workers/stage2 "input"
```

**Verification**: Execution starts from `stage2.worker`, not `main.worker`.

---

### 1.11 Project Initialization

**Story**: Create a new project from scratch or template.

```bash
# Minimal project
llm-do init my-project
# Creates:
# my-project/
# ├── main.worker
# ├── input/
# └── output/

# From template
llm-do init my-project --template pipeline
# Creates:
# my-project/
# ├── main.worker
# ├── project.yaml
# ├── workers/
# │   ├── stage_1.worker
# │   ├── stage_2.worker
# │   └── stage_3.worker
# ├── input/
# └── output/

# List available templates
llm-do init --list-templates
```

---

### 1.12 Template Inheritance (Jinja2 extends)

**Story**: Templates can extend base templates.

```jinja2
{# templates/base_report.jinja #}
# {{ title }}

{% block summary %}{% endblock %}

## Analysis
{% block analysis %}{% endblock %}
```

```jinja2
{# templates/financial_report.jinja #}
{% extends 'base_report.jinja' %}

{% block summary %}
Financial summary for {{ period }}...
{% endblock %}

{% block analysis %}
Detailed financial analysis...
{% endblock %}
```

```yaml
# workers/reporter.worker
---
name: reporter
---
{% include 'financial_report.jinja' %}
```

**Verification**: Template inheritance works correctly.

---

### 1.13 Dynamic Template Selection

**Story**: Select template at runtime based on variables.

```yaml
# main.worker (front matter provides variables)
---
name: main
locale: en
persona: formal
---
{% include 'locales/' + locale + '.jinja' %}
{% include 'personas/' + persona + '.jinja' %}

Help the user.
```

```
templates/
├── locales/
│   ├── en.jinja
│   └── es.jinja
└── personas/
    ├── formal.jinja
    └── casual.jinja
```

**Verification**: Templates are dynamically selected based on front matter values.

---

### 1.14 Parent Directory Rejection

**Story**: Attempting to use `../` in worker references fails with helpful error.

```bash
# This should fail
worker_call("../other/worker")
```

**Expected error**:
```
ValueError: Parent directory references ('..') are not allowed in worker names.
Use library references (lib:worker) for cross-project dependencies.
```

---

### 1.15 Toolsets Deep Merge

**Story**: Worker toolsets are merged with project toolsets.

```yaml
# project.yaml
toolsets:
  filesystem: {}
  shell:
    rules: ["no rm -rf"]
```

```yaml
# workers/processor.worker
---
name: processor
toolsets:
  custom:
    tools: [my_tool]
  # filesystem and shell inherited from project
---
```

**Verification**: Processor has `filesystem`, `shell` (from project), AND `custom` (local).

---

## Part 2: Library System (Future)

These stories are deferred to Phase 5.

### 2.1 Library Dependencies

**Story**: Project depends on external worker libraries.

```yaml
# project.yaml
name: my-project
dependencies:
  - utils                    # Latest from ~/.llm-do/libs/
  - legal@2.0               # Specific version
```

```yaml
# main.worker
---
name: main
toolsets:
  worker_call: {}
---
Use worker_call("utils:summarizer") to summarize text.
Use worker_call("legal:disclaimer_generator") for legal text.
```

---

### 2.2 Library Template References

**Story**: Include templates from libraries.

```jinja2
{# In any worker #}
{% include 'legal:disclaimer.jinja' %}
{% include 'utils:common_header.jinja' %}
```

---

### 2.3 Library Installation

**Story**: Install and manage worker libraries.

```bash
# Install from directory
llm-do lib install ./path/to/my-library

# Install from git (future)
llm-do lib install git+https://github.com/org/workers.git

# List installed
llm-do lib list

# Show details
llm-do lib info utils

# Remove
llm-do lib remove utils
```

---

### 2.4 Creating a Library

**Story**: Package a project as a reusable library.

```
my-library/
├── lib.yaml              # Library manifest (required)
├── workers/
│   ├── summarizer.worker
│   └── translator.worker
├── tools/
│   └── text_utils.py
└── templates/
    └── base.jinja
```

```yaml
# lib.yaml
name: utils
version: 2.1.0
description: Common utility workers

exports:
  - summarizer
  - translator

dependencies:
  - text-processing@1.0
```

---

### 2.5 Versioned Libraries

**Story**: Depend on specific library versions.

```yaml
# project.yaml
dependencies:
  - utils@2.0              # Exactly version 2.0
  - legal@1.5              # Exactly version 1.5
```

Library storage:
```
~/.llm-do/libs/
├── utils/                 # Latest/unversioned
├── utils@2.0/            # Versioned
├── utils@1.0/            # Old version
└── legal@1.5/
```

---

### 2.6 Library Tool Aggregation

**Story**: Workers get tools from worker-local, project, AND library sources.

Tool priority (highest to lowest):
1. Worker-local `tools.py`
2. Project `tools.py` or `tools/`
3. Library `tools/` (in dependency order)

Name conflicts: higher priority wins.

---

### 2.7 Circular Dependency Detection

**Story**: Circular library dependencies fail at load time.

```yaml
# lib-a/lib.yaml
dependencies:
  - lib-b

# lib-b/lib.yaml
dependencies:
  - lib-a
```

**Expected error**:
```
Error: Circular dependency detected: lib-a → lib-b → lib-a
```

---

### 2.8 Version Conflict Detection

**Story**: Conflicting version requirements fail with helpful error.

```yaml
# project.yaml
dependencies:
  - lib-a@2.0
  - lib-b@1.0    # lib-b requires lib-a@1.0

# lib-b@1.0/lib.yaml
dependencies:
  - lib-a@1.0
```

**Expected error**:
```
Error: Version conflict for lib-a
  - my-project requires lib-a@2.0
  - lib-b@1.0 requires lib-a@1.0
```

---

## Test Coverage

### Part 1: Core Features

| # | Story | Tests |
|---|-------|-------|
| 1.1 | Single file execution | `test_project.py::TestDetectInvocationMode::test_single_worker_file`, `test_project.py::TestResolveProject::test_resolve_single_file` |
| 1.2 | Minimal project | `test_project.py::TestDetectInvocationMode::test_project_with_main_worker`, `test_project.py::TestResolveProject::test_resolve_project_directory`, `test_project.py::TestRegistryProjectConfigInheritance::test_main_worker_at_project_root` |
| 1.3 | Project with custom tools | `test_custom_tools.py::test_custom_tools_discovery`, `test_custom_tools.py::test_custom_tools_loaded_and_callable` |
| 1.4 | Multiple workers with delegation | `test_pydanticai_base.py::test_call_worker_respects_allowlist`, `test_pydanticai_base.py::test_call_worker_supports_wildcard_allowlist`, `test_worker_delegation.py::test_call_worker_forwards_attachments` |
| 1.5 | Project-level templates | `test_project.py::TestPhase2TemplateSearchPaths::test_project_templates_directory` |
| 1.6 | Worker-local templates override | `test_project.py::TestPhase2TemplateSearchPaths::test_worker_local_templates`, `test_project.py::TestPhase2TemplateSearchPaths::test_worker_templates_override_project` |
| 1.7 | Worker-local tools | `test_custom_tools.py::test_custom_tools_discovery` (directory-form workers) |
| 1.8 | Explicit path references | `test_project.py::TestPhase2ExplicitPathSyntax::test_explicit_path_simple_form`, `test_project.py::TestPhase2ExplicitPathSyntax::test_explicit_path_directory_form` |
| 1.9 | Configuration inheritance | `test_project.py::TestRegistryProjectConfigInheritance::test_registry_inherits_project_model`, `test_project.py::TestRegistryProjectConfigInheritance::test_worker_model_overrides_project`, `test_project.py::TestRegistryProjectConfigInheritance::test_registry_merges_sandbox_paths` |
| 1.10 | Entry point override | `test_project.py::TestResolveProject::test_resolve_project_with_entry_override` |
| 1.11 | Project initialization | `test_pydanticai_cli.py::test_cli_init_creates_project`, `test_pydanticai_cli.py::test_cli_init_minimal` |
| 1.12 | Template inheritance | *(not tested - relies on Jinja2 built-in)* |
| 1.13 | Dynamic template selection | *(not tested - relies on Jinja2 built-in)* |
| 1.14 | Parent directory rejection | `test_project.py::TestPhase2ExplicitPathSyntax::test_parent_directory_rejected` |
| 1.15 | Toolsets deep merge | `test_project.py::TestRegistryProjectConfigInheritance::test_registry_merges_toolsets`, `test_project.py::TestRegistryProjectConfigInheritance::test_worker_toolsets_override_project` |

### Part 2: Library System (Future)

| # | Story | Tests |
|---|-------|-------|
| 2.1 | Library dependencies | `test_project.py::TestPhase2ExplicitPathSyntax::test_library_reference_not_yet_supported` *(placeholder error)* |
| 2.2 | Library template references | *(not implemented)* |
| 2.3 | Library installation | *(not implemented)* |
| 2.4 | Creating a library | *(not implemented)* |
| 2.5 | Versioned libraries | *(not implemented)* |
| 2.6 | Library tool aggregation | *(not implemented)* |
| 2.7 | Circular dependency detection | *(not implemented)* |
| 2.8 | Version conflict detection | *(not implemented)* |
