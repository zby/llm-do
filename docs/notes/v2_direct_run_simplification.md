# Simplifying v2_direct run.py

## Context
`experiments/inv/v2_direct/run.py` demonstrates running workers directly via Python, but it carries a lot of boilerplate (sys.path hack, instruction loading, worker assembly, approval wrapping, UI wiring, context run). The goal is to identify ways to make this script much simpler and to offer multiple ways to run the library (CLI, config-driven, Python API, embedding).

## Findings
- **Current state in `experiments/inv/v2_direct/run.py`**: manual sys.path injection, explicit instruction loading, WorkerEntry assembly, recursive approval wrapping, explicit UI event wiring, and low-level Context setup/run.
- **Ergonomics vs “traditional” llm-do (CLI)**:
  - CLI is frictionless for a quick run, but opaque for embedding and non-standard wiring (approval, toolsets, custom UI).
  - Direct Python is flexible and debuggable, but currently too verbose for a “copy/paste and tweak” workflow.
  - The ideal surface keeps CLI simplicity for quick runs while offering a minimal Python API for embedding without exposing internal plumbing.
### Postulated simplifications
- **Library-level convenience API**:
  - `llm_do.run(entry, prompt, *, model, approval_mode, verbosity, display)` that handles approval wrapping + display wiring internally.
  - `llm_do.run.from_instructions(dir, prompt, ...)` to assemble workers from an instructions directory and a config file.
  - `Context.run_with_defaults(...)` or `Context.from_entry(..., approval_mode=..., display=...)` to bundle the boilerplate.
- **Exported “evaluation” entrypoints**:
  - Move `run_evaluation()` into `llm_do.examples.pitchdeck` or `llm_do.eval.pitchdeck`, then keep `run.py` as a 5-line wrapper.
  - Provide a tiny `python -m llm_do.examples.pitchdeck` runner that prints results and takes flags for model/verbosity/approval.
- **Config-driven runner**:
  - A `llm_do run --config experiments/inv/v2_direct/config.yaml` path that defines model, prompt, workers, instructions dir, approval, verbosity.
  - A `llm_do.run.from_config(path)` function for direct Python usage.
- **Structured worker loaders**:
  - `WorkerEntry.from_dir("experiments/inv/v2_direct")` that loads instructions, default toolsets, and nested workers.
  - `WorkerEntry.with_tools(...)` builder to reduce boilerplate (e.g., `WorkerEntry.simple(name, instructions_path, tools=[...])`).
- **Approval handling as a first-class feature**:
  - `ApprovalMode = "auto" | "deny" | "prompt"` with a single wrapper function in core.
  - `ApprovalToolset.wrap_all(entry_or_toolsets, mode=...)` to remove the recursive wrapper from scripts.
- **Display/verbosity as defaults**:
  - `Context.from_entry(..., display="headless", verbosity=1)` auto-wires events to a backend.
  - Shortcut `llm_do.ui.run_with_display(...)` that returns the result and prints progress.
- **Packaging/setup**:
  - Avoid sys.path edits by using editable installs (`uv pip install -e .`) or `python -m llm_do`.
  - Provide a short README snippet for “direct Python” that imports a single helper.
- **Multiple usage patterns to support**:
  - CLI for quick runs.
  - Python API for embedding and notebooks.
  - Config-only for reproducible runs.
  - Example modules for “copy/paste and tweak” workflows.

## Open Questions
- Where should the “high-level runner” live (`llm_do.run`, `llm_do.runner`, `llm_do.eval`), and how public do we want it to be?
- Should worker assembly be declarative (YAML/JSON) or code-first with small helpers?
- What is the minimal set of options to expose (model, prompt, approval, verbosity, instructions dir) without overfitting?
- How should approval behavior be specified when running via config/CLI (global, per-tool, per-worker)?
- Do we want to standardize “example runners” as public modules, or keep them under `experiments/`?

## Proposed Answers
- **Runner location**: prefer `llm_do.run` as the stable public entry; avoid `llm_do.eval` for general usage; keep `llm_do.runner` internal if needed.
- **Worker assembly**: support both, but prioritize a small config format for CLI/reproducibility and a compact code-first helper for Python; keep them aligned in semantics.
- **Minimal options**: model, prompt/input payload, approval_mode, verbosity/display, instructions_dir; defer per-tool settings until a concrete need arises.
- **Approval behavior**: default global policy with an optional per-worker override; keep per-tool out of config until a real use case appears.
- **Example runners**: move polished examples into `examples/` as public modules; keep `experiments/` for scratch and avoid standardizing them.
