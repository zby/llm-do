# Interpreting Fuzzy Specifications

> This document sketches a theoretical framing for llm-do. Not a complete theory—just enough conceptual machinery to clarify why certain design choices make sense.

## LLMs as Virtual Machines

An LLM can be viewed as a virtual machine. Give it a sufficiently detailed specification, and it interprets that spec into behavior. This is more than metaphor—projects like [OpenProse](https://github.com/openprose/prose) treat the LLM explicitly as an interpreter: "A long-running AI session is a Turing-complete computer."

The key insight: **simulation with sufficient fidelity is implementation.** When an LLM receives a detailed VM specification, it *becomes* that VM through simulation. The interpreter runs inside the session.

This pure LLM VM approach has limitations:
- Every operation costs tokens (expensive at scale)
- Every step requires API round-trip (high latency)
- Specifications are in natural language (fuzzy semantics, no precise denotation)
- Execution is indeterministic (sampling noise on top of semantic fuzziness)

**llm-do takes the next step: a hybrid VM** that unifies LLM execution (neural) and Python execution (symbolic) under a single calling convention. The VM can dispatch to either; callers don't need to know which. This enables moving computation between neural and symbolic as systems evolve—stabilise patterns to code when they emerge, soften rigid code back to LLM when edge cases multiply.

## Two Distinct Phenomena

LLM-based systems differ from traditional programs in two ways that are often conflated but are conceptually distinct:

**1. Execution indeterminism.** The same prompt can produce different outputs across runs due to sampling (temperature > 0). This is a property of the execution engine—conceptually simpler than semantic fuzziness, and theoretically eliminable (temperature=0), though in practice all deployed systems exhibit it and often benefit from it.

**2. Semantic fuzziness.** Natural language specifications don't have precise denotations. "Refactor for readability" doesn't pick out a unique transformation—it admits a *space* of valid interpretations. This is a property of the specification language itself, not the engine. Even a perfectly deterministic LLM would still face the problem that the spec doesn't uniquely determine the output.

These two phenomena are not entirely orthogonal—indeterminism is the mechanism by which different interpretations get surfaced across runs—but they are fundamentally different in kind. The first is engineering; the second is semantics.

### Indeterminism obscures the real difference

Counterintuitively, indeterminism *hides* the deeper issue rather than revealing it. Because outputs vary across runs, people attribute the variation to randomness—"it's stochastic"—and reach for familiar tools: temperature tuning, retries, sampling strategies. This provides a comfortable framework that avoids confronting the real difference from traditional programming.

If LLMs were deterministic, you'd get one stable output for "refactor for readability"—but you'd have to ask: *why this interpretation and not any of the other equally valid ones?* That question forces you to see that the specification language doesn't have the same semantics as a formal programming language. The indeterminism lets you avoid that question by explaining everything as noise.

## Probabilistic Programming as Practical Model

Both phenomena—fuzzy semantics and execution indeterminism—are captured by a single framework: probabilistic programming. LLM-based agentic systems interleave deterministic computation with components that interpret fuzzy natural-language specs:

```python
x = llm_call(prompt)        # fuzzy semantics + indeterminism
y = f(x)                    # deterministic
z = llm_call(prompt2(y))    # fuzzy semantics + indeterminism
```

The LLM components have two sources of variation—the semantic fuzziness of natural language specs and the execution indeterminism of the engine—while traditional code has neither. The combined distribution is too complex to characterize directly, so we reason about it through simpler mental models.

## A Useful Mental Model: "Program Sampling"

Programmers often reason about LLMs as if they sample a *program* (or interpretation) from the specification, then execute it:

```
Spec → sample interpretation → execute on input → output
```

This model captures the **semantic fuzziness** phenomenon directly: the spec admits multiple valid programs, and the LLM picks one. It's fundamentally about the spec-to-program mapping being one-to-many—a semantic property, not a probabilistic one. (With indeterminism, different runs may pick different ones; without it, the LLM picks the same one consistently—but the one-to-many mapping remains.)

This makes LLMs fundamentally different from compilers. A traditional compiler performs a semantic-preserving transformation—a homeomorphism between representations where the meaning is invariant. An LLM performs a *projection*: a natural-language spec admits a space of valid interpretations, and the LLM collapses that space to one concrete program. Even a deterministic LLM would do this—it would just always pick the same interpretation, with no principled way for the user to predict which one from the spec alone.

Mathematically, this projection is a mixture model:

```
D(Output | Spec, Input) ≈ Σ Pr[Program | Spec] · D(Output | Program, Input)
```

The mixture over programs captures the semantic fuzziness—multiple valid interpretations of the spec. The `D(Output | Program, Input)` term captures execution indeterminism—variation within a single interpretation. Both are present in practice, but the program-sampling model highlights that the more interesting variation comes from the first source.

### Example: "Refactor for Readability"

Ask an LLM coding assistant to refactor a function for readability. Valid interpretations include:

- Extract helper functions
- Rename variables for clarity
- Restructure control flow (loops → comprehensions)
- Add comments explaining intent

These aren't noisy variations of *one* strategy—they're different *interpretations* of "readability." The spec doesn't pick out a unique transformation; the space of valid refactoring approaches is genuinely plural. A deterministic LLM would still have to choose one—but you couldn't predict which from the spec alone, and you'd have no basis to say it chose wrong.

We don't claim this is how LLMs actually work internally. But as a mental model for reasoning about the semantic gap between natural language specs and concrete behavior, it's useful: prompt engineering becomes about narrowing the space of valid interpretations, not debugging a fixed program.

## Narrowing the Interpretation Space

In probabilistic programming, you shape distributions through priors, conditioning, and constraints. With LLMs, you use different mechanisms—but the goal is the same: **narrowing the space of interpretations the LLM might choose**.

| Mechanism | Effect |
|-----------|--------|
| System prompt | Sets prior expectations, narrows toward intended behavior |
| Few-shot examples | Shifts probability mass toward demonstrated patterns |
| Tool definitions | Biases toward valid actions; can truncate support when tool-only decoding is enforced |
| Output schemas | Constrain structure and sometimes content (enums, ranges, regexes) |
| Conversation history | Dynamic reshaping as context accumulates |
| Temperature | Flattens or sharpens the distribution at sampling time |

Understanding these as **distribution-shaping techniques** clarifies what each can and can't do—and which phenomenon each addresses. Temperature operates on execution indeterminism only; it sharpens or flattens the sampling without changing what the spec means. Examples and detailed instructions operate on semantic fuzziness; they narrow the space of valid interpretations. Schemas and tool definitions do both: they constrain structure (reducing indeterminism) and sometimes eliminate entire classes of interpretation (reducing fuzziness). But none eliminate the ambiguity entirely—natural language specs remain fuzzy even under maximum constraint.

## Semantic Boundaries

Agentic systems interleave components with fuzzy semantics (LLM) and precise semantics (code). When an LLM calls a tool, or a tool triggers an LLM, execution crosses a **semantic boundary**.

```
Fuzzy semantics → Precise semantics → Fuzzy semantics
     (LLM)             (tool)              (LLM)
 interpretation      exact function      interpretation
```

At each crossing:
- **Fuzzy → Precise**: The LLM's interpretation is consumed by code that treats it as a concrete value. The code doesn't know or care that the input could have been different under a different interpretation of the spec.
- **Precise → Fuzzy**: A concrete value enters a component that interprets a natural-language spec to decide what to do with it. The spec doesn't uniquely determine the behavior; the LLM resolves the ambiguity.

These boundaries are natural **checkpoints**. The deterministic code doesn't care how it was reached—only what arguments it received. This matters for debugging, testing, and reasoning about the system.

But boundaries aren't fixed. As systems evolve, logic moves across them.

## Stabilising and Softening

Components exist on a spectrum from fuzzy semantics (natural language, LLM-interpreted) to precise semantics (formal language, deterministic code). Logic can move in both directions.

**Stabilising**: Replace an LLM component with a deterministic one. This does two things simultaneously: it **resolves semantic fuzziness** by choosing one interpretation from the space the spec admits and committing to it in a language with precise semantics, and it **removes execution indeterminism** by eliminating sampling noise. Both matter in practice, but the semantic commitment is the deeper operation.

**Softening**: Replace a deterministic component with an LLM-interpreted one. Describe new functionality in natural language; the LLM figures out how to do it.

```
Fuzzy (flexible, handles ambiguity)  ——stabilise——>  Precise (reliable, testable, cheap)
Fuzzy (flexible, handles ambiguity)  <——soften———  Precise (reliable, testable, cheap)
```

### Why stabilise?

Stabilising a pattern to code has three practical benefits:

**Cost.** LLM API calls are priced per token. A simple operation like sanitising a filename might cost fractions of a cent, but at scale those fractions compound. The same operation in code costs effectively nothing.

**Latency.** Every LLM call involves network round-trip plus inference time. Even fast models add hundreds of milliseconds. Code executes in microseconds.

**Reliability.** Deterministic code returns the same output for the same input, every time. No hallucination, no refusal, no drift across model versions.

The tradeoff: code requires you to commit to one precise interpretation. LLMs let you specify *intent* in fuzzy natural language and defer the choice of interpretation to runtime. That's why stabilising is progressive—you wait until patterns emerge before committing to a specific semantics.

### One-shot vs progressive stabilising

LLMs can act as compilers: spec in, code out. But as the program-sampling model makes clear, this is projection from a fuzzy spec, not compilation—the LLM resolves the semantic ambiguity, producing one valid implementation from the space the spec admits, with no way to predict which one from the spec alone. This is one-shot stabilising: freeze a single resolution into code.

Alternatively, you can stabilise incrementally. As you observe the LLM's behavior across many runs, you learn which interpretations it consistently chooses—and can extract those stable patterns into deterministic code while keeping the LLM for genuinely ambiguous cases.

Example: a file-renaming agent initially uses LLM judgment for everything. You notice it always lowercases and replaces spaces with underscores—so you extract `sanitize_filename()` to code. The agent still handles ambiguous cases ("is '2024-03' a date or a version?"), but the common path is now deterministic.

Either way, **version both spec and artifact**. Regeneration is a new projection from the same spec—potentially a different resolution of the same ambiguity, not a deterministic rebuild. Don't treat "re-generate later" as a build step.

For the gradient of stabilisation techniques — from prompt restructuring through evals to deterministic modules — see [Crystallisation](../kb/notes/crystallisation.md).

### Softening as extension

The common path for softening is **extension**: you need new capability, describe it in natural language, and it becomes callable. The rarer path is **replacement**: rigid code is drowning in edge cases, so you swap it for an LLM call that handles linguistic variation.

Real systems need both directions. A component might start as an LLM call (quick to add), stabilise to code as patterns emerge (reliable and fast), then grow new capabilities via softening. The system breathes.

## The Hybrid VM

The hybrid VM unifies neural (LLM) and symbolic (Python) execution **at the tool layer the LLM sees**. This unified calling convention is what enables bidirectional refactoring between components with fuzzy and precise semantics.

### Why unified calling matters

If an LLM call looks completely different from a tool call, refactoring across the semantic boundary is painful. Prompt structure fights the change.

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

The LLM-facing calling convention is unified. The implementation moved from fuzzy to precise semantics; prompts don't change.

For more on this design, see [Unified calling conventions enable bidirectional refactoring](../kb/notes/unified-calling-conventions-enable-bidirectional-refactoring.md).

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
- **Composition**: Components with fuzzy and precise semantics interleave freely
- **Testing strategies**: Swap implementations for testing
- **Auditability**: Tool-level logging and inspection

The harness is llm-do's specific implementation choice. The hybrid VM concept stands independently—other systems could build different orchestration layers on the same interception points.

## Testing and Debugging

LLM components require different approaches, and the two phenomena create different challenges.

**Testing**: Execution indeterminism means you run the same input N times and check the distribution of outputs—statistical hypothesis testing, not assertion equality. Semantic fuzziness means you also need to verify that the space of valid interpretations is acceptable, not just that individual outputs look right. Every piece you stabilise becomes traditionally testable—because you've committed to one interpretation in a precise language.

**Debugging**: When a prompt "fails," you need to distinguish between the two phenomena. Is the LLM producing a bad execution of a good interpretation (indeterminism problem—may not reproduce)? Or is it consistently choosing an interpretation you didn't intend (fuzziness problem—the spec admits it, so it will recur)? The fix is different: retry vs. rewrite the spec.

## Design Implications

Treating agentic systems as interpreters of fuzzy specifications suggests:

1. **Be explicit about semantic boundaries**—know where you're crossing between precise and fuzzy semantics
2. **Enable bidirectional refactoring**—design interfaces so components can move across the boundary without rewriting call sites
3. **Narrow interpretations where reliability matters**—use schemas, constraints, and deterministic code on critical paths
4. **Preserve ambiguity where it helps**—don't over-constrain creative or genuinely open-ended tasks
5. **Version both spec and artifact**—regeneration is a new projection, not a deterministic rebuild
6. **Design for unpredictable interpretation**—the LLM may resolve ambiguity differently than you expect
7. **Stabilise progressively, soften tactically**—start with fuzzy specs for flexibility, commit to precise semantics as patterns emerge

## Tradeoffs

**llm-do is a good fit when:**
- You want normal Python control flow (branching, loops, retries)
- You're prototyping and will stabilise as patterns emerge
- You need tool-level auditability and approvals
- You want flexibility to refactor between LLM and code

**It may be a poor fit when:**
- You need durable workflows with checkpointing/replay
- Graph visualization is your primary interface
- You need distributed orchestration out of the box

llm-do can be a component *within* durable workflow systems (Temporal, Prefect), but doesn't replace them.

---

See also: [architecture](architecture.md) for internal structure, [reference](reference.md) for API.
