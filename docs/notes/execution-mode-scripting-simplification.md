---
description: Simplifying Python embedding with quick_run and Runner helpers
---

# Execution Mode Scripting Simplification

## Status
Partially implemented. `Worker.call()` provides direct Python embedding; manifest-based CLI is the current approach.

## Context
- `docs/notes/execution-modes-user-stories.md` outlines goals for TUI-first workflows with a headless escape hatch and predictable approvals/outputs.
- Direct Python embedding is possible via `Worker.call()` with a `CallContext`.
- CLI currently requires a JSON manifest; direct `.agent` file execution is a future simplification.

## Findings
### Pain points with the current direct-run pattern
- **Boilerplate**: Each script rebuilds workers, loads instructions from disk, and wires approval/display plumbing even though behavior mirrors CLI defaults.
- **Path duplication**: FileSystemToolset and workers both accept `base_path`, forcing authors to remember to keep them in sync.
- **Output handling**: Headless scripts must manually choose verbosity, streaming, and JSON/Markdown formatting instead of reusing CLI defaults.
- **Policy drift**: Approval modes and tool exposure are configured differently between CLI and ad-hoc scripts, risking inconsistent safety defaults.

### Principles from the user stories to preserve
- **Chat-first, headless as opt-in**: Python embedding should feel like calling a worker function while still honoring the same approval/telemetry defaults as headless CLI runs.
- **Portable configuration**: Prompts, tool wiring, and base paths should live with the worker package so both CLI and scripts resolve them consistently.
- **Deterministic outputs**: Scripts should be able to request structured output (JSON/Markdown) and stable tool exposure to support CI and batch jobs.

### Proposed simplifications
1. **`quick_run` wrapper aligned with CLI defaults**
   - Accepts `path_or_worker`, `prompt`, and optional overrides (`approve_all`, `verbosity`, `output_format`).
   - Internally configures `HeadlessDisplayBackend` + `RunApprovalPolicy` mirroring `llm-do --headless` so scripts and CLI stay behaviorally identical.

2. **Keep the script as the manifest**
   - Let Python import tools and workers directly; avoid a separate YAML manifest when the code already captures intent.
   - Add a `load_workers_from_dir` helper that scans a directory for workers and instructions so authors don’t hand-enumerate imports when bulk-loading.
   - Provide `.run(prompt, **overrides)` on a `Runner` helper object for repeated calls in batch workflows.

3. **Shared output adapters**
   - Expose helpers to format results as JSON/Markdown/CSV with citation metadata so that headless scripts don’t reimplement formatting decisions.
   - Keep default output consistent with headless CLI (e.g., JSON envelope when `--json` is requested).

4. **Approval and tool exposure presets**
   - Offer presets like `SafeDefaults` (prompt approvals except read-only tools) and `ApproveAll` to map directly onto CLI flags.
   - Ensure presets propagate through sub-worker trees so scripted runs match interactive safety posture.

5. **Example shrink target**
   - Replace `experiments/inv/v2_direct/run.py` with a ~12–15 line sample using `quick_run`/`Runner` to demonstrate the pattern and keep docs/tests aligned with the API.

> **Note:** `Runner` here is a proposed helper surface, not an existing class. The intent is to wrap `Worker.call()` with default display/approval wiring so repeated calls from Python stay aligned with headless CLI defaults. Currently, `Worker.call()` requires manually constructing a `CallContext` with approval policy and event callbacks.

### How this supports the user stories
- **Headless automation**: Minimal script surface plus optional directory-scanning helpers give predictable approvals, relative-path stability, and structured outputs for CI or batch jobs.
- **Developer iteration**: One-liners for quick runs, with `Runner` reuse for debugging without opening the TUI.
- **Packaging/distribution**: Workers remain self-contained Python modules, with optional directory loaders to reduce boilerplate when bundling multiple workers.
- **Discovery**: `Runner.from_dir` can become the Python-side equivalent of `llm-do ./worker_dir`, reducing divergence between chat and script entrypoints.

## Open Questions
- What heuristics should `load_workers_from_dir` use to avoid surprising imports while still being convenient?
- What defaults should `quick_run` choose for output format—plain text vs JSON envelope?
- Should approval presets allow scoped grants (per tool/directory) to mirror future CLI ergonomics, or is global approve/prompt enough for now?
- How do we expose citation/source metadata consistently across chat/headless/script outputs without bloating simple runs?
- Does `Runner` become a new helper (wrapping `Worker.call()` + display/approval defaults), or should we extend `WorkerRunner` to serve both TUI and headless scenarios?

## Conclusion
A thin `quick_run` + `Runner` layer, paired with an opt-in `load_workers_from_dir` helper and output/approval presets, would collapse most of the boilerplate in `experiments/inv/v2_direct/run.py` while aligning direct Python runs with the expectations in the execution-mode user stories. The same worker artifacts could then serve chat, headless CLI, and embedded scripts with consistent safety and output defaults without introducing a separate manifest format.
