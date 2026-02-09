# RLM Implementations vs llm-do

## Context

Two open-source Recursive Language Model implementations — `ysz/recursive-llm` and
`alexzhang13/rlm-minimal` — explore how LLMs can recursively decompose tasks by
writing and executing code. We compare them with llm-do to understand where the
designs overlap and where they diverge.

A third RLM implementation, Shesha, is covered separately in `shesha-comparison.md`
(it adds a full document ingestion pipeline). Observations that apply to the RLM
family as a whole are noted here.

## The Implementations

### ysz/recursive-llm

- Repo: `https://github.com/ysz/recursive-llm`
- Single `RLM` class with `completion()` / `acompletion()` running a model-in-the-loop
  REPL until `FINAL(...)` is emitted.
- Recursion via `recursive_llm(sub_query, sub_context)` injected into the REPL; creates
  a fresh `RLM` instance at `_current_depth + 1`.
- Context stored as a Python variable, not embedded in the prompt.
- Sandboxing via RestrictedPython with whitelisted builtins. No file/network tools,
  no approval boundary.
- Per-instance depth and iteration limits; no global usage aggregation.

### alexzhang13/rlm-minimal

- Repo: `https://github.com/alexzhang13/rlm-minimal` (commit `1bed65d`)
- Intentionally stripped-down "minimal version."
- Model emits ` ```repl``` ` blocks; the system executes them and appends output back
  into the message list. `FINAL(...)` / `FINAL_VAR(...)` terminates the loop.
- Single-depth recursion by default via `llm_query` (`Sub_RLM`). Deeper nesting
  requires manual wiring.
- Execution via `exec`/`eval` with curated `__builtins__`; allows `__import__` and
  `open` — not a hard sandbox.
- OpenAI-only, GPT-5 defaults, presentation-first logging (ANSI/rich).

### What They Share

Both implementations follow the same pattern:

- **Model-driven REPL.** The LLM decides what code to write and execute; the system
  runs whatever the model emits.
- **FINAL protocol.** Explicit termination signal rather than structured tool returns.
- **Context as a variable.** Large context passed as data in the REPL namespace.
- **Pure computation.** Generated code reads data and produces answers but causes no
  side effects.
- **Ephemeral code.** Generated code is discarded after each run — every query starts
  from scratch.
- **Single concern.** Both focus on long-context exploration / recursive decomposition,
  not general agent orchestration.

## Where llm-do Diverges

The RLM implementations and llm-do both support recursive dispatch between LLM and
code, but they optimize for different things. Three differences follow from this, each
building on the previous.

### 1. Power vs. Evolvability

**RLMs optimize for power** — solve harder problems at a point in time. The LLM writes
divide-and-conquer algorithms over large contexts. An explicit boundary between LLM
calls and code calls is fine because you're not planning to move things across it.

**llm-do optimizes for evolvability** — systems that grow and mature. The core insight
is *stabilizing*: LLM applications evolve by progressively converting stochastic
behavior into deterministic code, and vice versa (see `docs/theory.md`).

```
Stochastic (prompt)  →  Deterministic (code)
         ↑                      ↓
         └── soften ←── stabilize ──┘
```

This requires a **unified calling convention** — whether a capability is implemented
as a prompt or as code must be invisible at the call site, because logic will migrate
between them as patterns emerge. Refactoring cost is everything.

Recursion in llm-do wasn't a design goal. It emerged from following software's natural
structure: functions call functions, workers call workers, and the refactoring
shouldn't stop because you hit framework limitations.

### 2. Ephemeral vs. Versioned Code

This is the most practically significant difference.

RLM-generated code is **ephemeral** — written per query, executed once, discarded.
Every run re-derives logic from scratch.

llm-do tools are **versioned infrastructure** — stored in files, checked into version
control, tested, reviewed, and reused across runs. They participate in the standard
software lifecycle:

- **Version control** — `git diff`, `git blame`, `git bisect` all work
- **Testing** — stable interfaces that can be unit-tested
- **Code review** — same review process as any other code
- **Reuse** — a tool written for one agent is available to all agents in the project
- **Debugging** — when something breaks, the code is there to read and fix

Code versioning is a solved problem with decades of tooling. Ephemeral code opts out
of all of it.

Crucially, versioned does **not** mean human-written. The LLM can generate tool code
too — via bootstrapping (LLM generates tools at runtime that graduate into permanent
infrastructure) or out-of-band (a coding assistant writes tools that get committed).
The difference is what happens *after* generation: in RLM systems the code vanishes;
in llm-do it enters the codebase and accumulates value.

```
RLM:    LLM generates code → executes → discards
llm-do: LLM generates code → executes → saves → tests → versions → reuses
```

This is the concrete mechanism behind progressive stabilization — patterns the LLM
discovers don't have to be rediscovered. They become permanent, tested, cheap-to-run
infrastructure.

### 3. Purity vs. Side Effects

The first two differences lead to a third: RLMs and llm-do operate in fundamentally
different trust regimes.

RLM-generated code is pure — it reads data and produces answers but causes no side
effects. This is what makes the approval problem disappear: if code can't cause side
effects, there's nothing to approve. The sandbox *is* the approval policy.

llm-do agents do real work — file writes, shell commands, API calls — so they need
approval gates at the trust boundary. This gives llm-do both modes when sandboxed
execution is available:

- **Pure sandbox**: LLM-generated code for computation/analysis, no approvals needed
- **Side-effectful tools**: developer-written tools for real work, approval-gated

The RLM approach only needs the first mode. llm-do needs both.

## Comparison Table

| Aspect | RLM implementations | llm-do |
|--------|---------------------|--------|
| **Priority** | Power | Evolvability |
| **Control flow** | Model-driven REPL | Code-driven orchestration |
| **Recursion** | Injected REPL function | Named workers with schemas |
| **Composition** | Implicit (code writes code) | Explicit (worker declares toolsets) |
| **Code lifespan** | Ephemeral | Versioned infrastructure |
| **Side effects** | None (pure computation) | Full (file, shell, API) |
| **Trust boundary** | Sandbox (containment) | Approval system (consent) |
| **Calling convention** | Explicit (LLM ≠ code) | Unified (LLM = code) |
| **Refactoring cost** | Pay the tax | Free (call sites don't change) |
| **State isolation** | Fresh instance per call | `CallFrame` per call |

## Open Questions

- Do we want an RLM-style REPL toolset (stateful Python exec) as a built-in or
  example? If so, should approvals gate arbitrary code execution or only
  side-effectful tools within that environment?
- Should we add a long-context exploration example that mimics `context` as a
  variable, or keep long-context handling out of scope?
- Is there value in an iterative runner that loops a worker until a FINAL-style
  termination signal, or does the standard agent loop already cover this?

## Conclusion

RLM implementations and llm-do both support true recursion — LLM calls that trigger
new LLM conversations — but from different motivations, with different consequences:

- **RLM implementations** solve specific problems (context length, recursive
  decomposition) with a clever trick: let the LLM write its own algorithms. Code is
  ephemeral — powerful in the moment, but nothing accumulates between runs.

- **llm-do** provides a framework for evolving LLM applications. Code — whether
  human-written or LLM-generated — is versioned infrastructure that participates in
  the standard software lifecycle. The unified calling convention makes refactoring
  across the stochastic-deterministic boundary cheap, so the system can breathe:
  stabilize as patterns emerge, soften when rigidity hurts.

The two key differentiators: *code that accumulates value* (versioned, tested, reused
rather than re-derived on every run) and *seamless refactoring* (a worker can become a
tool, a tool can become a worker, and call sites never change).
