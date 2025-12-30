According to a document from **2025-11-18** (the AICL paper), the core thing to implement is a **two-loop harness** where the LLM only updates a **semantic state + proposed semantic action**, and **deterministic code** (1) probes that state for gaps/contradictions, (2) executes the action safely, and (3) applies a **relaxation ladder** when progress stalls. 

Below is a concrete implementation plan for adding this capability to **llm-do** in a way that matches llm-do’s own framing: *distribution boundaries*, *harness-not-graph*, and *progressive hardening*.

---

## 1) Target outcome

### What we will ship

A reusable **AICL runner** inside `llm-do` that lets you wrap any “worker” (LLM) with:

* a **State Manager** (typed semantic state + persistence)
* a deterministic **Probe Evaluator** `gθ(state)` returning diagnostics
* a deterministic **Action Mapper** that translates “semantic actions” into `ctx.call()` (workers/tools) with llm-do approvals still applying
* a **Relaxation Ladder** (progressively weaker constraints) when `NOPROGRESS(state, new_state)`
* a full **iteration trace** for debugging & tests

This is exactly the modular boundary AICL argues for: the LLM does semantic updates, while determinism handles evaluation/execution. 

### Why this fits llm-do

llm-do explicitly frames reliability as “make things deterministic at key spots”, provides a unified calling convention, and treats tool calls as interceptable syscalls/approvals. AICL is basically a “first-class pattern” for choosing those key deterministic spots: probes + action mapping + relaxation.

---

## 2) Architectural mapping: AICL → llm-do

### AICL components

AICL’s loop and components are described in the paper as:

* **LLM reasoning**: `(s_{t+1}, a_{t+1}) = fLLM(s_t, …)` (semantic-only)
* **Deterministic probe**: `p_t = gθ(s_t)` checks completeness/contradictions/evidence/schema
* **Relaxation ladder**: descend when no progress
* **Deterministic action mapping**: executes “query/retrieve/refine/…” as concrete operations

### llm-do equivalents

* **Semantic state**: a Pydantic model (or JSON dict) carried across iterations
* **Probe**: pure Python function(s) that inspect the state and emit a structured `ProbeResult`
* **Planner**: a normal llm-do worker (“planner worker”) that receives `(state, probe, constraints)` and returns `(new_state, semantic_action)`
* **Action mapper**: deterministic Python that maps semantic actions into:

  * `ctx.call("some_worker", …)` or
  * calling a registered Python tool
    approvals still apply because mapping ultimately uses the same tool layer interception llm-do already emphasizes.

---

## 3) Phase plan (incremental, shippable at every step)

### Phase A — Define core interfaces & schemas (make it hard to misuse)

**Deliverables**

1. `SemanticState` schema(s)
2. `ProbeResult` schema
3. `SemanticAction` schema
4. `ConstraintLevel` / `RelaxationLevel` schema

**Suggested minimum models**

* `SemanticState` (generic, then specialized per domain):

  * `goal`
  * `hypotheses[]`
  * `evidence[]` (each evidence item has source/quote/structured fields)
  * `open_questions[]`
  * `plan` (optional)
  * `last_actions[]` (for idempotence detection)
* `ProbeResult`:

  * `missing_fields[]`
  * `contradictions[]`
  * `evidence_score` / `evidence_gaps[]`
  * `schema_violations[]`
  * `uncertainty_score` (optional)
    This aligns directly with AICL’s Algorithm 2 probe outputs.
* `SemanticAction`:

  * `type` enum: `query | retrieve | refine | delegate | noop | finalize`
  * `payload` (typed per action)
    AICL explicitly calls out deterministic action mapping as a module. 
* `ConstraintLevel`:

  * `required_fields`
  * `allowed_action_types`
  * `max_steps_this_level`
  * optional: `prompt_addendum` (small instruction block for planner)

**Acceptance checks**

* You can serialize/deserialize state deterministically
* ProbeResult is stable for identical inputs (unit-testable)

---

### Phase B — Implement the deterministic core: probe, progress, ladder, action mapper

**Deliverables**

1. `probe_fn(state) -> ProbeResult` (pluggable)
2. `converged(state, probe) -> bool`
3. `no_progress(prev_state, next_state) -> bool`
4. `RelaxationLadder` class
5. `ActionMapper` with safety & idempotence

**Key details to get right**

* **Deterministic probe** must be reproducible and unit-testable (this is one of AICL’s main engineering claims).
* **No-progress detection**

  * Canonicalize state (e.g., stable JSON dump with sorted keys)
  * Define “progress” as: fewer missing fields OR higher evidence score OR reduced contradictions OR changed hypothesis set
* **Idempotent action detection**

  * Keep a rolling hash of `(action.type, payload)` plus a hash of pre/post state
  * If the same action repeats without meaningful state delta, treat as `NOPROGRESS` and descend ladder
    This is explicitly called out as preventing infinite-loop behavior in the AICL evaluation writeup.
* **Action mapper safety**

  * Whitelist allowed `ctx.call()` targets per constraint level
  * Enforce budgets: max tool calls, max iterations, max “expensive” calls
  * Let llm-do approvals still act as a syscall gate for risky tools (don’t bypass it).

**Acceptance checks**

* Full deterministic unit test suite for:

  * probe completeness checks
  * contradiction detection (even if simplistic at first)
  * ladder descent logic
  * idempotence detection

---

### Phase C — Build the AICL runner (the orchestration loop)

**Deliverables**

