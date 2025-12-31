# Simplifying v2_direct run.py

## Context
`experiments/inv/v2_direct/run.py` demonstrates running workers directly via Python, but it carries a lot of boilerplate (sys.path hack, instruction loading, worker assembly, approval wrapping, UI wiring, context run). The goal is to identify ways to make this script much simpler and to offer multiple ways to run the library (CLI, config-driven, Python API, embedding).

## Current Pain Points
- **170 lines** for what should be "run a worker with some config"
- Manual `sys.path` injection (lines 17-18)
- Explicit instruction file loading (lines 52-54)
- 35-line recursive approval wrapper (lines 82-116)
- Manual UI event wiring (lines 124-127)
- Low-level Context setup with redundant WorkerEntry reconstruction (lines 134-153)

## Target: 12-Line Script

```python
#!/usr/bin/env python
"""v2_direct: Run pitch deck evaluation."""

from llm_do import quick_run

result = quick_run(
    ".",  # current directory
    prompt="Go",
    model="anthropic:claude-haiku-4-5",
    approve_all=True,
    verbosity=1,
)
print(result)
```

## Proposed API Levels

| Level | Use Case | API |
|-------|----------|-----|
| 1. One-liner | Demos, quick runs | `quick_run(path, prompt, model=...)` |
| 2. Runner object | Reusable, multiple runs | `Runner.from_dir(path).run(prompt)` |
| 3. Explicit workers | Custom toolsets | Build WorkerEntry manually, pass to Runner |
| 4. Full Context | Embedding, custom everything | `Context.create()` with ApprovalPolicy |

### Level 1: `quick_run()`

```python
from llm_do import quick_run

result = quick_run(
    "experiments/inv/v2_direct",
    prompt="Go",
    model="anthropic:claude-haiku-4-5",
    approve_all=True,
    verbosity=1,
)
```

### Level 2: Runner Object

```python
from llm_do import Runner

runner = Runner.from_dir(
    "experiments/inv/v2_direct",
    model="anthropic:claude-haiku-4-5",
)

result = runner.run("Go")

# Or with overrides
result = runner.run(
    "Go",
    approve_all=False,
    on_approval=lambda req: input(f"Approve {req.tool_name}? ") == "y",
)
```

### Level 3: Explicit Worker Construction

```python
from llm_do import WorkerEntry, Runner
from llm_do.toolsets.filesystem import FileSystemToolset

pitch_evaluator = WorkerEntry(
    name="pitch_evaluator",
    instructions="instructions/pitch_evaluator.md",  # auto-loads file
    model="anthropic:claude-haiku-4-5",
)

main = WorkerEntry(
    name="main",
    instructions="instructions/main.md",
    model="anthropic:claude-haiku-4-5",
    toolsets=[FileSystemToolset(), pitch_evaluator],
)

result = Runner(main).run("Go", approve_all=True, verbosity=1)
```

### Level 4: Full Control

```python
from llm_do import WorkerEntry, Context
from llm_do.approval import ApprovalPolicy

main = WorkerEntry.from_dir("experiments/inv/v2_direct")

def my_approval(request):
    if request.tool_name.startswith("read_"):
        return True
    return input(f"Approve {request.tool_name}? ") == "y"

ctx = Context.create(
    main,
    model="anthropic:claude-haiku-4-5",
    approval=ApprovalPolicy(callback=my_approval),
    verbosity=1,
)

result = await ctx.run("Go")
```

## Key Implementation: `wrap_tree()`

The single biggest win is a function that recursively wraps all toolsets with approval, eliminating the 35-line recursive wrapper from user scripts:

```python
# llm_do/approval.py

from enum import Enum

class ApprovalMode(Enum):
    AUTO = "auto"      # Approve everything
    DENY = "deny"      # Deny everything (for testing)
    PROMPT = "prompt"  # Ask user

def wrap_tree(
    entry: WorkerEntry,
    mode: ApprovalMode | str = "prompt",
    callback: Callable | None = None,
) -> WorkerEntry:
    """Recursively wrap all toolsets in a WorkerEntry tree with approval."""
    from pydantic_ai_blocking_approval import ApprovalToolset, ApprovalMemory, ApprovalDecision

    memory = ApprovalMemory()

    def approval_callback(request):
        if mode == "auto" or mode == ApprovalMode.AUTO:
            return ApprovalDecision(approved=True)
        if mode == "deny" or mode == ApprovalMode.DENY:
            return ApprovalDecision(approved=False, reason="Auto-denied")
        if callback:
            result = callback(request)
            if isinstance(result, bool):
                return ApprovalDecision(approved=result)
            return result
        raise PermissionError(f"Tool '{request.tool_name}' requires approval")

    def wrap_toolsets(toolsets):
        wrapped = []
        for toolset in toolsets:
            if isinstance(toolset, WorkerEntry) and toolset.toolsets:
                toolset = toolset.replace(toolsets=wrap_toolsets(toolset.toolsets))
            wrapped.append(ApprovalToolset(
                inner=toolset,
                approval_callback=approval_callback,
                memory=memory,
            ))
        return wrapped

    return entry.replace(toolsets=wrap_toolsets(entry.toolsets))
```

## Directory Structure Convention

```
experiments/inv/v2_direct/
    instructions/
        main.md              # Main worker instructions (required)
        pitch_evaluator.md   # Sub-worker instructions
    config.yaml              # Optional: defines toolsets and worker tree
    run.py                   # Minimal script (12 lines)
```

Optional `config.yaml`:
```yaml
model: anthropic:claude-haiku-4-5
workers:
  main:
    instructions: instructions/main.md
    toolsets:
      - filesystem: {}
      - worker: pitch_evaluator
  pitch_evaluator:
    instructions: instructions/pitch_evaluator.md
```

## Migration Path

| Phase | Change | Impact | Risk |
|-------|--------|--------|------|
| 1 | Add `wrap_tree()` to `llm_do.approval` | Removes 35 lines from user scripts | Low |
| 2 | Add `WorkerEntry.replace()` method | Cleaner immutable updates | Low |
| 3 | Add `Runner` class | Bundles Context + display wiring | Medium |
| 4 | Add `quick_run()` function | Trivial once Runner exists | Low |
| 5 | Add `WorkerEntry.from_dir()` + config | Optional, config-driven approach | Medium |

**Recommendation**: Start with Phase 1 alone—it's additive, low-risk, and immediately cuts run.py roughly in half.

## Design Decisions

### Runner namespace
- **Avoid** `llm_do.run` as both module and function (confusing)
- **Prefer** `llm_do.quick_run()` for the one-liner, `llm_do.Runner` for the class
- Keep internal helpers in `llm_do.runner` module

### Code-first vs config-driven
- **Primary**: Code-first with helpers (more Pythonic, better IDE support)
- **Secondary**: Config for reproducibility and CLI integration
- Avoid maintaining two parallel schema definitions

### Approval granularity
- **Default**: Global policy (`approve_all=True/False`)
- **Defer**: Per-tool and per-worker settings until concrete need arises

### Example organization
- Move polished examples to `examples/` as public modules
- Keep `experiments/` for scratch work, don't standardize
