---
description: Simplifying Python embedding with a quick_run helper that collapses 15 lines of wiring to 1-3
---

# Execution Mode Scripting Simplification

**Status**: Not implemented. Pain points validated against current architecture (2026-02-19).

## Context

- `docs/notes/execution-modes-user-stories.md` outlines goals for TUI-first workflows with a headless escape hatch and predictable approvals/outputs.
- Direct Python embedding is documented in `docs/notes/programmatic-embedding.md` with two patterns: manifest-driven and direct Python.
- CLI currently requires a JSON manifest (`project.json`); the CLI main.py assembles ~100 lines of wiring to go from manifest to execution.

## Current Embedding Pain Points

### 1. Boilerplate (still the primary issue)

The manifest-driven embedding pattern requires ~15 lines for what should be a 2-3 line operation:

```python
# Current: 15 lines to run an agent from Python
from llm_do.project import build_registry, build_registry_host_wiring, resolve_entry, EntryConfig
from llm_do.runtime import Runtime, RunApprovalPolicy

registry = build_registry(
    ["analyzer.agent"], [],
    project_root=project_root,
    **build_registry_host_wiring(project_root),
)
entry = resolve_entry(EntryConfig(agent="analyzer"), registry, python_files=[], base_path=project_root)
runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="approve_all"), project_root=project_root)
runtime.register_agents(registry.agents)
result, ctx = await runtime.run_entry(entry, input_data={"input": "Analyze this"})
```

Compare to the desired surface:

```python
# Target: 1-3 lines
from llm_do import quick_run
result = await quick_run("analyzer.agent", "Analyze this", approve_all=True)
```

### 2. Output handling

Headless scripts must manually construct `HeadlessDisplayBackend` with the right verbosity level and stream target. The CLI does this automatically based on `--headless`/`-v` flags, but embedding scripts get no output by default.

### 3. Policy drift

Scripts construct `RunApprovalPolicy` and `Runtime` independently from CLI defaults. There's no shared "headless defaults" object — each embedding site reinvents the same choices (approve_all, no OAuth, project_root from cwd).

### 4. Path duplication (partially addressed)

`build_registry_host_wiring(project_root)` consolidates built-in toolset setup, but `project_root` is still passed separately to `build_registry`, `Runtime`, and `resolve_entry`.

## Proposed Simplifications

### 1. `quick_run` helper aligned with CLI headless defaults

A thin wrapper that accepts an agent file path (or directory), prompt, and optional overrides:

```python
async def quick_run(
    agent: str | Path,               # .agent file or project directory
    prompt: str | dict[str, Any],     # input data
    *,
    project_root: Path | None = None, # defaults to agent file's parent
    approval_mode: str = "approve_all",
    verbosity: int = 0,
    max_depth: int = 5,
    on_event: EventCallback | None = None,
) -> tuple[Any, CallContext]:
    """Run an agent with sensible headless defaults.

    Internally: build_registry → resolve_entry → Runtime → run_entry
    with the same wiring that `llm-do --headless` uses.
    """
```

This collapses the 5-step wiring into one call. Internally it uses `build_registry`, `build_registry_host_wiring`, `resolve_entry`, `Runtime`, and `run_entry` — the same code path as the CLI.

### 2. `Runtime.from_project()` class method

For scripts that need more control than `quick_run` but less boilerplate than manual wiring:

```python
runtime, entry = await Runtime.from_project(
    project_root=Path("."),
    agent_files=["analyzer.agent"],
    entry_agent="analyzer",
    approval_mode="approve_all",
)
result, ctx = await runtime.run_entry(entry, {"input": "Analyze this"})
```

This consolidates `build_registry` + `build_registry_host_wiring` + `resolve_entry` + `register_agents` into one step while still returning a `Runtime` that can be reused for multiple runs.

### 3. Approval presets

Named presets mapping to common configurations:

```python
# Instead of:
RunApprovalPolicy(mode="approve_all")

# Offer presets:
from llm_do.runtime import APPROVE_ALL, HEADLESS_DEFAULTS, INTERACTIVE_DEFAULTS

runtime = Runtime(run_approval_policy=APPROVE_ALL, ...)
```

These presets ensure scripts and CLI use the same default values. `HEADLESS_DEFAULTS` would match `llm-do --headless` behavior; `INTERACTIVE_DEFAULTS` would match TUI behavior.

### 4. Output integration for headless scripts

`quick_run` should accept a `verbosity` parameter that automatically sets up `HeadlessDisplayBackend` on stderr (matching CLI `--headless -v` behavior), so scripts get progress output without manual backend wiring.

## How This Supports the User Stories

- **Headless automation**: `quick_run` gives predictable approvals and structured output for CI/batch jobs in 1-3 lines.
- **Developer iteration**: Quick experimentation without opening TUI or writing a manifest.
- **Consistency**: Same code paths as CLI, same approval defaults, same output formatting.
- **Reusable runtime**: `Runtime.from_project()` supports batch workflows that run multiple entries against the same agent registry.

## Implementation Notes

- `quick_run` lives in `llm_do/__init__.py` as a top-level export
- Internally reuses `_make_entry_factory` pattern from `cli/main.py`
- No new abstractions — just a convenience wrapper over existing components
- `Runtime.from_project()` is a classmethod on the existing `Runtime` class

## Open Questions

- Should `quick_run` return just the result string, or `(result, CallContext)` like `run_entry`?
- Should `Runtime.from_project()` auto-discover `.agent` files in a directory, or require explicit file list?
- Should approval presets allow scoped grants (per tool/directory) to mirror future CLI ergonomics, or is global approve/prompt enough for now?
