# Interpreting Underspecified Instructions

> A theoretical framing for llm-do. Not a complete theory — just enough conceptual machinery to clarify why certain design choices make sense.

## Two Distinct Phenomena

LLM-based systems differ from traditional programs in two ways that are often conflated but are conceptually distinct:

**1. Semantic underspecification.** Natural language specifications don't have precise denotations. "Write a summary" admits a *space* of valid interpretations — different lengths, emphases, structures. This is a property of the specification language itself, not the engine.

**2. Execution indeterminism.** The same prompt can produce different outputs across runs due to sampling (temperature > 0). This is a property of the execution engine — conceptually simpler than semantic underspecification, and largely eliminable via temperature=0, though implementation details (floating-point non-determinism, batching, infrastructure changes) mean true determinism is hard to guarantee in practice. All deployed systems exhibit indeterminism and often benefit from it.

The two are not entirely orthogonal — indeterminism is the mechanism by which different interpretations get surfaced across runs — but they are fundamentally different in kind. The first is semantics; the second is engineering.

### Indeterminism obscures the real difference

Counterintuitively, indeterminism *hides* the deeper issue rather than revealing it. Because outputs vary across runs, people attribute the variation to randomness — "it's stochastic" — and reach for familiar tools: temperature tuning, retries, sampling strategies. This provides a comfortable framework that avoids confronting the real difference from traditional programming.

If LLMs were deterministic, you'd get one stable output for a given prompt — but you'd have to ask: *why this interpretation and not any of the other equally valid ones?* That question forces you to see that the specification language doesn't have the same semantics as a formal programming language. The indeterminism lets you avoid that question by explaining everything as noise.

## Spec-to-Program Projection

A natural-language spec admits multiple valid programs. The LLM picks one:

```
Spec → choose interpretation → execute on input → output
```

The spec-to-program mapping is one-to-many — a semantic property, not a probabilistic one. Even a deterministic LLM would face it: it would always pick the same interpretation, but the user couldn't predict which one from the spec alone.

This makes LLMs different from compilers. A compiler performs a semantics-preserving translation — the source and target represent the same program, just in different languages. An LLM performs a *projection*: it collapses a space of valid interpretations to one concrete program.

The two phenomena layer on top of each other: the projection picks an interpretation (semantic underspecification), then execution of that interpretation may vary across runs (indeterminism). But the more interesting variation comes from the first source — qualitatively different strategies, not noisy executions of the same one.

### Example: "Refactor for Readability"

Ask an LLM coding assistant to refactor a function for readability. Valid interpretations include:

- Extract helper functions
- Rename variables for clarity
- Restructure control flow (loops → comprehensions)
- Add comments explaining intent

These aren't noisy variations of *one* strategy — they're different *interpretations* of "readability." The spec doesn't pick out a unique transformation; the space of valid approaches is genuinely plural.

This reframes prompt engineering: it's about narrowing the space of valid interpretations, not debugging a fixed program.

## Narrowing the Interpretation Space

The usual tools: system prompts, few-shot examples, tool definitions, output schemas, conversation history, temperature. In practice it's hard to determine which phenomenon a given mechanism addresses — a more detailed system prompt might narrow the interpretation space, or it might just make one interpretation more likely without eliminating the others. The line between "disambiguating the spec" and "biasing the engine" is rarely clean.

Temperature is often cited as purely an indeterminism control, but it's subtler than that. Lowering temperature concentrates the sampling distribution — which can change *which interpretation* you see, not just how noisily you see it. At temperature=0 the LLM still picks one interpretation from the space the spec admits; you just get the same one every time. This is why lowering temperature alone doesn't solve the "wrong interpretation" problem — it eliminates variation without ensuring the remaining interpretation is the one you wanted.

None of these eliminate ambiguity entirely. Natural language specs remain underspecified even under maximum constraint. So real systems don't just manage underspecification within LLM components — they manage the transitions between LLM and code.

