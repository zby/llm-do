---
description: Brainstorm on using Pydantic Monty for a pure-function (no side effects) variant of llm-do
---

# Monty + llm-do: Pure Functions Brainstorm

## The "Conflicting Announcements" Tension

Pydantic ships Monty — a sandboxed Python interpreter where agents write code instead
of making sequential tool calls. PydanticAI announces `CodeModeToolset` to integrate it.
Meanwhile, llm-do already has:

- `pure-dynamic-tools` design (LLM-authored orchestration code with only `call_agent`)
- `pure-python-vs-mcp-codemode` note distinguishing human-authored composite tools from
  LLM-authored code-mode tools
- The whole approval/harness layer for safe tool execution

The tension: Monty's sandbox-by-construction seems to overlap with llm-do's
approval-by-interception model. If Monty makes tool execution safe by limiting what code
can do, does the approval layer become redundant?

**Resolution**: They serve different domains on the same spectrum.

## The Spectrum of Agent Capabilities

```
Pure computation ←──────────────────────────────→ Full system access
     │                    │                              │
  Monty sandbox      Approval-gated              Trusted code
  No side effects    Controlled effects           (FunctionEntry)
  No approval        Requires approval            Developer-authored
  needed             per call
```

A "pure-function llm-do" lives at the left end. Current llm-do lives in the middle.
Both are valid operating points. The question is whether the left end is useful enough
to be a distinct mode.

## What Monty Brings to the Table

### The External Function = `call_agent`

Monty's core mechanism: code runs → hits external function → **pauses** → host handles
it → **resumes** with result. This maps directly onto llm-do's calling convention:

| Monty concept          | llm-do equivalent                    |
|------------------------|--------------------------------------|
| External function      | `call_agent(name, input)`            |
| Pause at function call | Blocking at tool boundary            |
| Host handles call      | Runtime dispatches to agent/tool     |
| Resume with result     | Tool result returned to caller       |
| Serializable snapshot  | *(no equivalent — new capability)*   |

The critical insight: **Monty's pause/resume solves the "code mode can't call back to
LLM" problem** identified in the `pure-python-vs-mcp-codemode` note. MCP code mode
sandboxes run to completion. Monty sandboxes can pause mid-execution to call an LLM,
then resume with the result. This is exactly what llm-do's pure tools need.

### What "Pure" Means Here

"Pure" in the functional programming sense: no side effects on the host system. But
with two deliberate escape hatches:

1. **LLM calls** — non-deterministic but read-only w.r.t. system state
2. **Agent calls** — delegate to other agents, which may themselves be pure or effectful

For a fully pure variant, we restrict escape hatch #2: agents in the pure namespace
can only call other pure agents. No filesystem, no shell, no network. The only
"external" operations are LLM inference calls.

### What Monty Cannot Do (Limitations)

- No classes (coming soon, but not yet)
- Limited stdlib: `sys`, `typing`, `asyncio`, `dataclasses`, `json`
- No `re`, `collections`, `itertools`, `datetime`, `pathlib`
- No third-party packages (no Pydantic models inside Monty code)
- No `match` statements

These limitations constrain what the LLM can express. For orchestration code (calling
agents, transforming results, branching), this is mostly fine. For complex data
processing, it's restrictive.

## Architecture: Three Possible Integration Points

### Option A: Monty as a Tool Sandbox (replaces RestrictedPython)

The `pure-dynamic-tools` design currently proposes RestrictedPython. Monty is strictly
better for this:

```python
# Current design sketch (RestrictedPython):
class PureToolExecutor:
    async def execute(self, code: str, args: dict) -> Any:
        byte_code = compile_restricted_exec(code)
        exec(byte_code.code, restricted_globals, env)

# Monty replacement:
class PureToolExecutor:
    async def execute(self, code: str, args: dict) -> Any:
        m = pydantic_monty.Monty(code, inputs=list(args.keys()),
                                  external_functions=['call_agent'])
        return await pydantic_monty.run_monty_async(
            m, inputs=args,
            external_functions={'call_agent': self.call_agent}
        )
```

**Advantage**: Monty is purpose-built for this. Better security model (Rust interpreter,
not Python bytecode restriction), faster startup, serializable state.

**Scope**: This is a tactical replacement — swap the sandbox implementation inside the
existing `PureToolsToolset` design. The rest of llm-do stays the same.

### Option B: CodeModeToolset as a Toolset Type

