# Stochastic Computation: A Sketch

> This document sketches a theoretical framing for llm-do. It's not a complete theory—just enough conceptual machinery to clarify why certain design choices make sense.

## The Gap in Existing Models

Classical models of nondeterminism and probability—nondeterministic automata, probabilistic Turing machines, probabilistic programming, Markov decision processes—treat uncertainty as a property of an otherwise well-defined machine. Probability attaches to explicit transitions or sampled variables. Execution denotes a fixed mathematical object: a language, a distribution, or an optimal policy.

Large language models don't fit this pattern. The uncertainty is not confined to modeled variables or transitions—it resides in how the specification is understood. A prompt doesn't denote a single behavior or program; it denotes a distribution over them.

Existing theories do not account for this regime. This sketch doesn't propose a full formalization—only notes that the gap exists and explores its practical consequences for system design.

## Stochastic Computers

We frame this by treating LLMs as **stochastic computers**. The key distinction from classical probabilistic models: the *program itself* is sampled, not just the execution.[^models]

[^models]: In probabilistic programming, random variables are explicit within a fixed program structure. In MDPs, the model is fixed and uncertainty lies in environment transitions. In both cases, you know what program you're running. Here, the program is what varies.

```
Traditional:     (Program, Input) → Output
Probabilistic:   (Program, Input) → sample from D(Program, Input)
Stochastic:      (Spec, Input) → sample from D(Spec, Input)
                 where D(S,I) ≈ Σ Pr[P|S] · D(P,I)
```

Technically, the stochastic case is a special case of probabilistic computation—both produce distributions over outputs. But conceptually, programmers model it differently: the output distribution *behaves as if* the spec induced a distribution over programs, each of which would handle the input differently. The LLM doesn't literally sample a program then execute it, but the mixture model captures the intuition: the interpretation varies, not just the execution path.

Each invocation samples from this distribution. The temperature parameter controls how broadly you sample. This stochasticity isn't a bug awaiting a fix—it's intrinsic to how these systems work. For many applications we want to reduce variance, but the question becomes: how do you build reliable systems on a stochastic foundation?

## What Shapes the Distribution

The "spec" isn't a single thing. Multiple factors shape the output distribution, each with different effects:

| Factor | Effect on Distribution |
|--------|----------------------|
| System prompt | Sets prior expectations, narrows toward intended behavior |
| Few-shot examples | Shifts probability mass toward demonstrated patterns |
| Tool definitions | Biases toward valid action space; can truncate support when tool-only decoding is enforced |
| Output schemas | Constrain structure and sometimes content (enums, ranges, regexes) |
| Conversation history | Dynamic reshaping as context accumulates |
| Temperature | Controls sampling breadth by flattening/sharpening the effective distribution |

Understanding these as **distribution-shaping techniques** clarifies what each intervention can and can't do. Examples shift the mode; schemas constrain the support; temperature reshapes the effective distribution at sampling time without changing model weights.

## Distribution Boundaries

When stochastic computation calls deterministic code (or vice versa), execution crosses a **distribution boundary**. Example: an LLM decides to call a calculator—that decision was sampled from a distribution, but the arithmetic itself is deterministic.

```
Stochastic → Deterministic → Stochastic
   (LLM)        (tool)         (LLM)
distribution   point mass    distribution
```

At each crossing:
- **Stochastic → Deterministic**: Variance collapses unless the tool itself is nondeterministic.
- **Deterministic → Stochastic**: Variance is introduced. A fixed input enters a system that produces a distribution over outputs.

These boundaries are natural **checkpoints**. The deterministic code doesn't care how it was reached—only what arguments it received. This matters for debugging, testing, and reasoning about the system. (Operational concerns like audit logs and approval policies may still need to track provenance, but the computation itself is context-free at the boundary.)

## Hardening and Softening

Logic can move across the distribution boundary in both directions.

**Hardening** (stochastic → deterministic): Sample from the distribution and freeze the result. The output becomes a fixed artifact—code, configuration, a decision—that no longer varies.

**Softening** (deterministic → stochastic): Replace fixed logic with a spec. Add new functionality by describing it in natural language; the LLM figures out how to do it.

```
Harden                              Soften
   ↓                                   ↓
Stochastic ◄─────────────────────► Deterministic
(flexible,                          (reliable,
 handles ambiguity)                  testable, cheap)
```

### One-shot hardening (stochastic compilation)

LLMs can act as compilers: spec in, code out. Each run samples from the distribution, producing a different but (hopefully) valid implementation.

```
spec → LLM → code → executor → result
       ↑
       samples from distribution
```

This is hardening in one step: a stochastic spec becomes deterministic code. But unlike traditional compilation, regeneration gives you a *different sample*, not the same code.

**Versioning implication**: Both spec and generated code are distinct artifacts that should be versioned. If you keep only the spec, reproducing what you deployed is practically impossible.[^repro] If you keep only the code, you lose the intent that generated it.

[^repro]: Theoretical reproducibility requires pinning model version, decoding parameters, RNG seeds, and more. In practice, this is rarely done.

### Progressive hardening

Rather than generating code in one shot, you can harden incrementally:

1. Start with a stochastic component (a worker/agent)
2. Run it, observe patterns in its behavior
3. Extract stable patterns to deterministic code
4. Keep the stochastic component for remaining ambiguous cases

Example: a file-renaming agent initially uses LLM judgment for everything. You notice it always lowercases and replaces spaces with underscores—so you extract `sanitize_filename()` to Python. The agent still handles ambiguous cases ("is '2024-03' a date or a version?"), but the common path is now code.

### Softening as extension

The common path for softening is **extension**: you need new capability, you describe it in natural language, and it becomes callable. You can write a spec, or even just user stories, and plug it into the system. An LLM can combine user stories into a coherent spec. (The new capability is still bounded by available tools and permissions—natural language doesn't conjure abilities the system lacks.)

The rarer path is **replacement**: rigid code is drowning in edge cases, so you swap it for an LLM call that handles linguistic variation.

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

**Testing**: Run the same input N times. Check that the distribution of outputs meets expectations. This is statistical hypothesis testing, not assertion equality. (Caching and model updates can break i.i.d. assumptions, so treat results with appropriate caution.) Every piece you harden becomes traditionally testable—a strong argument for progressive hardening.

**Debugging**: When a prompt "fails," you're not tracing execution—you're reshaping a probability distribution. The failure might not reproduce. Changes have non-local effects. There's no stack trace. This is why prompt engineering is empirical and iterative.

**Error taxonomy**: Stochastic systems have characteristic failure modes—hallucination, refusal, misinterpretation, drift, format violation—each suggesting different mitigations.

## Design Implications

Taking stochastic computation seriously suggests:

1. **Be explicit about distribution boundaries**—know where you're crossing between deterministic and stochastic execution

2. **Enable bidirectional refactoring**—design interfaces so components can move across the boundary without rewriting call sites

3. **Minimize distribution width where reliability matters**—use schemas, constraints, and deterministic code on critical paths

4. **Preserve distribution width where it helps**—don't over-constrain creative or ambiguous tasks

5. **Version intermediate forms**—when you harden (one-shot or progressive), both the spec and the frozen artifact matter

6. **Accept statistical failure**—design for retry and graceful degradation rather than assuming failures can be eliminated

7. **Harden progressively, soften tactically**—start stochastic where you need flexibility, harden as patterns emerge, add new capabilities via specs

---

This sketch provides the conceptual backdrop for llm-do's design. The [concept document](concept.md) explains how these ideas manifest in practice: workers as functions, unified calling conventions, the harness architecture, and the hardening/softening workflow.
