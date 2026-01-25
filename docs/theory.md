# LLM-Based Agentic Systems as Probabilistic Programs

*A hybrid virtual machine for LLM and code.*

> This document sketches a theoretical framing for llm-do. Not a complete theory—just enough conceptual machinery to clarify why certain design choices make sense.

## LLMs as Virtual Machines

An LLM can be viewed as a virtual machine. Give it a sufficiently detailed specification, and it interprets that spec into behavior. This is more than metaphor—projects like [OpenProse](https://github.com/openprose/prose) treat the LLM explicitly as an interpreter: "A long-running AI session is a Turing-complete computer."

The key insight: **simulation with sufficient fidelity is implementation.** When an LLM receives a detailed VM specification, it *becomes* that VM through simulation. The interpreter runs inside the session.

This pure LLM VM approach has limitations:
- Every operation costs tokens (expensive at scale)
- Every step requires API round-trip (high latency)
- All execution is stochastic (unpredictable)

**llm-do takes the next step: a hybrid VM** that unifies LLM execution (neural) and Python execution (symbolic) under a single calling convention. The VM can dispatch to either; callers don't need to know which. This enables moving computation between neural and symbolic as systems evolve—stabilize patterns to code when they emerge, soften rigid code back to LLM when edge cases multiply.

## Probabilistic Programming as Foundation

LLM-based agentic systems are naturally understood as **probabilistic programs**: programs that interleave deterministic computation with sampling from distributions.

```python
x = sample(distribution)    # stochastic
y = f(x)                    # deterministic
z = sample(another_dist(y)) # stochastic
```

What's distinctive about agentic systems is that some components have **unknown, high-variance distributions** (the LLM) while others have **known, deterministic behavior** (traditional code). The LLM's distribution is shaped by prompts, examples, and context—but we don't have direct access to its parameters or structure. The distribution is too complex to characterize directly, so we reason about it through simpler mental models.

## A Useful Mental Model: "Program Sampling"

Programmers often reason about LLMs as if they sample a *program* (or interpretation) from the specification, then execute it:

```
Spec → sample interpretation → execute on input → output
```

This captures why the same prompt can produce qualitatively different behaviors, not just noisy variations of the same behavior—the *interpretation* varies, not just the execution.

Mathematically, this is a mixture model:

```
D(Output | Spec, Input) ≈ Σ Pr[Program | Spec] · D(Output | Program, Input)
```

If you treat `Program` as deterministic, `D(Output | Program, Input)` collapses to a point mass; most of the variance comes from the mixture over programs.

### Example: "Refactor for Readability"

Ask an LLM coding assistant to refactor a function for readability. Different runs might:

- Extract helper functions
- Rename variables for clarity
- Restructure control flow (loops → comprehensions)
- Add comments explaining intent

These aren't noisy variations of *one* strategy—they're different *interpretations* of "readability." Each run samples a different program from the space of valid refactoring approaches.

We don't claim this is how LLMs actually work internally. But as a mental model for reasoning about complex, opaque distributions, it's useful: prompt engineering becomes about shaping a distribution over *behaviors*, not debugging a fixed program.

## Shaping the Distribution

In probabilistic programming, you shape distributions through priors, conditioning, and constraints. With LLMs, you use different mechanisms—but the goal is the same: **narrowing the distribution toward desired behaviors**.

| Mechanism | Effect |
|-----------|--------|
| System prompt | Sets prior expectations, narrows toward intended behavior |
| Few-shot examples | Shifts probability mass toward demonstrated patterns |
| Tool definitions | Biases toward valid actions; can truncate support when tool-only decoding is enforced |
| Output schemas | Constrain structure and sometimes content (enums, ranges, regexes) |
| Conversation history | Dynamic reshaping as context accumulates |
| Temperature | Flattens or sharpens the distribution at sampling time |

Understanding these as **distribution-shaping techniques** clarifies what each can and can't do. Examples shift the mode; schemas constrain the support; temperature reshapes the distribution without changing the underlying model.

## Distribution Boundaries

Probabilistic programs naturally interleave stochastic and deterministic computation. When an LLM calls a tool, or a tool triggers an LLM, execution crosses a **distribution boundary**.

```
Stochastic → Deterministic → Stochastic
   (LLM)        (tool)         (LLM)
distribution   point mass    distribution
```

At each crossing:
- **Stochastic → Deterministic**: Variance usually collapses. Given the same arguments (and environment), the tool returns the same output regardless of how the arguments were produced.
- **Deterministic → Stochastic**: Variance is introduced. A fixed input enters a component that produces a distribution over outputs.

These boundaries are natural **checkpoints**. The deterministic code doesn't care how it was reached—only what arguments it received. This matters for debugging, testing, and reasoning about the system.

But boundaries aren't fixed. As systems evolve, logic moves across them.

## Stabilizing and Softening

Components exist on a spectrum from stochastic to deterministic. Logic can move in both directions.

**Stabilizing**: Replace a stochastic component with a deterministic one. Sample from the distribution and freeze the result into code, configuration, or a decision that no longer varies.

**Softening**: Replace a deterministic component with a stochastic one. Describe new functionality in natural language; the LLM figures out how to do it.

```
Stochastic (flexible, handles ambiguity)  ——stabilize——>  Deterministic (reliable, testable, cheap)
Stochastic (flexible, handles ambiguity)  <——soften———  Deterministic (reliable, testable, cheap)
```

### Why stabilize?

Stabilizing a pattern to code has three practical benefits:

**Cost.** LLM API calls are priced per token. A simple operation like sanitizing a filename might cost fractions of a cent, but at scale those fractions compound. The same operation in Python costs effectively nothing.

**Latency.** Every LLM call involves network round-trip plus inference time. Even fast models add hundreds of milliseconds. Code executes in microseconds.

**Reliability.** Deterministic code returns the same output for the same input, every time. No hallucination, no refusal, no drift across model versions.

The tradeoff: code requires you to know the exact behavior upfront. LLMs let you specify *intent* and figure out the details. That's why stabilizing is progressive—you wait until patterns emerge before committing to code.

### One-shot vs progressive stabilizing

LLMs can act as compilers: spec in, code out. Each run samples from the distribution, producing a different but (hopefully) valid implementation. This is stabilizing in one step.

Alternatively, you can stabilize incrementally. As you observe the LLM's behavior across many runs, you learn which "programs" it tends to sample—and can extract the consistent patterns into deterministic code while keeping the stochastic component for genuinely ambiguous cases.

Example: a file-renaming agent initially uses LLM judgment for everything. You notice it always lowercases and replaces spaces with underscores—so you extract `sanitize_filename()` to Python. The agent still handles ambiguous cases ("is '2024-03' a date or a version?"), but the common path is now code.

Either way, **version both spec and artifact**. Don't rely on "re-generate later" as a build step—regeneration gives you a *different sample*, not the same code.

### Softening as extension

The common path for softening is **extension**: you need new capability, describe it in natural language, and it becomes callable. The rarer path is **replacement**: rigid code is drowning in edge cases, so you swap it for an LLM call that handles linguistic variation.

Real systems need both directions. A component might start as an LLM call (quick to add), stabilize to code as patterns emerge (reliable and fast), then grow new capabilities via softening. The system breathes.

## The Hybrid VM

The hybrid VM unifies neural (LLM) and symbolic (Python) execution **at the tool layer the LLM sees**. This unified calling convention is what enables bidirectional refactoring between stochastic and deterministic components.

### Why unified calling matters

If an LLM call looks completely different from a tool call, refactoring across the boundary is painful. Prompt structure fights the change.

The hybrid VM solves this:
- Agents and tools share a single tool namespace for the LLM
- Prompt call sites stay stable when implementations move across the boundary

```python
# LLM tool call (prompt) stays the same:
# tool: ticket_classifier(...)

# Python orchestration today (neural)
analysis = await ctx.deps.call_agent("ticket_classifier", ticket_text)

# Python orchestration tomorrow (symbolic)
analysis = ticket_classifier(ticket_text)
```

The LLM-facing calling convention is unified. The implementation moved from neural to symbolic; prompts don't change.

### Name-based dispatch

Unified calling requires **name-based dispatch**: components are identified by string name rather than direct object reference.

Why names?

- **Dynamic resolution.** When an LLM decides to call another component, it outputs a string. You need name-based lookup to resolve that string to an implementation.
- **Late binding.** The called component doesn't need to exist when the caller is defined.
- **Implementation-agnostic interfaces.** A name like `ticket_classifier` can resolve to an agent today and a Python function tomorrow.

Direct reference couples caller to implementation. Name-based dispatch keeps the interface stable while implementations change.

## The Harness (llm-do's Addition)

On top of the hybrid VM, llm-do adds a **harness**—an orchestration layer that intercepts operations, manages approvals, and controls execution flow.

The VM enables the harness by providing interception points. Name-based dispatch means every call goes through a lookup layer that can wrap, modify, or gate the invocation. The VM provides the machinery; the harness uses it to implement policies.

The harness enables:
- **Approval workflows**: Human-in-the-loop for sensitive operations (VM provides the interception; harness provides the UI)
- **Composition**: Stochastic and deterministic components interleave freely
- **Testing strategies**: Swap implementations for testing
- **Auditability**: Tool-level logging and inspection

The harness is llm-do's specific implementation choice. The hybrid VM concept stands independently—other systems could build different orchestration layers on the same interception points.

## Testing and Debugging

Stochastic components require different approaches.

**Testing**: Run the same input N times. Check that the distribution of outputs meets expectations—statistical hypothesis testing, not assertion equality. Every piece you stabilize becomes traditionally testable.

**Debugging**: When a prompt "fails," you're not tracing execution—you're reshaping a distribution. The failure might not reproduce. This is why prompt engineering is empirical.

## Design Implications

Treating agentic systems as probabilistic programs suggests:

1. **Be explicit about boundaries**—know where you're crossing between deterministic and stochastic execution
2. **Enable bidirectional refactoring**—design interfaces so components can move across the boundary without rewriting call sites
3. **Reduce variance where reliability matters**—use schemas, constraints, and deterministic code on critical paths
4. **Preserve variance where it helps**—don't over-constrain creative or ambiguous tasks
5. **Version both spec and artifact**—regeneration produces different samples
6. **Design for statistical failure**—expect retries and graceful degradation
7. **Stabilize progressively, soften tactically**—start stochastic for flexibility, extract determinism as patterns emerge

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

See also: [architecture](architecture.md) for internal structure, [reference](reference.md) for API.
