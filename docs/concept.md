# llm-do: Design and Implementation

> How llm-do realizes the hybrid VM model. For the theoretical foundation—probabilistic programs, distribution boundaries, why stabilizing works—see [theory.md](theory.md).

## Workers as Functions

A **worker** is a prompt + configuration + tools, packaged as an executable unit. Workers are the neural operations of the hybrid VM.

```yaml
---
name: file_organizer
model: anthropic:claude-haiku-4-5
toolsets: [filesystem]
---
You organize files by renaming them to consistent formats.
Given a filename, return a cleaned version.
```

Workers call other workers and Python tools interchangeably—the calling convention is unified:

```python
# From Python
result = await ctx.call("file_organizer", {"input": filename})

# From another worker (via tool call)
# The LLM sees both workers and tools as callable functions
```

## Unified Calling Convention

Theory says: unified calling enables local refactoring when components move across the neural-symbolic boundary. Here's how llm-do implements it.

**Both workers and tools use `ctx.call()`:**

```python
# Call a worker (neural)
analysis = await ctx.call("sentiment_analyzer", {"input": text})

# Call a tool (symbolic) - same syntax
sanitized = await ctx.call("sanitize_filename", {"name": raw_name})
```

**Workers see tools and other workers identically.** When an LLM runs, its available tools include both Python functions and other workers. It doesn't know—or need to know—which is which.

**Stabilizing doesn't change call sites.** When `sentiment_analyzer` graduates from a worker to a Python function, callers keep using `ctx.call("sentiment_analyzer", ...)`. The registry dispatches to the new implementation.

## The Harness Layer

The harness is the orchestration layer sitting on top of the VM. It's imperative—your code owns control flow.

**Key responsibilities:**
- Dispatch calls to workers or tools
- Intercept tool calls for approval
- Manage execution context and depth limits
- Track conversation state within worker runs

**Harness vs. graph DSLs:**

| Aspect | Graph DSLs | llm-do Harness |
|--------|------------|----------------|
| Control flow | DSL constructs | Native Python |
| State | Global context through graph | Local scope per worker |
| Approvals | Checkpoint/resume | Blocking interception |
| Refactoring | Redraw edges | Change code |

Need a fixed sequence? Write a loop. Need dynamic routing? Let the LLM decide. Same calling convention for both.

## Approvals as Syscalls

Every tool call from an LLM can be intercepted. Think syscalls: when a worker needs to do something potentially dangerous, execution blocks until the harness grants permission.

```python
runtime = Runtime(
    run_approval_policy=RunApprovalPolicy(
        mode="prompt",  # Ask user for each call
        # Or: "approve_all", "reject_all", custom callable
    )
)
```

**Pattern-based rules** auto-approve safe operations:

```python
def my_policy(call_info):
    if call_info.tool_name == "read_file":
        return "approve"  # Always safe
    if call_info.tool_name == "delete_file":
        return "reject"   # Never allow
    return "prompt"       # Ask for others
```

**Approvals reduce risk, not eliminate it.** Prompt injection can trick LLMs into misusing approved tools. Treat approvals as one defense layer. For real isolation, use containers.

## Distribution Shaping Surfaces

Theory identifies mechanisms that shape LLM output distributions. Here's how they map to llm-do:

| Theory concept | llm-do surface |
|----------------|----------------|
| System prompt | Worker `system_prompt` field, spec body |
| Few-shot examples | Examples in worker spec |
| Tool definitions | `@tools.tool` decorators, toolset schemas |
| Output schemas | Pydantic models, structured output config |
| Temperature / model | Worker config: `model`, `temperature` |

Each narrows the distribution differently. Schemas constrain structure; examples shift the mode; temperature controls sampling breadth.

## Stabilizing Workflow

Theory says: stabilize stochastic components to deterministic code as patterns emerge. Here's the practical workflow.

### 1. Start stochastic

Worker handles everything with LLM judgment:

```yaml
---
name: filename_cleaner
model: anthropic:claude-haiku-4-5
---
Clean the given filename: remove special characters,
normalize spacing, ensure valid extension.
```

### 2. Observe patterns

Run it repeatedly. Watch what the LLM consistently does:
- Always lowercases
- Replaces spaces with underscores
- Strips leading/trailing whitespace
- Keeps alphanumerics and `.-_`

### 3. Extract to code

Stable patterns become Python:

```python
@tools.tool
def sanitize_filename(name: str) -> str:
    """Remove special characters from filename."""
    name = name.strip().lower()
    return "".join(c if c.isalnum() or c in ".-_" else "_" for c in name)
```

### 4. Keep stochastic edges

Worker still handles ambiguous cases the code can't:

```yaml
---
name: filename_cleaner
model: anthropic:claude-haiku-4-5
toolsets: [filename_tools]
---
Clean the given filename. Use sanitize_filename for basic cleanup.
For ambiguous cases (is "2024-03" a date or version?), use judgment
to pick the most descriptive format.
```

### What changes when you stabilize

| Aspect | Before (stochastic) | After (deterministic) |
|--------|---------------------|----------------------|
| Cost | Per-token API charges | Effectively free |
| Latency | Network + inference | Microseconds |
| Reliability | May vary | Identical every time |
| Testing | Statistical sampling | Assert equality |
| Approvals | May need user consent | Trusted by default |

### Canonical progression

The pitchdeck examples demonstrate this:

1. **[`pitchdeck_eval/`](../examples/pitchdeck_eval/)** — All LLM: orchestrator decides everything
2. **[`pitchdeck_eval_stabilized/`](../examples/pitchdeck_eval_stabilized/)** — Extracted `list_pitchdecks()` to Python
3. **[`pitchdeck_eval_code_entry/`](../examples/pitchdeck_eval_code_entry/)** — Python orchestration, LLM only for analysis

## Softening Workflow

Theory says: soften deterministic code back to stochastic when edge cases multiply or you need new capability.

### Extension (common)

Need new capability? Write a spec:

```yaml
---
name: sentiment_analyzer
model: anthropic:claude-haiku-4-5
---
Analyze the sentiment of the given text.
Return: positive, negative, or neutral with confidence score.
```

Now it's callable:

```python
result = await ctx.call("sentiment_analyzer", {"input": feedback})
```

### Replacement (rare)

Rigid code drowning in edge cases? A function full of `if/elif` handling linguistic variations might be better as an LLM call that handles the variation naturally.

### Hybrid pattern

Python handles deterministic logic; workers handle judgment:

```python
@tools.tool
async def evaluate_document(ctx: RunContext[WorkerRuntime], path: str) -> dict:
    content = load_file(path)           # deterministic
    if not validate_format(content):    # deterministic
        raise ValueError("Invalid format")

    # Stochastic: LLM judgment for analysis
    analysis = await ctx.deps.call("content_analyzer", {"input": content})

    return {                            # deterministic
        "score": compute_score(analysis),
        "analysis": analysis
    }
```

Think: "deterministic pipeline that uses LLM where judgment is needed."

## Toolset Patterns

### Basic toolset

```python
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import ToolsetSpec

def build_tools(_ctx):
    tools = FunctionToolset()

    @tools.tool
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    return tools

tools = ToolsetSpec(factory=build_tools)
```

### Toolset with runtime access

```python
from pydantic_ai.tools import RunContext
from llm_do.runtime import WorkerRuntime

def build_tools(_ctx):
    tools = FunctionToolset()

    @tools.tool
    async def delegate_analysis(ctx: RunContext[WorkerRuntime], text: str) -> str:
        """Delegate to another worker."""
        return await ctx.deps.call("analyzer", {"input": text})

    return tools
```

### Toolset policies

Constrain what tools can do in code, not prompt instructions:

```python
def build_tools(_ctx):
    tools = FunctionToolset()

    @tools.tool
    def write_file(path: str, content: str) -> str:
        """Write content to a file."""
        # Policy: only allow writes to output directory
        if not path.startswith("output/"):
            raise ValueError("Can only write to output/")
        Path(path).write_text(content)
        return f"Wrote {path}"

    return tools
```

## Tradeoffs

**llm-do is a good fit when:**
- You want normal Python control flow (branching, loops, retries)
- You're prototyping and will stabilize as patterns emerge
- You need tool-level auditability and approvals
- You want flexibility to refactor between LLM and code

**It may be a poor fit when:**
- You need durable workflows with checkpointing/replay
- Graph visualization is your primary interface
- You need distributed orchestration out of the box

llm-do can be a component *within* durable workflow systems (Temporal, Prefect), but doesn't replace them.

---

**Further reading:**
- [theory.md](theory.md) — Theoretical foundation: probabilistic programs, distribution boundaries
- [architecture.md](architecture.md) — Internal structure: runtime scopes, execution flow
- [reference.md](reference.md) — API reference: worker format, toolset API, runtime methods
