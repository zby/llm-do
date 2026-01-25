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

Similarly, "add error handling" might yield try/catch blocks, input validation, Result types, or defensive returns. Same spec, qualitatively different implementations.

We don't claim this is how LLMs actually work internally. But as a mental model for reasoning about complex, opaque distributions, it's useful: prompt engineering becomes about shaping a distribution over *behaviors*, not debugging a fixed program. This framing recurs throughout—in how we think about stabilizing, testing, and the boundaries between stochastic and deterministic code.

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
Stochastic (flexible, handles ambiguity)  -- stabilize -->  Deterministic (reliable, testable, cheap)
Stochastic (flexible, handles ambiguity)  <-- soften --  Deterministic (reliable, testable, cheap)
```

### Why code wins (when it does)

Stabilizing a pattern to code has three key practical benefits:

**Cost.** LLM API calls are priced per token—input and output. A simple operation like sanitizing a filename might cost fractions of a cent, but at scale those fractions compound. The same operation in Python costs effectively nothing: CPU cycles are measured in nanoseconds, not dollars. When you stabilize a pattern to code, you stop paying for it.

**Latency.** Every LLM call involves network round-trip time plus inference time. Even fast models add hundreds of milliseconds; slower models can take seconds. Code executes in microseconds. For operations on the critical path—especially those called repeatedly in loops—this difference dominates. A workflow that makes 50 LLM calls where 40 could be code is leaving performance on the table.

**Reliability.** Deterministic code returns the same output for the same input, every time. No hallucination, no refusal, no drift across model versions. When you know exactly what a component should do, code does it perfectly. LLMs excel at ambiguity; code excels at precision.

The tradeoff: code requires you to know the exact behavior upfront. LLMs let you specify *intent* and figure out the details. That's why stabilizing is progressive—you wait until patterns emerge before committing to code.

### One-shot stabilizing

LLMs can act as compilers: spec in, code out. Each run samples from the distribution, producing a different but (hopefully) valid implementation.

```
spec → LLM → code → executor → result
       ↑
       samples from distribution
