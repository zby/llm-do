---
description: How to embed llm-do in Python applications (API unstable)
---

# Programmatic Embedding

> **API status: unstable.** The embedding surface is evolving. Expect breaking changes.

llm-do can be used as a library from Python, not just via the CLI. There are two layers:

- **`llm_do.runtime`**: core execution — `Runtime`, `CallContext`, `AgentSpec`, `FunctionEntry`
- **`llm_do.project`**: manifest/linker — `build_registry`, `resolve_entry`, `build_registry_host_wiring`

## Manifest-Driven Embedding

Use the project layer to load `.agent` files and run them the same way the CLI does:

```python
from pathlib import Path

from llm_do.project import (
    EntryConfig,
    build_registry,
    build_registry_host_wiring,
    resolve_entry,
)
from llm_do.runtime import RunApprovalPolicy, Runtime

async def main():
    project_root = Path(".").resolve()
    registry = build_registry(
        ["analyzer.agent"],
        [],
        project_root=project_root,
        **build_registry_host_wiring(project_root),
    )
    entry = resolve_entry(
        EntryConfig(agent="analyzer"),
        registry,
        python_files=[],
        base_path=project_root,
    )
    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
        project_root=project_root,
    )
    runtime.register_agents(registry.agents)

    result, ctx = await runtime.run_entry(
        entry,
        input_data={"input": "Analyze this data"},
    )
    print(result)
```

`build_registry_host_wiring(project_root)` provides the standard built-in toolsets
(filesystem, shell, agent-as-tool wrapping) that the CLI normally assembles. This
wiring is required — the registry no longer implicitly pulls in host toolsets.

## Direct Python (No Manifest)

Skip the manifest entirely and wire agents in pure Python:

```python
from llm_do.models import resolve_model
from llm_do.runtime import AgentSpec, FunctionEntry, CallContext

MODEL = resolve_model("anthropic:claude-haiku-4-5")
EVALUATOR = AgentSpec(
    name="evaluator",
    model=MODEL,
    instructions="Analyze the input.",
)

async def main(_input_data, runtime: CallContext) -> str:
    result = await runtime.call_agent(EVALUATOR, {"input": "hello"})
    return result

ENTRY = FunctionEntry(name="main", fn=main)
```

See [`examples/pitchdeck_eval_direct/`](../examples/pitchdeck_eval_direct/) for
complete working examples of both patterns.

## Open Questions

- Embedding API surface is not yet stable — expect `build_registry` signature changes
- Host wiring assembly may be simplified in future iterations
- See [`docs/reference.md`](reference.md) for the current detailed API reference