* `AICLRunner.run(initial_state, observations, planner_worker, probe_fn, ladder, action_mapper, budgets) -> final_state`
* structured trace output per iteration:

  * state summary hash
  * probe result
  * ladder level
  * action proposed + action executed
  * progress / convergence decision

This is essentially AICL Algorithm 1: probe → planner update → execute → ladder if no progress.

**Important: keep it “harness-y”**
In llm-do terms, this runner should be “just Python control flow” that calls workers/tools through the unified call interface, so we preserve *harness not graph* and *call sites stay the same when implementations harden*.

---

### Phase D — Implement the planner worker (LLM reasoning layer)

**Deliverables**

* A worker (e.g. `aicl_planner.worker`) that:

  * takes `(state, probe, constraints)`
  * returns `(next_state, semantic_action)`
  * never directly executes tools; it only proposes actions

This enforces AICL’s “separation of reasoning and execution.”

**Prompt/contract requirements**

* Output must validate against the Pydantic schema (hard failure if not)
* Must incorporate probe feedback:

  * fill missing fields first
  * resolve contradictions explicitly
  * when evidence is insufficient, propose `query/retrieve` actions
* Must respect `constraints.allowed_action_types`
* Must prefer `noop/finalize` when probe says complete and stable

**Acceptance checks**

* The worker can operate with `temperature=0` (or low) for stability where desired (paper notes temp=0 in evaluation). 

---

### Phase E — Pilot on an existing llm-do example and harden it

Pick one of llm-do’s canonical “progressive hardening” example chains (the pitchdeck progression is already documented).

**Pilot deliverables**

* New example: `examples/pitchdeck_eval_aicl/` (or similar)
* Domain-specific:

  * `PitchdeckState`
  * `pitchdeck_probe(state)` that checks:

    * all rubric sections present
    * scores in range
    * evidence snippets quoted for each score
    * contradictions (e.g., “market is huge” vs “market is tiny”)
  * ladder levels like:

    1. strict: all sections + evidence required
    2. relax: allow missing 1–2 low-priority sections but keep evidence for top risks
    3. relax: produce only top-3 findings + recommended next actions
       (This matches AICL’s “progressively simplified reasoning mode” ladder idea.)

**Why this is a good pilot**

* Easy to write deterministic probes (schema completeness and ranges are straightforward)
* Action mapping is simple: list decks, load deck text, call analysis worker, compile report
* You get a visible win: fewer “loop forever / wander” behaviors, more stable outputs

---

### Phase F — Testing strategy (make AICL pay off)

AICL’s big promise is: “unit tests should target probe logic rather than the LLM.”
This aligns perfectly with llm-do’s view that deterministic components become traditionally testable and that stochastic parts need statistical/invariant-based testing.

**Deliverables**

1. Unit tests:

   * probe checks (pure deterministic)
   * ladder descent
   * idempotence / no-progress
   * action mapper whitelisting
2. “Contract tests” for planner output schema:

   * validate that planner output always parses
3. Lightweight stochastic tests:

   * run N times and assert invariants (no missing required fields at convergence, no forbidden actions executed)

---

### Phase G — Observability & artifacts (debuggability by default)

AICL emphasizes traceability: semantic states + probe outputs + ladder steps form a reasoning trace.

**Deliverables**

* Structured JSON trace per run (write to `./runs/<id>/trace.jsonl`)
* Optional “pretty” markdown summary for humans
* Include hashes for:

  * state snapshots
  * executed actions
  * probe outputs
    So that regressions are detectable even when LLM outputs vary.

---

## 4) Minimal file/module structure to add to llm-do

Even without touching the rest of the system, you can add:

* `llm_do/aicl/`

  * `models.py` (State / Probe / Action / Constraint schemas)
  * `probe.py` (probe framework + default checks)
  * `ladder.py` (RelaxationLadder)
  * `mapper.py` (ActionMapper)
  * `runner.py` (AICLRunner)
  * `trace.py` (trace event types + writers)

* `examples/.../` for the pilot

* `tests/test_aicl_*.py` focused mostly on deterministic pieces

This keeps llm-do’s core promise intact: the harness lets you swap stochastic vs deterministic without rewriting call sites.

---

## 5) Definition of Done

You’ll know the implementation is “real” when all of this is true:

1. **Deterministic probes are unit-tested** and stable (same input → same probe output).
2. The **planner worker cannot execute side effects directly** (only proposes semantic actions). 
3. The runner **converges or relaxes monotonically** (never infinite-loops on identical actions).
4. All execution still flows through llm-do’s **tool interception / approvals**, preserving the syscall-like control plane.
5. A pilot example shows reduced “wandering” behavior and produces a clean trace artifact for every run. 

---

## 6) Risks you should plan for (and how to mitigate)

* **Probe quality is a bottleneck**: a bad probe will steer the loop incorrectly. Start with simple, obviously-correct structural probes (missing fields, schema ranges) before “smart” probes.
* **LLM can converge to a wrong but consistent story**: require evidence anchoring in state, and make “evidence sufficiency” a first-class probe.
* **Over-relaxation can degrade usefulness**: design ladders to relax *scope* or *fidelity*, not correctness constraints (e.g., still require citations, but allow fewer sections).

---

If you want, I can also sketch the **exact Pydantic models** and a first-pass **default probe library** (completeness/schema/contradiction heuristics) that’s generic enough to reuse across multiple workers, with a pitchdeck-specific probe as the first adapter.