## Boundaries

Agentic systems interleave LLM components and code. When an LLM calls a tool, or a tool triggers an LLM, execution crosses a boundary where both phenomena change simultaneously:

```
       LLM           →        Tool          →        LLM
underspecified + indeterministic   precise + deterministic   underspecified + indeterministic
```

At each crossing:
- **LLM → Code**: Semantic underspecification resolves — the code treats the LLM's output as a concrete value, regardless of what other interpretations were possible. Indeterminism collapses — given the same arguments, the code returns the same result.
- **Code → LLM**: Both are reintroduced. A concrete value enters a component that interprets a natural-language spec to decide what to do with it. The spec doesn't uniquely determine the behavior, and sampling adds further variation.

The two phenomena are conceptually distinct but travel together in practice: LLM components have both, code has neither. This is why these boundaries are natural **checkpoints** — the deterministic code doesn't care how it was reached, only what arguments it received. This matters for debugging, testing, and reasoning about the system.

But boundaries aren't fixed. As systems evolve, logic moves across them.

## Stabilising and Softening

Components exist on a spectrum from underspecified semantics (natural language, LLM-interpreted) to precise semantics (formal language, deterministic code). Logic can move in both directions.

**Stabilising**: Replace an LLM component with a deterministic one. This does two things simultaneously: it **resolves semantic underspecification** by choosing one interpretation from the space the spec admits and committing to it in a language with precise semantics, and it **removes execution indeterminism** by eliminating sampling noise. Both matter in practice, but the semantic commitment is the deeper operation.

**Softening**: Replace a deterministic component with an LLM-interpreted one. Describe new functionality in natural language; the LLM figures out how to do it.

```
Underspecified (flexible, handles ambiguity)  ——stabilise——>  Precise (reliable, testable, cheap)
Underspecified (flexible, handles ambiguity)  <——soften———  Precise (reliable, testable, cheap)
```

### Why stabilise?

Stabilising a pattern to code has three practical benefits:

**Cost.** LLM API calls are priced per token. A simple operation like sanitising a filename might cost fractions of a cent, but at scale those fractions compound. The same operation in code costs effectively nothing.

**Latency.** Every LLM call involves network round-trip plus inference time. Even fast models add hundreds of milliseconds. Code executes in microseconds.

**Reliability.** Deterministic code returns the same output for the same input, every time. No hallucination, no refusal, no silent behavior changes when the underlying model is updated.

The tradeoff: code requires you to commit to one precise interpretation. LLMs let you specify *intent* in natural language and defer the choice of interpretation to runtime. That's why stabilising is progressive — you wait until patterns emerge before committing to a specific semantics.

### One-shot vs progressive stabilising

LLMs can generate code from a spec: spec in, code out. But this is projection, not compilation — the LLM resolves the semantic ambiguity, producing one valid implementation from the space the spec admits. This is one-shot stabilising: freeze a single projection into code.

Alternatively, you can stabilise incrementally. As you observe the LLM's behavior across many runs, you learn which interpretations it consistently favours — and can extract those stable patterns into deterministic code while keeping the LLM for genuinely ambiguous cases.

Example: a file-renaming agent initially uses LLM judgment for everything. You notice it always lowercases and replaces spaces with underscores — so you extract `sanitize_filename()` to code. The agent still handles ambiguous cases ("is '2024-03' a date or a version?"), but the common path is now deterministic.

Either way, **version both spec and artifact**. Regeneration is a new projection from the same spec — potentially a different resolution of the same ambiguity, not a deterministic rebuild. Don't treat "re-generate later" as a build step.