```

This is stabilizing in one step. But unlike traditional compilation, regeneration gives you a *different sample*, not the same code—a consequence of the program sampling model.

### Versioning and Reproducibility

Stabilizing—whether one-shot or progressive—creates artifacts that should be versioned:

- **The spec** (the intent—natural language description of what you want)
- **Generated/stabilized code** (the frozen sample)
- **Model + decoding params** when reproducibility matters

Don't rely on "re-generate later" as a build step—regeneration gives you a *different sample*, not the same code. Treat worker specs and stabilized artifacts as deployable inputs.

Both spec and code are necessary. Keep only the spec, and reproducing what you deployed is practically impossible.[^repro] Keep only the code, and you lose the intent that generated it.

[^repro]: Theoretical reproducibility requires pinning model version, decoding parameters, RNG seeds, and more. In practice, this is rarely done.

### Progressive stabilizing

Rather than generating code in one shot, you can stabilize incrementally. As you observe the LLM's behavior across many runs, you learn which "programs" it tends to sample—and can extract the consistent patterns into deterministic code.

1. Start with a stochastic component (a worker/agent)
2. Run it, observe patterns in its behavior
3. Where outputs are consistent, extract to deterministic code
4. Keep the stochastic component for genuinely ambiguous cases

Example: a file-renaming agent initially uses LLM judgment for everything. You notice it always lowercases and replaces spaces with underscores—so you extract `sanitize_filename()` to Python. The agent still handles ambiguous cases ("is '2024-03' a date or a version?"), but the common path is now code.

### Softening as extension

The common path for softening is **extension**: you need new capability, describe it in natural language, and it becomes callable. Write a spec—or even just user stories—and plug it in. (The new capability is still bounded by available tools and permissions.)

The rarer path is **replacement**: rigid code is drowning in edge cases, so you swap it for an LLM call that handles linguistic variation.

Real systems need both directions. A component might start as an LLM call (quick to add), stabilize to code as patterns emerge (reliable and fast), then grow new capabilities via softening. The system breathes.

## The Hybrid VM and Harness Pattern

The hybrid VM unifies neural (LLM) and symbolic (Python) execution **at the tool layer the LLM sees**. On top of this VM sits a **harness**—the orchestration layer that intercepts operations, manages approvals, and controls execution flow.

Bidirectional flow has a practical requirement: **you need to swap neural and symbolic components without rewriting prompts**.

If an LLM call looks completely different from a tool call, refactoring across the boundary is painful. Prompt structure fights the change.

The hybrid VM solves this:
- Agents and tools share a single tool namespace for the LLM
- The harness intercepts at the tool layer, enabling approvals and composition
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

### Unified Calling as Requirement

Unified calling at the LLM boundary isn't merely convenient—it's a requirement for smooth stabilization.

Consider the alternative: a framework where agents and tools have different LLM-facing names or invocation shapes.

When you stabilize a worker into a tool:
- Prompts must be rewritten to call the new tool
- The change ripples through the system

With unified LLM-facing calls, stabilization is local: the implementation changes, but prompts don't. This is what makes progressive stabilization practical—you can refactor component by component without coordination overhead.

### Name-Based Dispatch

Unified calling requires **name-based dispatch**: components are identified and called by string name rather than direct object reference.

Why names, not references?

**Dynamic resolution.** When an LLM decides to call another component, it outputs a string. You need name-based lookup to resolve that string to an implementation. Direct references can't be generated by the model.

**Late binding.** The called component doesn't need to exist when the caller is defined. New agents can be registered and become callable without modifying existing code or prompts.

**Implementation-agnostic interfaces.** A name like `ticket_classifier` can resolve to an agent today and a Python function tomorrow. The name is the stable interface; the implementation is free to change.

**Plugin architecture.** Third-party components can register under names that existing agents already know how to call.

Direct reference (calling by object rather than name) couples caller to implementation. Changing the implementation requires updating all call sites. This breaks the local refactoring property that makes stabilization practical.

### What the harness enables

- **Progressive stabilizing**: Start flexible, extract determinism as patterns emerge
- **Easy extension**: Add new capability by writing a spec and registering it
- **Composition**: Stochastic and deterministic components interleave freely
- **Testing strategies**: Swap implementations for testing

### What the harness doesn't hide

Same interface doesn't mean same semantics. The caller may still need to know what kind of component they're calling for error handling, retry logic, and performance expectations. The abstraction is thin enough to enable refactoring and honest enough that you know when you're crossing the boundary.

## Distribution Shaping Surfaces

The mechanisms that shape LLM output distributions map to concrete configuration surfaces:

| Mechanism | Effect |
|-----------|--------|
| System prompt | Sets prior expectations, narrows toward intended behavior |
| Few-shot examples | Shifts probability mass toward demonstrated patterns |
| Tool definitions | Biases toward valid actions; can truncate support when tool-only decoding is enforced |
| Output schemas | Constrain structure and sometimes content (enums, ranges, regexes) |
| Temperature / model | Flattens or sharpens the distribution at sampling time |

Each narrows the distribution differently. Schemas constrain structure; examples shift the mode; temperature controls sampling breadth. Understanding these as **distribution-shaping techniques** clarifies what each can and can't do.

## Testing and Debugging

Stochastic components require different approaches.

**Testing**: Run the same input N times. Check that the distribution of outputs meets expectations—statistical hypothesis testing, not assertion equality. (Caching and model updates can break i.i.d. assumptions.) Every piece you stabilize becomes traditionally testable—one of the strongest arguments for progressive stabilizing.

**Debugging**: When a prompt "fails," you're not tracing execution—you're reshaping a distribution. The failure might not reproduce. Changes have non-local effects. There's no stack trace. This is why prompt engineering is empirical.

**Error taxonomy**: LLM components have characteristic failure modes—hallucination, refusal, misinterpretation, drift, format violation—each suggesting different mitigations.

## Design Implications

Treating agentic systems as probabilistic programs suggests:

1. **Be explicit about boundaries**—know where you're crossing between deterministic and stochastic execution

2. **Enable bidirectional refactoring**—design interfaces so components can move across the boundary without rewriting call sites

3. **Reduce variance where reliability matters**—use schemas, constraints, and deterministic code on critical paths

4. **Preserve variance where it helps**—don't over-constrain creative or ambiguous tasks

5. **Version both spec and artifact**—regeneration produces different samples, so you need both

6. **Design for statistical failure**—expect retries and graceful degradation

7. **Stabilize progressively, soften tactically**—start stochastic for flexibility, extract determinism as patterns emerge, add capabilities via specs

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

This sketch provides the conceptual backdrop for llm-do's design. The VM framing—pure LLM VMs exist, llm-do is a hybrid—positions the system in the emerging landscape of LLM-based computation. The probabilistic programming framing gives us established vocabulary; the "program sampling" mental model captures how practitioners intuitively reason about LLM behavior; the hybrid VM shows how to build systems that can evolve across the neural-symbolic boundary. The [architecture document](architecture.md) explains internal structure; the [reference](reference.md) covers the API.
