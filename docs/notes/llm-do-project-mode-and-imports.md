# llm-do Project Mode, Worker Imports, and Tool Linking
**Specification**

## Status

**Proposed / Design-ready**

This document specifies how `.worker` files, Python tool modules, and projects
should be discovered, linked, and executed in `llm-do`, removing the need to
enumerate every file on the CLI while preserving determinism, security, and
auditability.

---

## 1. Motivation

### Current behavior
- `llm-do` builds the execution registry from files explicitly passed on the CLI.
- `.worker` files cannot reference other workers or tools directly.
- Python tools rely on manual CLI inclusion rather than structured discovery.

### Problems
- Poor ergonomics for non-trivial projects
- No dependency closure for `.worker` files
- No clear equivalent of Python’s `import` for workers
- High risk of documentation vs. implementation drift

### Goals
1. Run a project by pointing at a directory
2. Allow `.worker` files to declare dependencies explicitly
3. Keep execution deterministic and auditable
4. Preserve existing security guarantees (allowlists, tool approvals)

---

## 2. Design Overview

This spec introduces **two complementary mechanisms**:

### A. Project Mode (Directory-backed registry)
- A directory represents a runnable project.
- Workers and tools are discovered by convention.
- CLI defaults to project mode when given a directory.

### B. Worker Imports (Explicit dependency closure)
- `.worker` files may declare `imports` in front matter.
- Running a single worker loads its dependency closure without scanning the world.

Both mechanisms coexist:
- **Project mode** = convenience
- **Imports** = portability and hermetic execution

---

## 3. Terminology

| Term | Meaning |
|-----|--------|
| Project Root | Directory defining a runnable workspace |
| Workers Root | Directory containing worker definitions (default: `workers/`) |
| Prompts Root | Directory containing prompt templates (default: `prompts/`) |
| Tool Module | Python file or module registering tools |
| Worker ID | Canonical identifier for a worker |

---

## 4. Project Layout Conventions

### Default layout

```
project/
  workers/
    orchestrator.worker
    evaluator.worker
    reports/
      summarizer.worker
  prompts/
    orchestrator.jinja2
    evaluator.jinja2
    PROCEDURE.md
  toolsets/
    formatting.py
    parsing.py
  tools.py
  llm-do.yaml
  .llm-doignore
```

### Compatibility
- Existing `workers/*.yaml` definitions remain valid
- Existing `prompts/{name}.{jinja2,j2,txt,md}` conventions remain valid

---

## 5. Worker File Formats

### 5.1 `.worker` format (single file)

A `.worker` file consists of YAML front matter followed by instruction text.

```yaml
---
name: pitch_evaluator
model: anthropic:claude-sonnet-4
schema_in_ref: schemas.py:PitchInput
imports:
  workers:
    - reports/summarizer
  tools:
    - toolsets/formatting.py
tool_rules:
  worker.call:
    allowed: true
    approval_required: false
---
You are a pitch deck evaluation specialist.
{{ file("PROCEDURE.md") }}
```

Rules:
- YAML front matter is between the first two `---` lines
- Everything after is `instructions`
- If Jinja syntax is detected, render using the prompts root
- `schema_in_ref` (optional) points to a Pydantic `BaseModel` input schema
  - Supported forms: `module.Class` or `path.py:Class` (relative to the worker file)

---

### 5.2 YAML-only worker (existing)

Existing `.yaml` / `.yml` worker definitions remain supported.

If `instructions` is missing:
- Load from `prompts/{worker_name}.{jinja2,j2,txt,md}`

---

## 6. Worker Imports

### 6.1 Schema

```yaml
imports:
  workers:
    - reports/summarizer
    - ./workers/other.worker
  tools:
    - toolsets/formatting.py
```

Both keys are optional.

---

### 6.2 Semantics

- Imports control **availability**, not permissions
- Allowlists (`allow_workers`) are still enforced at call time
- Tool approval rules are still enforced at execution time

---

### 6.3 Resolution

When loading a worker:

1. Parse worker definition
2. Resolve `imports.workers`
3. Resolve `imports.tools`
4. Recursively load dependencies
5. Detect and ignore already-loaded files