For the gradient of stabilisation techniques — from prompt restructuring through evals to deterministic modules — see [Deploy-time learning: the missing middle](https://github.com/zby/commonplace/blob/main/kb/notes/deploy-time-learning-the-missing-middle.md).

### Softening as extension

The common path for softening is **extension**: you need new capability, describe it in natural language, and it becomes callable. The rarer path is **replacement**: rigid code is drowning in edge cases, so you swap it for an LLM call that handles linguistic variation.

Real systems need both directions. A component might start as an LLM call (quick to add), stabilise to code as patterns emerge (reliable and fast), then grow new capabilities via softening. The system breathes.

## The Hybrid VM

The concepts above — boundaries, stabilising, softening — are general. llm-do's specific contribution is a **hybrid VM** that makes the boundary between underspecified and precise semantics easy to cross.

The hybrid VM unifies LLM execution (neural) and Python execution (symbolic) under a single calling convention at the tool layer the LLM sees. The VM can dispatch to either; callers don't need to know which.

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

The LLM-facing calling convention is unified. The implementation moved from underspecified to precise semantics; prompts don't change.

For more on this design, see [Unified calling conventions enable bidirectional refactoring](../kb/notes/unified-calling-conventions-enable-bidirectional-refactoring.md).

### Name-based dispatch

Unified calling requires **name-based dispatch**: components are identified by string name rather than direct object reference.

Why names?

- **Dynamic resolution.** When an LLM decides to call another component, it outputs a string. You need name-based lookup to resolve that string to an implementation.
- **Late binding.** The called component doesn't need to exist when the caller is defined.
- **Implementation-agnostic interfaces.** A name like `ticket_classifier` can resolve to an agent today and a Python function tomorrow.

Direct reference couples caller to implementation. Name-based dispatch keeps the interface stable while implementations change.

## The Harness

On top of the hybrid VM, llm-do adds a **harness** — an orchestration layer that intercepts operations, manages approvals, and controls execution flow.

The VM enables the harness by providing interception points. Name-based dispatch means every call goes through a lookup layer that can wrap, modify, or gate the invocation. The VM provides the machinery; the harness uses it to implement policies.

The harness enables:
- **Approval workflows**: Human-in-the-loop for sensitive operations
- **Composition**: Components with underspecified and precise semantics interleave freely
- **Testing strategies**: Swap implementations for testing
- **Auditability**: Tool-level logging and inspection

The harness is llm-do's specific implementation choice. The hybrid VM concept stands independently — other systems could build different orchestration layers on the same interception points.

## Testing and Debugging

The two phenomena create different challenges for testing and debugging.

**Testing**: Execution indeterminism means you can't rely on assertion equality for LLM outputs — you need to run the same input multiple times and check that outputs fall within acceptable bounds. In practice this looks more like sampling and checking invariants than formal hypothesis testing, but the principle holds: you're characterising a distribution, not verifying a point. Semantic underspecification means you also need to verify that the space of valid interpretations is acceptable, not just that individual outputs look right. Every piece you stabilise becomes traditionally testable — because you've committed to one interpretation in a precise language.

**Debugging**: When a prompt "fails," the first question is which phenomenon is responsible. Is the LLM producing a bad execution of a good interpretation (indeterminism problem — may not reproduce)? Or is it consistently choosing an interpretation you didn't intend (underspecification problem — the spec admits it, so it will recur)? The fix is different: retry vs. rewrite the spec.

## Design Implications

Treating agentic systems as interpreters of underspecified instructions suggests:

1. **Be explicit about semantic boundaries** — know where you're crossing between precise and underspecified semantics
2. **Enable bidirectional refactoring** — design interfaces so components can move across the boundary without rewriting call sites
3. **Narrow interpretations where reliability matters** — use schemas, constraints, and deterministic code on critical paths
4. **Preserve ambiguity where it helps** — don't over-constrain creative or genuinely open-ended tasks
5. **Version both spec and artifact** — regeneration is a new projection, not a deterministic rebuild
6. **Design for unpredictable interpretation** — the LLM may resolve ambiguity differently than you expect
7. **Stabilise progressively, soften tactically** — start underspecified for flexibility, commit to precise semantics as patterns emerge

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
