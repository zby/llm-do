---
description: Systematic review of docs/notes/ for obsolescence, redundancy, and overlap — work through items one by one
---

# Notes Review (2026-02-19)

Systematic review of all 113 files in docs/notes/. Each item has a recommended action. Work through them one at a time, verifying before acting.

Status key: [ ] pending, [x] done, [-] skipped

---

## 1. Definitely Obsolete

These reference removed concepts (Worker class) or describe unimplemented proposals with no active path.

- [x] **`library-system-spec.md`** (366 lines) — ~~References Worker class (removed). Library system never built. Draft status. Action: delete.~~ Updated to current architecture (worker→agent, .worker→.agent, project.yaml→project.json, lib.yaml→lib.json, added integration points section). Kept as active design spec.
- [x] **`execution-mode-scripting-simplification.md`** (64 lines) — ~~Proposes `quick_run`/`Runner` helpers never implemented. References `Worker.call()` which no longer exists. Action: delete.~~ Rewritten against current architecture. Pain points validated — embedding still requires ~15 lines of boilerplate. Proposals updated: `quick_run`, `Runtime.from_project()`, approval presets. Kept as active design spec.
- [ ] **`research/experiment-runtime-without-worker.md`** (51 lines) — Exploring removing Worker class. This happened. Historical artifact. **Action: delete.**
- [ ] **`research/manifest-selected-entry-motivation.md`** (36 lines) — Motivation for a decision already implemented. Rationale baked into code. **Action: delete.**
- [ ] **`agent-skills-unification.md`** (82 lines) — Proposal to align with agentskills.io standard. Never acted on. **Action: delete.**
- [ ] **`llm-do-project-mode-and-imports.md`** (419 lines) — Pre-implementation spec for project mode, which is now live code. References Worker terminology throughout. **Action: delete** (implementation is the source of truth now).

## 2. Duplicates / Redundant Pairs

- [ ] **`type-catalog-review.md`** (top-level, 159 lines) vs **`research/type-catalog-review.md`** (58 lines) — Same title, same topic. Top-level is the expanded version. **Action: delete `research/type-catalog-review.md`.**
- [ ] **`meta/blocking_approvals.md`** (427 lines) — Raw upstream proposal draft. The analytical synthesis lives in `we-want-to-get-rid-of-approval-wrapping.md` + `pydanticai-traits-api-analysis.md`. **Action: decide — delete raw draft or keep as reference material.**
- [ ] **`reviews/useless-features-audit-2026-01-24.md`** (232 lines) — Superseded by 01-29 and 02-09 audits. **Action: delete** (findings carried forward into later audits).
- [ ] **`reviews/useless-features-audit-2026-01-29.md`** (110 lines) — Superseded by 02-09 audit. **Action: delete** (findings carried forward).

## 3. Stale Reviews Cluster (47 simplify-*.md files)

The runtime→project refactor is done. `toolsets/loader.py` removed. `worker_*` aliases removed. `simplify-summary.md` (2026-02-09) explicitly calls the old `simplify-runtime-{agent-file,discovery,entry-resolver,input-model-refs,manifest,registry}.md` files "historical records."

- [ ] **6 old `simplify-runtime-*.md` files** (agent-file, discovery, entry-resolver, input-model-refs, manifest, registry) — Explicitly marked historical by simplify-summary. Code moved to project/. **Action: delete all 6.**
- [ ] **Remaining ~35 simplify-*.md files** — Standing recommendations with no completion markers. 11-25 lines each. **Action: review whether `simplify-summary.md` captures everything worth keeping, then delete the individual files.** Alternatively, keep as a backlog if any recommendations are still actionable.
- [ ] **`simplify-summary.md`** — Synthesizes the campaign. **Action: keep** as the single record of simplification work.

## 4. Likely Stale (unimplemented proposals, no active path)

These are design proposals that were never implemented. Decide case by case whether the ideas are still worth pursuing.