Cycles are allowed if they do not redefine the same worker ID.

---

## 7. Worker Identity and Resolution

### 7.1 Canonical Worker ID

Worker ID is derived from path under `workers/`:

| File | Worker ID |
|-----|----------|
| `workers/evaluator.worker` | `evaluator` |
| `workers/reports/summarizer.worker` | `reports/summarizer` |

---

### 7.2 WorkerRef Forms

A worker reference may be:

1. Canonical ID  
   ```yaml
   - reports/summarizer
   ```

2. Relative path  
   ```yaml
   - ./workers/reports/summarizer.worker
   ```

3. Bare name  
   ```yaml
   - evaluator
   ```

---

### 7.3 Resolution Rules

1. If ref has an extension:
   - Resolve relative to project root
2. Else:
   - Look for `{workers_root}/{id}.worker`
   - Then `{workers_root}/{id}.yaml`
3. Error if none found
4. Error on ambiguity

---

### 7.4 `name:` consistency

- `name:` MUST match the canonical worker ID
- Mismatch is an error

---

## 8. Tool Module Imports

### 8.1 ToolRef Forms

```yaml
imports:
  tools:
    - toolsets/formatting.py
    - tools.py
    - my_project.tools:register
```

---

### 8.2 Tool Module Contract

A tool module MUST expose:

```python
def register(agent) -> None:
    ...
```

---

### 8.3 Registration Timing

- Tools are registered per worker agent
- Registration happens after built-in tools
- Tools are wrapped with approval gating

---

### 8.4 Tool Rule Enforcement

**All tools**, including custom ones, MUST be executed via
`ApprovalController.maybe_run(...)`.

---

## 9. Project Manifest (Optional)

File: `llm-do.yaml`

```yaml
version: 1
entry: pitch_orchestrator

workers:
  root: workers
  include: ["**/*.worker", "**/*.yaml"]
  exclude: ["**/drafts/**"]

prompts:
  root: prompts

tools:
  roots: ["toolsets"]
  modules: ["tools.py"]
  allow_module_imports: false
```

---

## 10. Directory Scanning

Scanning is used for:
- `--list-workers`
- Validation
- Diagnostics

Execution MUST NOT depend on scanning if IDs resolve deterministically.

Ignored by default:
- `.git/`
- `.venv/`
- `__pycache__/`
- `node_modules/`

---

## 11. CLI Changes

### Project invocation

```bash
llm-do . --entry pitch_orchestrator "Evaluate all decks"
```

---

### Worker file invocation

```bash
llm-do workers/pitch_orchestrator.worker "Evaluate decks"
```

---

### New flags

| Flag | Purpose |
|----|--------|
| `--project DIR` | Explicit project root |
| `--entry ID` | Entry worker |
| `--list-workers` | Show discovered workers |
| `--check` | Validate project |
| `--no-import-tools` | Disable tool imports |
| `--allow-module-imports` | Allow Python module imports |

---

## 12. Validation Errors

Mandatory errors:
- Worker not found
- Ambiguous worker ID
- Name/ID mismatch
- Tool module missing `register`
- Disallowed tool import
- Path escapes project root

---

## 13. Security Model

### Non-escalation principle

- Importing ≠ permission
- Loading a worker ≠ allowed to call it
- Loading a tool ≠ allowed to execute it

---

### Path safety

- All resolved paths must remain within project root
- Prompt file access remains confined to prompts root

---

### Tool import policy

Defaults:
- Allow project-relative tool files
- Disallow arbitrary Python module imports unless explicitly enabled

---

## 14. Implementation Notes

Minimal changes required:

1. Extend worker loader to support `.worker`
2. Add `imports` resolution layer
3. Add canonical worker ID derivation
4. Generalize tool registration + approval gating
5. Extend CLI to accept directory as project

---

## 15. Result

After implementation, users can:

```bash
llm-do . --entry orchestrator
```

or:

```bash
llm-do workers/orchestrator.worker
```

without enumerating files, while retaining:

- deterministic execution
- explicit security boundaries
- auditable artifacts
- progressive stabilizing workflow

---

## End of Spec