Use PydanticAI's `CodeModeToolset` directly as a llm-do toolset. The agent gets a
"write code" tool instead of individual function tools.

```yaml
---
name: researcher
toolsets:
  - code_mode    # Wraps pure function tools into CodeModeToolset
  - analyzer     # Another agent (still a regular toolset)
---
Research the topic by writing Python code that calls the available functions.
```

Behind the scenes:
- `code_mode` wraps a `FunctionToolset` containing pure functions
- The LLM writes Python code that calls those functions
- Monty executes the code, pausing at each function call
- PydanticAI handles the pause/resume loop

**Advantage**: Near-zero integration work. PydanticAI does the heavy lifting.
llm-do just needs to recognize `CodeModeToolset` as a valid toolset type.

**Limitation**: The wrapped functions must be the ones PydanticAI knows about.
Agent delegation would need to be exposed as one of those functions.

### Option C: Pure-Mode llm-do (a distinct execution mode)

A fundamentally simpler runtime for the pure-function case:

```
[User Input]
    ↓
[LLM generates Python code]
    ↓
[Monty executes]
    ├── pure functions: data transforms, parsing, formatting
    ├── external: call_llm(prompt) → pause → LLM inference → resume
    ├── external: call_llm_structured(prompt, schema) → pause → resume
    └── return final result
```

No approval layer. No toolsets. No CallScope/CallFrame complexity. Just:
1. A set of registered pure functions
2. `call_llm` as the single escape hatch
3. Monty as the execution engine

```python
# Minimal runtime for pure mode
class PureRuntime:
    def __init__(self, functions: dict[str, Callable], model: str):
        self.functions = functions
        self.model = model

    async def run(self, prompt: str) -> Any:
        # LLM generates code
        code = await self._generate_code(prompt)
        # Monty executes with registered functions + call_llm
        m = pydantic_monty.Monty(
            code,
            external_functions=list(self.functions) + ['call_llm']
        )
        return await pydantic_monty.run_monty_async(
            m,
            external_functions={
                **self.functions,
                'call_llm': self._call_llm,
            }
        )
```

**Advantage**: Radical simplification. No approval, no toolsets, no registry, no
manifest. Just functions + LLM + sandbox.

**Limitation**: Can't do anything effectful. Not even read a file.

## What Pure-Mode Enables

### 1. Multi-step Reasoning Pipelines

```python
# LLM generates this:
queries = call_llm("Generate 5 research angles for: " + topic)
queries = json.loads(queries)

findings = []
for q in queries:
    result = call_llm("Research this specific angle: " + q)
    findings.append({"angle": q, "finding": result})

summary = call_llm("Synthesize these findings: " + json.dumps(findings))
```

The LLM writes orchestration code that calls itself multiple times. Each `call_llm`
pauses Monty, runs inference, resumes. The control flow (loop, accumulation,
synthesis) is deterministic.

### 2. Map-Reduce Over LLM Calls

```python
# Process a batch of items through LLM reasoning
items = json.loads(input_data)
classified = []
for item in items:
    category = call_llm_structured(
        "Classify this item: " + item["text"],
        {"type": "object", "properties": {"category": {"type": "string"}}}
    )
    classified.append({**item, "category": category})

# Group and summarize
groups = {}
for item in classified:
    groups.setdefault(item["category"], []).append(item)

summaries = {}
for cat, items in groups.items():
    summaries[cat] = call_llm("Summarize these " + cat + " items: " + json.dumps(items))
```

### 3. Conditional Agent Routing

```python
# Triage and route
assessment = call_llm_structured(
    "Assess this request: " + user_input,
    {"type": "object", "properties": {
        "complexity": {"enum": ["simple", "complex"]},
        "domain": {"type": "string"}
    }}
)

if assessment["complexity"] == "simple":
    result = call_llm("Answer directly: " + user_input)
else:
    # Multi-step for complex queries
    plan = call_llm("Create a research plan for: " + user_input)
    steps = json.loads(plan)
    results = []
    for step in steps:
        results.append(call_llm("Execute this research step: " + step))
    result = call_llm("Synthesize: " + json.dumps(results))
```

### 4. Serializable Long-Running Computations

Monty can snapshot mid-execution. For a computation that makes 50 LLM calls, you
could:
- Serialize state after each call
- Resume from checkpoint on failure
- Distribute steps across workers
- Show progress (step 23/50)

This is something neither current llm-do nor vanilla PydanticAI can do.

