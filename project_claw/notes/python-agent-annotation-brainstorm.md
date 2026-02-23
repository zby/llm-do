---
description: Brainstorm for Python-only worker definitions via decorators
---

# Python Worker Annotation Brainstorm

## Context
We want a "softening" path that lets Python code become a worker with minimal friction,
possibly enabling a python-only project layout (even a single file). This should also
enable a future "stabilizing" path where prompts and config live in code.

This is a brainstorming document with multiple design variants and tradeoffs.

## Designs (Multiple Options)

### A) Decorator + Docstring (Minimal)
- API: `@worker_prompt()` on a function.
- Instructions = function docstring.
- Inputs = function signature (pydantic schema inferred).
- Output = return type hint (optional).
- Pros: tiny API, one-file projects.
- Cons: long docstrings are ugly; no room for toolsets/model config.

### B) Decorator + Explicit Prompt String
- API: `@worker_prompt(prompt=\"\"\"...\"\"\")`.
- Docstring can stay short or be unused.
- Pros: avoids huge docstrings; still one-file.
- Cons: prompt still embedded in code; may feel noisy.

### C) Decorator + Prompt Constant
- API: `PROMPT = \"...\"; @worker_prompt(prompt=PROMPT)`.
- Pros: separates prompt from logic without new files.
- Cons: still in code, but readable.

### D) Decorator + External Prompt File
- API: `@worker_prompt(prompt_path=\"prompts/analyzer.md\")`.
- Pros: clean code, better diffing for prompts.
- Cons: not one-file; introduces file structure.

### E) Class-Based Worker
- API: `class Analyzer(Worker): prompt = \"...\"; async def run(self, ...)`.
- Pros: room for metadata (model/toolsets/output schema).
- Cons: more boilerplate, less "lightweight".

### F) Function as Worker + Sidecar Config
- API: `@worker_prompt()` plus config in a dict next to function.
- Example:
  ```
  @worker_prompt
  def analyze(...):
      \"\"\"...\"\"\"

  analyze.config = {\"model\": \"anthropic:claude-sonnet-4\", ...}
  ```
- Pros: one-file; config is explicit.
- Cons: ad-hoc attribute pattern; less discoverable.

### G) Python-Only Worker Registry Module
- API: `WORKERS = [analyze, summarize]`
- The registry imports a module and inspects worker annotations.
- Pros: simple discovery; flexible.
- Cons: still needs a stable schema for config + prompt.

### H) Auto-Generated .agent (Stabilizing Path)
- API: `@worker_prompt(..., export=True)` generates a `.agent` file.
- Pros: bridges python-only to standard format; clean diffs.
- Cons: file generation is another step; needs tooling.

## Prompt Composition Patterns

1) Pure docstring as prompt
2) docstring + wrapper template ("Please compute function X with args ...")
3) explicit prompt string (decorator arg or constant)
4) prompt file
5) structured prompt parts (system, instructions, examples)

Open question: Should the wrapper template be fixed, configurable, or disabled?

## Inputs / Outputs

- Use function signature to infer input schema (pydantic or simple json).
- Use return type hints for output schema (optional).
- For "softening", allow untyped returns (string/any).
- For "stabilizing", require typed output or schema decorators.

## Model / Toolset Configuration

Options:
- Decorator parameters: `@worker_prompt(model=..., toolsets=...)`
- Sidecar config dict (attached to function)
- Class-based attributes (if using class worker)
- Global defaults in module (`WORKER_DEFAULTS = {...}`)

## Discovery / Project Layout

### One-File Project
- Single `tools.py` with decorated workers.
- CLI resolves workers by importing the module and scanning for annotations.

### Python-Only Project (Multi-File)
- `workers.py` or a package `workers/` with annotated functions.
- Optional `__all__` or `WORKERS` list for explicit exports.

### Hybrid
- Keep `.agent` files supported for compatibility, but add python-only mode.
- Note: If we pursue "python-only" as the primary path, we could make `.agent` optional.

## Migration / Refactoring Flow

- Softening: convert a `.agent` prompt into a decorated python function.
- Stabilizing: convert a decorated function into a `.agent` file (or vice versa).
- A single CLI tool could convert between formats.

## Risks / Tradeoffs

- Docstring prompts are clunky for long instructions.
- Python-only discovery requires import side effects and dependency hygiene.
- Toolsets and approvals are more complex to configure without YAML.
- One-file projects may become crowded quickly.

## Open Questions
- Should this be a new project mode or a universal option?
- If one-file is the goal, how do we avoid huge docstrings?
- Do we require a wrapper template around the prompt?
- What is the minimal config surface (model/toolsets/output) for v1?
- How should python-only workers be discovered (scan module vs explicit list)?
- Do we want auto-export to `.agent` files, or keep everything in Python?
