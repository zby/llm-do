# Assistant CLI Profiles + AGENTS Injection

## Status
information gathering

## Prerequisites
- [ ] design decision needed (AGENTS discovery + precedence + scope)
- [ ] none

## Goal
Introduce a dedicated assistant CLI mode/profile that layers AGENTS.md and other coding-assistant defaults on top of the existing one-shot runner without duplicating the core execution pipeline.

## Context
- Relevant files/symbols:
  - `llm_do/ctx_runtime/cli.py` (CLI entry, run modes, build_entry)
  - `llm_do/ctx_runtime/runner.py` (run_entry boundary)
  - `llm_do/ctx_runtime/invocables.py` (`WorkerInvocable.instructions` -> Agent)
  - `llm_do/ctx_runtime/worker_file.py` (worker file parsing)
- Related docs:
  - `docs/architecture.md` (execution flow, toolsets, approvals)
  - `AGENTS.md` (agent behavior expectations)
- How to verify / reproduce:
  - Run `llm-do` in one-shot mode and assistant mode; confirm assistant mode prepends AGENTS.md to the entry worker instructions and preserves approvals/tool resolution.

## Decision Record
- Decision: Add a small "runner profile" abstraction in the CLI layer to apply assistant defaults (AGENTS injection, default flags) without forking execution logic.
- Inputs:
  - Need a coding-assistant mode that auto-loads AGENTS.md and other repo-specific defaults.
  - Avoid duplicating run_entry/build_entry or diverging approval logic.
- Options:
  - A) Separate CLI executable with custom pipeline (risk drift, duplicated logic).
  - B) CLI profiles that wrap build_entry/run_entry (minimal divergence).
- Outcome: Prefer B; implement as subcommand or profile flag and keep all execution in the same core pipeline.
- Follow-ups:
  - Decide AGENTS lookup rule and precedence.
  - Decide scope of injection (entry-only vs all workers).

## Tasks
- [ ] Define runner profile data model and selection rules (subcommand or flag).
- [ ] Implement instruction augmentation hook (AGENTS.md loader) at build_entry time.
- [ ] Document assistant mode behavior in README/cli docs.
- [ ] Add tests for AGENTS injection and profile selection.

## Current State
Task created with initial abstraction sketch; needs decisions on AGENTS discovery/scope before implementation.

## Notes
- Abstraction sketch (CLI-layer profile):

```python
@dataclass(frozen=True)
class RunnerProfile:
    name: str
    default_flags: dict[str, Any]
    instruction_augmenters: list[Callable[[str, Path], str]]

# Example: assistant profile adds AGENTS.md

def inject_agents(instructions: str, worker_path: Path) -> str:
    agents_path = find_agents_md(start=worker_path.parent)
    if not agents_path:
        return instructions
    agents_text = agents_path.read_text(encoding="utf-8")
    return f"{agents_text}\n\n# ---\n\n{instructions}"

ASSISTANT_PROFILE = RunnerProfile(
    name="assistant",
    default_flags={"chat": True, "verbose": 1},
    instruction_augmenters=[inject_agents],
)
```

- Open decisions to capture before implementation:
  - AGENTS lookup: CWD vs worker dir vs nearest ancestor; allow override?
  - Prepend vs append; separators; max size or truncation behavior.
  - Scope: entry-only vs apply to all workers.
  - Python entrypoints: if entry is a tool/worker in code, do we inject AGENTS into workers they call?
