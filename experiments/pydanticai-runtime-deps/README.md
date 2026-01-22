# Experiment: Deps-As-Runtime for PydanticAI

## Context
llm-do uses a runtime object to centralize run-scoped policy (approvals, depth limits, usage
aggregation, message logging) and to provide a uniform tool/worker delegation interface.
PydanticAI supports "agent delegation" as a pattern (a tool function calls another agent's
`run()`), but does not define a first-class runtime object for policy or delegation.

This experiment explores whether we can implement llm-do's usage patterns directly in
PydanticAI by treating `deps` as the runtime object.

## Goal
Prove (or disprove) that the following llm-do semantics can be reproduced in PydanticAI
without custom agent loops:

- Tools can call other agents by name via a shared runtime object.
- Delegation respects a global max depth.
- Usage is aggregated across parent + delegate runs by passing `ctx.usage`.
- Approval workflow can be represented by the proposed `deferred_tool_handler` hook.

## Hypothesis
A minimal runtime object supplied as `deps` can provide the same delegation semantics
as llm-do's WorkerRuntime, while relying on PydanticAI's built-in agent loop.

## Current Architecture

### Core runtime (`runtime.py`)
The experiment uses a **deps-as-runtime** object (`AgentRuntime`) that owns the
run-scoped policy and delegation surface. It is intentionally small and delegates
specialized concerns to helper components.

**AgentRuntime responsibilities**
- Agent registry (`agents`) and delegation (`call_agent`).
- Depth tracking (`depth`, `max_depth`) with child runtime spawning.
- Toolset resolution per call (`toolsets_for`), including approval wrapping.
- Attachment access via an injected `AttachmentResolver`.

**Injected / composed helpers**
- `AttachmentResolver`: resolves attachment paths and loads `BinaryContent`.
- `ToolsetResolver`: instantiates toolsets per agent call from toolset specs.
- `ApprovalWrapper`: wraps toolsets per call using capability-based approvals.

### Toolset flow (per call)
Toolsets are created **per agent call**, not per agent:
1. `AgentRuntime.toolsets_for(agent)` resolves toolset specs for the agent name.
2. `ToolsetResolver` instantiates toolsets using `ToolsetBuildContext`.
3. `ApprovalWrapper` wraps the toolset list if approval is enabled.
4. The resulting toolsets are passed to `agent.run(...)`.

### Attachments flow
Attachments are resolved by the injected `AttachmentResolver`, which supports:
- `path_map` aliases for mock paths (e.g., `path/to/deck.txt` → real file)
- optional `base_path` for relative paths
Tools/agents pass attachment paths; the runtime loads `BinaryContent` on demand.

## Runtime Shape
The runtime object (used as `deps`) provides:

- `agents`: name -> Agent registry
- `max_depth`: global recursion limit
- `depth`: current depth (incremented on delegation)
- `call_agent(name, prompt, ctx)` helper that:
  - checks max depth
  - spawns a child runtime
  - calls the target agent with `deps=child` and `usage=ctx.usage`

## Sketch (PydanticAI-style)

```python
from dataclasses import dataclass, replace
from pydantic_ai import Agent, RunContext

@dataclass
class AgentRuntime:
    agents: dict[str, Agent]
    max_depth: int = 5
    depth: int = 0

    def spawn(self) -> "AgentRuntime":
        if self.depth >= self.max_depth:
            raise RuntimeError(f"max_depth exceeded: {self.depth} >= {self.max_depth}")
        return replace(self, depth=self.depth + 1)

    async def call_agent(self, name: str, prompt: str, ctx: RunContext) -> str:
        agent = self.agents[name]
        child = self.spawn()
        result = await agent.run(prompt, deps=child, usage=ctx.usage)
        return result.output

parent = Agent('openai:gpt-4o', deps_type=AgentRuntime)

@parent.tool
async def worker_call(ctx: RunContext[AgentRuntime], worker: str, prompt: str) -> str:
    return await ctx.deps.call_agent(worker, prompt, ctx)
```

## Prototype
This directory includes runnable prototypes that share the same deps-as-runtime
implementation in `runtime.py`.

Pitch deck example (`run.py`):
- Two agents: orchestrator + pitch evaluator
- Instructions: `prompts/orchestrator.txt`, `prompts/pitch_evaluator.txt`
- Orchestrator calls a mock file tool that returns `path/to/deck.txt`, then
  delegates with the attached file
- Deck input defaults to `input/deck.txt`

File organizer example (`file_organizer.py`):
- Two agents: orchestrator + file organizer
- Instructions: `prompts/file_orchestrator.txt`, `prompts/file_organizer.txt`
- Orchestrator calls a mock file tool that returns `path/to/files.txt`, then
  delegates with the attached file list
- File list defaults to `input/files.txt`