- [ ] **`subagent-onboarding-protocol.md`** (225 lines) — Bidirectional setup conversation before subagent starts work. No code exists. **Action: evaluate — still a desired feature, or superseded by current dynamic agents?**
- [ ] **`git-integration-research.md`** (181 lines) — Research from Aider/golem-forge. No git toolset built (git works via shell rules). **Action: evaluate — is a dedicated git toolset still planned?**
- [ ] **`container-security-boundary.md`** (87 lines) — Marked "Concept / Future Direction." No implementation. **Action: evaluate — still a goal, or just deployment advice?**
- [ ] **`python-agent-annotation-brainstorm.md`** (127 lines) — Decorator API brainstorm. Doesn't match current .agent file approach. **Action: evaluate — is a Python-only agent definition still desired?**
- [ ] **`pure-python-vs-mcp-codemode.md`** (58 lines) — MCP code mode comparison. **Action: evaluate — still useful as positioning document?**

## 5. Needs Terminology Update

- [ ] **`dynamic-agents-runtime-design.md`** (151 lines) — Implemented feature, but note body still uses `worker_create`/`worker_call` terminology. Only the 2026-01 addendum at top reflects current `agent_create`/`agent_call` names. **Action: update terminology or add a note that the body uses old names.**

## 6. Weak Structure / Missing Schema

These subdirectories contain files with no frontmatter, making them invisible to the knowledge graph.

- [ ] **`examples/`** (3 files: AICL.md, Chang2025.md, LongCoT.md) — No frontmatter, no headings. Raw AI analysis dumps. **Action: evaluate — add frontmatter, restructure, or delete?**
- [ ] **`related_works/`** (6 files) — No frontmatter. Not integrated. **Action: add minimal frontmatter (description at minimum) or delete if stale.**
- [ ] **`other_python_llm_assistants/`** (6 files including 705-line borrowing report) — No frontmatter. **Action: add minimal frontmatter or evaluate relevance.**
- [ ] **`agent-learnings/README.md`** — Single file in a subdirectory. No frontmatter. **Action: evaluate — merge into parent or delete if empty/stale.**

## 7. Still Relevant (no action needed)

For reference — these were reviewed and found current:

- **Approvals cluster** (7 notes): `approvals-index.md`, `capability-based-approvals.md`, `approvals-guard-against-llm-mistakes-not-active-attacks.md`, `approval-override-rationale.md`, `ui-event-stream-blocking-approvals.md`, `preapproved-capability-scopes.md`, `we-want-to-get-rid-of-approval-wrapping.md`
- **Toolset state cluster** (4 notes): `toolset-state-spectrum-from-stateless-to-transactional.md`, `toolset-state-prevents-treating-pydanticai-agents-as-global.md`, `proposed-toolset-lifecycle-resolution-for-pydanticai.md`, `stateful-flag-evaluation-against-toolset-spectrum.md`
- **Crystallisation pair**: `crystallisation-learning-timescales.md`, `crystallisation-is-continuous-learning.md`
- **Upstream tracking**: `pydanticai-upstream-index.md`, `pydanticai-traits-api-analysis.md`
- **Other current**: `llm-do-vs-pydanticai-runtime.md`, `execution-modes-user-stories.md`, `stabilize-message-capture.md`, `tool-output-rendering-semantics.md`, `tool-result-truncation.md`, `toolset-instantiation-questions.md`, `pure-dynamic-tools.md`, `programmatic-embedding.md`, `index.md`
- **Reviews still current**: `useless-features-audit-2026-02-09.md`, `review-modules-summary.md`, `review-solid.md`, `review-tests.md`
- **Meta**: `llm-day-2026-presentation.md`, `llm-day-2026-presentation-v2.marp.md`, `meetup-demo-plan.md`, `pydanticai-runtime-trace.md`
- **Research**: `research/voooooogel-multi-agent-future.md`, `research/adaptation-agentic-ai-analysis.md`

---

## Method

Reviewed by scanning all 113 files for descriptions and headings, cross-referencing against current codebase state (Worker class removed, project/ refactor complete, dynamic agents implemented, library system not built, git toolset not built, container security not implemented, agent-skills standard not adopted). Each recommendation should be verified before acting.
