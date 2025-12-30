Do it **as an example application first**, and only later **extract the reusable bits into an optional extension (“contrib”)**—*not* as a core llm-do feature.

That matches llm-do’s explicit positioning:

* llm-do is an **imperative harness** where “your code owns control flow” and llm-do “intercepts at the tool layer.” ([GitHub][1])
* It also explicitly says it’s **not a durable workflow engine** (no built-in checkpointing/replay; restart on failure or integrate Temporal/Prefect/etc.). ([GitHub][1])
* Chang’s MACI stack (baiting / filtering / persistence incl. transactional memory) is **a coordination policy layer**, not a syscall layer. ([arXiv][2])

So: keep llm-do core “syscalls + unified function space + approvals” clean, and build MACI/UCCT as a **policy package that uses llm-do**.

---

## What goes where

### Keep in llm-do core (probably nothing new, or only generic hooks)

Only add something to core if it’s **mechanism**, not **policy**.

Examples of “mechanism” additions (if you discover you need them):

* A general “call middleware” / tracing hook around `ctx.call()` (for metrics).
* A structured event/log API.

But don’t ship “judge templates”, “debate policies”, or “transactional memory semantics” as core defaults. Those are opinions.

This is consistent with llm-do’s “harness, not graph” and “intercepts at tool layer” stance. ([GitHub][1])

---

### Build as an example application (first)

Create an example that proves the whole loop end-to-end, with real outcomes and ablations.

Recommended shape:

**`examples/maci_pitchdeck_eval/`** (or fork an existing example like pitchdeck_eval)

* `main.py` (Python entry) = the MACI coordinator in code
* `planner.worker` = produce plan/decision/claim
* `critic.worker` = generate counterarguments/alternatives (baiting)
* `crit_judge.worker` = CRIT-style gate (filtering)
* `memory_tools.py` = append-only transactional log + commit/rollback tools (persistence)

Why Python entry?

* MACI is basically “if stability low → debate; else proceed” logic. That’s native Python control flow, which llm-do explicitly prefers you to own. ([GitHub][1])

---

### Extract into an llm-do extension (after it works)

Once the example stabilizes, extract generic parts into something like:

**`llm_do/contrib/coordination/`**

* `probe.py` (anchoring/stability probes)
* `judge.py` (generic judge runner; your project supplies the prompt/template)
* `txn.py` (transaction log interface; backends: JSONL, sqlite, external)
* `debate.py` (debate controller / escalation policy)

This is the “progressive hardening” idea applied to coordination itself: start as a concrete app; then harden reusable patterns into code. ([GitHub][3])

---

## A concrete implementation plan that fits llm-do

### 1) Implement “anchoring probes” as a *library function*, not a framework feature

In your example, implement:

* `probe_stability(ctx, worker, input, variants=...) -> StabilityReport`

Variants you can do without touching llm-do internals:

* **Paraphrase variants**: call a “paraphraser” worker/tool, then re-run the worker on paraphrased prompt.
* **Retrieval variants** (if your example uses retrieval): change top-k or doc ordering.
* **N-samples**: run multiple times with fixed temperature settings.

The probe returns metrics like:

* agreement rate on key fields
* entropy / variance of structured outputs
* verifier pass rate (if you have deterministic checks)

This leans on llm-do’s “testing is statistical” framing for stochastic components. ([GitHub][3])

### 2) Implement “filtering” as a hard gate in your action/memory tools

Don’t rely on “the orchestrator will remember to judge”.

Instead:

* Expose **only** “guarded” tools to workers (e.g., `commit_claim()`, `write_file_guarded()`), not raw “write file” tools.
* Those guarded tools internally call the `crit_judge` worker and refuse/raise if rejected.

This matches llm-do’s “guardrails by construction” and “tool calls as syscalls (approvals)” philosophy—put enforcement in code/tool surfaces, not in prose. ([GitHub][4])

### 3) Implement “transactional memory” as an append-only event log backend

Given llm-do’s stance on durability, do *not* make llm-do itself a durable engine. ([GitHub][1])

In the example:

* `TxnLog.append(event)` (JSONL or sqlite)
* `begin(run_id)`
* `commit(run_id, artifacts, evidence_refs, judge_scores)`
* `rollback(to_commit_id)` (logical rollback = mark previous commit as superseded)

This leverages llm-do’s “distribution boundaries are natural checkpoints” concept: commits happen at boundaries where you freeze decisions/artifacts. ([GitHub][3])

### 4) Implement “baiting” (debate) as *conditional escalation*

In the coordinator:

* Run `planner` → `probe_stability`
* If stability is high: go straight to judge → commit → action
* If stability is low: spawn:

  * `critic` (attack plan)
  * `alt_planner` (independent solution)
  * `refiner` (reconcile + revise)
* Re-probe → judge → commit

This directly matches the paper’s MACI components at the application level (baiting/filtering/persistence). ([arXiv][2])

---

## The “do we ever put this in llm-do itself?” rule of thumb

Put it in **llm-do core** only if:

* it’s a **primitive mechanism** that many patterns need, and
* it doesn’t force a particular coordination ideology.

Put it in **llm_do.contrib** if:

* it’s reusable, but still “a policy layer”.

Keep it as an **example** if:

* you’re still tuning thresholds/heuristics/templates
* you’re not sure it generalizes beyond the demo task

Given MACI/UCCT are *definitions of a coordination policy layer*, they start life as **example**, graduate to **contrib**, and should almost never be **core**.

---

## What I’d do next (concretely)

1. Fork an existing example (pitchdeck_eval is perfect) into `examples/pitchdeck_eval_maci/`. ([GitHub][1])
2. Implement `probe_stability()` + `crit_judge.worker` + `txn_log` (JSONL).
3. Add a simple ablation flag: `--mode baseline|judge|judge+txn|judge+txn+debate`.
4. Once that’s stable and obviously reusable, extract the probe/judge/txn helpers into `llm_do/contrib/coordination/` and have the example import from there.

If you want, I can sketch the directory structure and the minimal Pydantic models for `StabilityReport`, `JudgeVerdict`, and `CommitRecord` so you can drop them straight into an example.

[1]: https://raw.githubusercontent.com/zby/llm-do/refs/heads/main/README.md "raw.githubusercontent.com"
[2]: https://arxiv.org/abs/2512.05765 "[2512.05765] The Missing Layer of AGI: From Pattern Alchemy to Coordination Physics"
[3]: https://raw.githubusercontent.com/zby/llm-do/refs/heads/main/docs/theory.md "raw.githubusercontent.com"
[4]: https://raw.githubusercontent.com/zby/llm-do/refs/heads/main/docs/concept.md "raw.githubusercontent.com"
