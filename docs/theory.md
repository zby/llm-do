# Stochastic Computation Theory: A Sketch

> This document sketches a theoretical framing for llm-do. It's not a complete theory—just enough conceptual machinery to clarify why certain design choices make sense.

## The Core Distinction

Traditional computers are deterministic: given program P and input I, you get output O. The same input always produces the same output.

LLMs are **stochastic computers**: given a specification S and input I, you get a sample from a probability distribution over outputs.

```
Traditional:   (Program, Input) → Output
Stochastic:    (Spec, Input) → sample from Distribution[Output]
```

This isn't a bug awaiting a fix—though for many applications we do want to reduce variance. It's intrinsic to how these systems work. The temperature parameter makes it explicit: you're controlling how broadly you sample from the distribution.

## What Shapes the Distribution

The "spec" isn't a single thing. Multiple factors shape the output distribution, each with different effects:

| Factor | Effect on Distribution |
|--------|----------------------|
| System prompt | Sets prior expectations, narrows toward intended behavior |
| Few-shot examples | Shifts probability mass toward demonstrated patterns |
| Tool definitions | Truncates distribution to valid action space |
| Output schemas | Constrains structure, not content |
| Conversation history | Dynamic reshaping as context accumulates |
| Temperature | Controls sampling breadth, not distribution shape |

Understanding these as **distribution-shaping techniques** clarifies what each intervention can and can't do. Examples shift the mode; schemas constrain the support; temperature affects sampling, not the underlying probabilities.

## Distribution Boundaries

When stochastic computation calls deterministic code (or vice versa), execution crosses a **distribution boundary**.

```
Stochastic → Deterministic → Stochastic
   (LLM)        (tool)         (LLM)
distribution   point mass    distribution
```

At each crossing:
- **Stochastic → Deterministic**: Variance collapses. Whatever probabilistic path got here, the tool's behavior is now fixed.
- **Deterministic → Stochastic**: Variance is introduced. A fixed input enters a system that produces a distribution over outputs.

These boundaries are natural **checkpoints**. The deterministic code doesn't care how it was reached—only what arguments it received. This matters for debugging, testing, and reasoning about the system.

## Stochastic Compilation

LLMs can act as compilers: spec in, code out. But unlike traditional compilation, each run may yield different code.

Traditional compilation fuses with execution because it's deterministic—the intermediate form is derivable from the source. Stochastic compilation breaks this:

```
spec → LLM → code → executor → result
       ↑
       samples from distribution
```

**Practical consequence**: Both spec and generated code are distinct artifacts that should be versioned. If you keep only the spec, you can't reproduce what you deployed. If you keep only the code, you lose the intent that generated it. Regeneration gives you a *different sample*, not the same code.

## Hardening and Softening

Logic can move across the distribution boundary in both directions.

**Hardening** (stochastic → deterministic): As patterns stabilize, extract them to code. Deterministic code doesn't hallucinate, can be unit tested, runs faster, and doesn't consume API tokens.

**Softening** (deterministic → stochastic): Add new functionality by writing a spec—or even just user stories—and plugging it into the system as a worker. The spec describes what you want; the LLM figures out how to do it. You can also combine user stories into a coherent spec using an LLM, then patch that into your program.

```
Harden                              Soften
   ↓                                   ↓
Stochastic ◄─────────────────────► Deterministic
(flexible,                          (reliable,
 handles ambiguity)                  testable, cheap)
```

The common softening path is **extension**: you need new capability, you describe it in natural language, and it becomes callable. The rarer path is **replacement**: rigid code is drowning in edge cases, so you swap it for an LLM call that handles linguistic variation.

Real systems need both directions. A component might start as an LLM call (quick to add), harden to code as patterns emerge (reliable and fast), then have new capabilities softened in as requirements grow.

## The Need for a Harness

Bidirectional flow has a practical requirement: **you need to swap stochastic and deterministic components without rewriting the rest of the system**.

If calling an LLM looks completely different from calling a function, refactoring across the boundary is painful. The structure of your code fights the change.

This motivates the harness pattern:
- Stochastic and deterministic components share a calling convention
- The harness intercepts at the tool layer, enabling approvals and composition
- Call sites don't change when implementations move across the boundary

```python
# Today: LLM handles classification
result = await ctx.call("ticket_classifier", ticket_text)

# Tomorrow: hardened to Python (same call site)
result = await ctx.call("ticket_classifier", ticket_text)
```

The calling convention is unified. The implementation moved from stochastic to deterministic. The rest of the system doesn't care.

### What the harness enables

- **Progressive hardening**: Start flexible, extract determinism as patterns emerge
- **Easy extension**: Add new capability by writing a spec and registering it
- **Composition**: Stochastic and deterministic components interleave freely
- **Testing strategies**: Swap implementations for testing

### What the harness doesn't hide

Same interface doesn't mean same semantics. The caller may still need to know what kind of component they're calling for error handling, retry logic, and performance expectations. The abstraction is thin enough to enable refactoring and honest enough that you know when you're crossing the boundary.

## Testing and Debugging

Stochastic systems require different approaches.

**Testing**: Run the same input N times. Check that the distribution of outputs meets expectations. This is statistical hypothesis testing, not assertion equality. Every piece you harden becomes traditionally testable—a strong argument for progressive hardening.

**Debugging**: When a prompt "fails," you're not tracing execution—you're reshaping a probability distribution. The failure might not reproduce. Changes have non-local effects. There's no stack trace. This is why prompt engineering is empirical and iterative.

**Error taxonomy**: Stochastic systems have characteristic failure modes—hallucination, refusal, misinterpretation, drift, format violation—each suggesting different mitigations.

## Design Implications

Taking stochastic computation seriously suggests:

1. **Be explicit about distribution boundaries**—know where you're crossing between deterministic and stochastic execution

2. **Enable bidirectional refactoring**—design interfaces so components can move across the boundary without rewriting call sites

3. **Minimize distribution width where reliability matters**—use schemas, constraints, and deterministic code on critical paths

4. **Preserve distribution width where it helps**—don't over-constrain creative or ambiguous tasks

5. **Version intermediate forms**—if LLMs generate artifacts, version those alongside the specs

6. **Accept statistical failure**—design for retry and graceful degradation rather than assuming failures can be eliminated

7. **Harden progressively, soften tactically**—start stochastic where you need flexibility, harden as patterns emerge, add new capabilities via specs

---

This sketch provides the conceptual backdrop for llm-do's design. The [concept document](concept.md) explains how these ideas manifest in practice: workers as functions, unified calling conventions, the harness architecture, and the hardening/softening workflow.