## The Interesting Hybrid: Pure Core + Effectful Shell

Gary Bernhardt's "functional core, imperative shell" applied to agents:

```
┌─────────────────────────────────────────┐
│  Imperative Shell (llm-do harness)      │
│  - Reads input files                    │
│  - Writes output files                  │
│  - Manages state                        │
│  - Handles approvals                    │
└────────────────┬────────────────────────┘
                 │
    ┌────────────▼────────────┐
    │  Functional Core (Monty)│
    │  - Pure computation     │
    │  - LLM reasoning calls  │
    │  - Data transformation  │
    │  - No side effects      │
    └─────────────────────────┘
```

A FunctionEntry (imperative shell) reads data, passes it to a Monty-based pure
computation, then writes the result. The pure core is maximally testable and safe.
The shell handles the messy real-world interface.

```python
# entry function (imperative shell)
async def main(input_data, ctx):
    # Effectful: read input
    raw_data = await ctx.call_agent("filesystem_reader", {"path": input_data["file"]})

    # Pure core: all reasoning happens in Monty
    result = await ctx.call_agent("pure_analyzer", {"data": raw_data})

    # Effectful: write output
    await ctx.call_agent("filesystem_writer", {"path": "output.json", "content": result})

    return result
```

The `pure_analyzer` agent runs entirely in Monty with only `call_llm`. It's
deterministic modulo LLM responses, fully testable with mock LLM responses, and
safe by construction.

## How This Relates to Approvals

The key realization: **pure functions don't need approvals because there's nothing
to approve**. No filesystem access, no shell commands, no network calls. The
approval system is exactly the machinery you need for the imperative shell — and
exactly the machinery you can skip for the functional core.

This suggests a natural split:
- **Pure agents**: Run in Monty, no approval wrapper, no toolsets, just functions + LLM
- **Effectful agents**: Run in current llm-do runtime with full approval machinery

The unified calling convention still works: an effectful agent can call a pure agent
(it's just another tool), and a pure agent's `call_agent` can delegate to another
pure agent. The boundary is at the agent level, not the function level.

## Concrete Next Steps (if pursuing this)

1. **Spike**: Add `pydantic-monty` as a dependency, build a minimal example that
   runs LLM-generated code with `call_llm` as the sole external function

2. **Evaluate CodeModeToolset**: When PydanticAI ships it, test whether it can be
   used directly as an llm-do toolset wrapping pure functions + `call_agent`

3. **Design the pure agent spec**: What does a `.agent` file look like when it
   declares "I'm pure"? Something like:
   ```yaml
   ---
   name: analyzer
   mode: pure  # or: sandbox: monty
   functions:
     - parse_json
     - format_output
   ---
   ```

4. **Prototype the hybrid pattern**: FunctionEntry shell + Monty core, to validate
   the functional-core/imperative-shell split works in practice

## Open Questions

1. **Is `call_llm` pure enough?** LLM calls are non-deterministic and cost money.
   Should pure-mode have a budget/limit concept even without approval?

2. **Structured output in Monty**: How does `call_llm_structured(prompt, schema)`
   work when Monty can't import Pydantic? Return dicts only?

3. **Error handling**: What happens when Monty code raises an exception? When an
   LLM call fails? How does the error surface to the outer agent?

4. **Async in Monty**: Monty supports `asyncio`. Can we do `asyncio.gather` over
   multiple `call_llm` calls for parallel inference? This would be a significant
   efficiency win.

5. **Class support timeline**: Monty's "no classes" limitation means no dataclasses,
   no typed containers. When classes ship, this opens up much richer data modeling
   inside the sandbox.

6. **Progressive stabilization path**: Can a pure agent be "graduated" to a
   FunctionEntry when its behavior stabilizes? The calling convention is the same
   (`call_agent`), but the implementation moves from Monty-sandboxed to trusted
   Python.

7. **Monty as Monty grows**: Monty is young. What if it adds file I/O later? Does
   "pure mode" mean "Monty with only these external functions" rather than "Monty
   in its default configuration"?

## Related

- `docs/notes/pure-dynamic-tools.md` — RestrictedPython approach to same problem
- `docs/notes/pure-python-vs-mcp-codemode.md` — code mode comparison
- `docs/notes/container-security-boundary.md` — container approach to isolation
- `docs/notes/llm-do-vs-pydanticai-runtime.md` — what llm-do adds over vanilla PydanticAI