Worker loader helper (`worker_loader.py`):
- Parses `.worker` files using `llm_do.runtime.worker_file`
- Builds PydanticAI Agents from worker definitions
- Adds delegation tools for toolsets that reference other workers
- Resolves `schema_in_ref` to WorkerArgs models and uses them as tool schemas
- If a WorkerArgs model defines `input_parts()`, it is used to build the callee prompt
- Resolves built-in toolsets (filesystem/shell) and Python ToolsetSpecs
- Returns toolset specs/registry so the runtime can instantiate toolsets per call
- Reports unsupported toolsets for follow-up

Example usage (loads the pitchdeck workers and prints unresolved toolsets):

```python
from pathlib import Path

from worker_loader import load_worker_agents

bundle = load_worker_agents(
    worker_files=[
        "examples/pitchdeck_eval/main.worker",
        "examples/pitchdeck_eval/pitch_evaluator.worker",
    ],
    project_root=Path("examples/pitchdeck_eval"),
)
print(bundle.entry_name)
print(bundle.unsupported_toolsets)
```

Run the pitch deck example with a model (or set `LLM_DO_MODEL`):

```bash
.venv/bin/python experiments/pydanticai-runtime-deps/run.py --model openai:gpt-4o-mini
```

To print every event emitted during the run, add `--log-events`:

```bash
.venv/bin/python experiments/pydanticai-runtime-deps/run.py --model openai:gpt-4o-mini --log-events
```

You can point at a custom deck text file:

```bash
.venv/bin/python experiments/pydanticai-runtime-deps/run.py --model openai:gpt-4o-mini --deck /path/to/deck.txt
```

To write OpenTelemetry spans to a local log directory:

```bash
.venv/bin/python experiments/pydanticai-runtime-deps/run.py --model openai:gpt-4o-mini --trace-dir ./logs
```

Each run writes a JSONL trace file named with the run and timestamp. Use `--trace-binary` to include attachment content.

Run the file organizer example:

```bash
.venv/bin/python experiments/pydanticai-runtime-deps/file_organizer.py --model openai:gpt-4o-mini
```

Or point at a custom file list:

```bash
.venv/bin/python experiments/pydanticai-runtime-deps/file_organizer.py --model openai:gpt-4o-mini --files /path/to/files.txt
```

Demo script for `.worker` files (pitchdeck example):

```bash
.venv/bin/python experiments/pydanticai-runtime-deps/demo_pitchdeck_workers.py --model openai:gpt-4o-mini
```

Recursive task decomposer (model-driven input schema):

```bash
.venv/bin/python experiments/pydanticai-runtime-deps/recursive_task_decomposer.py --model openai:gpt-4o-mini
```

## Experiment Plan
1. Create a small set of agents (parent + delegate) and wire them into an `AgentRuntime`.
2. Implement a `worker_call` tool on the parent agent using `ctx.deps.call_agent()`.
3. Confirm:
   - delegation works without extra glue code
   - `max_depth` prevents runaway recursion
   - usage aggregates when `usage=ctx.usage` is passed
4. If `deferred_tool_handler` exists (or can be mocked), confirm approvals can be
   handled without reimplementing the agent loop.

## Out of Scope
- Input schema (llm-do only)
- CLI and UI event streaming
- Toolset approval wrappers beyond the deferred-handler proposal

## Risks
- PydanticAI lacks a first-class runtime object, so app code must carry policy.
- Depth limits may need extra structure if delegation patterns diversify.
- Approval integration depends on upstream acceptance of `deferred_tool_handler`.

## Open Questions
- Should depth be part of `deps` or derived from a separate runtime state object?
- Do we need a standardized `AgentToolset`/`agent.as_tool()` helper upstream?
- Where should a shared agent registry live in a larger application?

## Next Steps
- Implement a minimal prototype in this directory.
- Compare behavior to llm-do's `WorkerToolset` delegation path.
- Identify what core PydanticAI extensions would reduce boilerplate.

## Approvals (Call-Time Wrapping)
The deps runtime can optionally wrap toolsets with the local `pydantic-ai-blocking-approval`
package at call time. This keeps approvals as a runtime concern while avoiding a deferred
tool loop.

Minimal example:

```python
from runtime import AgentRuntime, AttachmentResolver, build_path_map
from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalRequest

def approve_all(_: ApprovalRequest) -> ApprovalDecision:
    return ApprovalDecision(approved=True)

runtime = AgentRuntime(
    agents=agents,
    attachment_resolver=AttachmentResolver(
        path_map=build_path_map({}),
    ),
    approval_callback=approve_all,
    approval_config={
        "shell": {"capabilities": ["proc.exec"]},
    },
    capability_rules={
        "proc.exec": "needs_approval",
    },
)
```

Toolsets are wrapped per call via `runtime.toolsets_for(agent)`.
Toolsets may optionally implement `get_capabilities(name, tool_args, ctx, config)` to
provide per-call capabilities used by the policy wrapper.
Approval decisions are derived from capabilities plus config; toolsets should not
return approval decisions here.
The default runtime policy blocks `proc.exec.unlisted` unless overridden.
