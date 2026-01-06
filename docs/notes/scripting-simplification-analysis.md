# Scripting API Simplification Analysis

## Context

This note analyzes how to simplify supporting the needs described in `execution-modes-user-stories.md`, using `experiments/inv/v2_direct/run.py` as a concrete example. The goal is a coherent design that serves scripting, CI, and embedding use cases without over-engineering.

## Current State of run.py (~114 lines)

The script has these sections:

1. **Configuration constants** (8 lines) — MODEL, APPROVE_ALL, VERBOSITY, PROMPT
2. **Worker definitions** (28 lines) — `load_instructions()`, `build_workers()`
3. **Runtime** (20 lines) — HeadlessDisplayBackend, RunApprovalPolicy, run_invocable
4. **Main entry** (10 lines) — asyncio.run wrapper, print statements

**Already solved** (via `run_invocable()`):
- Recursive approval wrapping
- Context/runtime setup
- Message history management

**Still manual**:
- Instruction file loading
- HeadlessDisplayBackend instantiation
- Model passing in multiple places (Worker and run_invocable)
- Approval policy construction
- asyncio.run boilerplate

## Key User Stories to Support

From the user stories document, these are the essential scripting needs:

| Need | Priority | Current Support |
|------|----------|-----------------|
| Run worker from script/CI | High | Possible but verbose |
| Predictable approval (approve-all/reject-all) | High | `RunApprovalPolicy` works |
| JSON output | Medium | No dedicated support |
| Pipe input/capture output | Medium | Works with headless |
| CLI args for parameters | Medium | Not in Python API |
| Workers as Python functions | High | Worker class exists |
| Package as Python packages | High | Works today (just Python) |

## Proposal: Worker.run() with Sensible Defaults

The core insight: most scripting use cases want "run this worker headlessly." Make that the happy path.

### Minimal Script Target (15-20 lines)

```python
#!/usr/bin/env python
"""Run pitch deck evaluation."""
from pathlib import Path
from llm_do import Worker
from llm_do.toolsets.filesystem import FileSystemToolset

HERE = Path(__file__).parent

main = Worker(
    name="main",
    model="anthropic:claude-haiku-4-5",
    instructions=(HERE / "instructions/main.md").read_text(),
    toolsets=[FileSystemToolset(config={"base_path": str(HERE)})],
)

result = main.run("Go", approve_all=True, verbosity=1)
print(result)
```

### Worker.run() API

```python
class Worker:
    def run(
        self,
        prompt: str,
        *,
        approve_all: bool = False,
        verbosity: int = 0,
        output_format: Literal["text", "json"] | None = None,
    ) -> str:
        """Synchronous headless run with sensible defaults.

        This is the primary scripting API. For async or interactive
        use, use run_invocable() directly.
        """
        # Internally: asyncio.run, HeadlessDisplayBackend, RunApprovalPolicy
```

**Key design decisions**:
1. **Synchronous** — Most scripts are sync; don't force asyncio knowledge
2. **Headless by default** — No display backend required unless verbosity > 0
3. **Simple approval** — `approve_all=True/False`, not a policy object
4. **Returns result directly** — Not a tuple, not a context

### What NOT to Build

To keep the design coherent, I recommend **deferring** these:

| Feature | Reason to Defer |
|---------|-----------------|
| `quick_run(path)` with auto-discovery | Requires standardized project layout; solve Worker.run() first |
| `Runner` class | Adds abstraction layer; Worker.run() covers main use case |
| `config.yaml` loading | YAML adds complexity; Python is already declarative |
| `Worker.from_dir()` | Requires layout conventions; not essential for scripting |
| CLI integration with `llm-do pkg:entry` | Package entrypoints work with standard Python |

### Comparison: Before and After

**Before (current):**
```python
async def run_evaluation() -> str:
    main, _ = build_workers()
    backend = HeadlessDisplayBackend(stream=sys.stderr, verbosity=VERBOSITY)
    approval_policy = RunApprovalPolicy(
        mode="approve_all" if APPROVE_ALL else "prompt",
    )
    result, _ctx = await run_invocable(
        main,
        prompt=PROMPT,
        model=MODEL,
        approval_policy=approval_policy,
        on_event=backend.display if VERBOSITY > 0 else None,
        verbosity=VERBOSITY,
    )
    return result

def main():
    print(f"Running with MODEL={MODEL}, ...")
    result = asyncio.run(run_evaluation())
    print(result)
```

**After (proposed):**
```python
result = main.run("Go", approve_all=True, verbosity=1)
print(result)
```

## Implementation Plan

### Phase 1: Worker.run() (Low Risk)

Add synchronous `run()` method to Worker class:

```python
# llm_do/runtime/worker.py

def run(
    self,
    prompt: str,
    *,
    approve_all: bool = False,
    verbosity: int = 0,
) -> Any:
    """Synchronous headless run."""
    import asyncio
    import sys
    from .approval import RunApprovalPolicy
    from .runner import run_invocable
    from ..ui.display import HeadlessDisplayBackend

    backend = HeadlessDisplayBackend(
        stream=sys.stderr,
        verbosity=verbosity,
    ) if verbosity > 0 else None

    policy = RunApprovalPolicy(
        mode="approve_all" if approve_all else "reject_all"
    )

    async def _run():
        result, _ = await run_invocable(
            self,
            prompt=prompt,
            model=self.model,
            approval_policy=policy,
            on_event=backend.display if backend else None,
            verbosity=verbosity,
        )
        return result

    return asyncio.run(_run())
```

### Phase 2: Async Variant (Optional)

If users need async control:

```python
async def run_async(self, prompt: str, **kwargs) -> Any:
    """Async variant of run() for use in async contexts."""
```

### Phase 3: JSON Output (If Needed)

Add `output_format` parameter that either:
1. Uses Worker's `schema_out` for structured output, or
2. Wraps result in `{"result": ...}` for text output

## Addressing User Stories

| Story | Solution |
|-------|----------|
| "Run from script/CI" | `worker.run(prompt, approve_all=True)` |
| "Predictable approval" | `approve_all=True/False` parameter |
| "JSON output" | `output_format="json"` parameter (phase 3) |
| "Workers as functions" | Worker class already works this way |
| "Package as Python packages" | Just ship Python packages; no special format needed |
| "Pin dependencies" | Use standard requirements.txt/pyproject.toml |
| "Relative paths" | Works today with `base_path` parameter |

## What This Doesn't Cover

The user stories document includes features that are out of scope for scripting simplification:

1. **Chat mode** — Separate concern; TUI handles this
2. **/load command** — Interactive feature; not for scripts
3. **Worker discovery** — CLI concern; scripts specify workers directly
4. **Sub-worker delegation** — Works today; no changes needed
5. **Approval granularity** — `approve_all` is sufficient for scripting

## Relation to Existing Notes

- **worker-run-method-refactoring.md**: This analysis aligns with that proposal but suggests a simpler sync-first API
- **v2_direct_run_simplification.md**: Proposes `quick_run()` and `Runner`; I recommend deferring those in favor of simpler `Worker.run()`

## Recommendation

Implement `Worker.run()` as a single, focused improvement:

1. Synchronous by default (wraps asyncio.run internally)
2. Headless by default (no display unless verbosity > 0)
3. Simple approval parameter (bool, not policy object)
4. Returns result directly (not tuple)

This addresses 80% of scripting needs with minimal API surface. Defer `quick_run()`, `Runner`, and config-file loading until concrete needs arise.
