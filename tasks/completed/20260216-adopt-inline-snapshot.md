# Adopt inline-snapshot for test assertions

## Status
completed

## Prerequisites
- [x] none

## Goal
Replace verbose multi-field assertions in tests with `inline-snapshot` snapshot comparisons, starting with the highest-value files and establishing the pattern for future tests.

## Context

### Why inline-snapshot
[Pydantic article](https://pydantic.dev/articles/inline-snapshot) — inline-snapshot keeps expected values in the test source (not separate files), auto-generates them via `pytest --inline-snapshot=fix`, and composes with `dirty-equals` for non-deterministic fields. This fits llm-do's test style: many tests parse a structure and assert 5-10 fields individually.

### Current pain
Tests use per-field assertions for structured outputs:

```python
# test_agent_file.py — 6 assertions for one parse result
assert result.name == "test_agent"
assert result.model == "anthropic:claude-haiku-4-5"
assert result.instructions == "These are the instructions."
assert result.description is None
assert result.tools == []
assert result.toolsets == []
```

With inline-snapshot:
```python
assert result.model_dump() == snapshot({
    "name": "test_agent",
    "model": "anthropic:claude-haiku-4-5",
    "instructions": "These are the instructions.",
    "description": None,
    "tools": [],
    "toolsets": [],
})
```

One assertion, full coverage, auto-updatable.

### Relevant files/symbols
- `pyproject.toml` — add `inline-snapshot` to `[project.optional-dependencies] dev`
- `tests/runtime/test_agent_file.py` (395 lines) — highest value: many multi-field parse assertions on `AgentDefinition`
- `tests/runtime/test_manifest.py` (384 lines) — config defaults, manifest loading, structured validation
- `tests/runtime/test_cli_errors.py` (541 lines) — error message assertions; convert selectively (exact snapshots for stable messages, leave `in` checks for fragile ones)
- `tests/test_shell.py` (261 lines) — `parse_command` results, shell execution results

### Key decisions
- Prefer contract-focused snapshots over full-object snapshots. Snapshot only behavior-relevant fields unless full object equality is the contract under test.
- Use `.model_dump()` (or equivalent dict conversion) before snapshotting Pydantic models when a dict snapshot is the clearest contract.
- If non-deterministic values must be asserted, use `dirty-equals` matchers via `inline-snapshot` integration.
- Keep fuzzy substring checks (`"not found" in err`, platform-dependent shell stderr) as substring assertions unless the message is demonstrably stable.
- Start with `test_agent_file.py` as the pilot to establish the pattern

### How to verify
- Baseline before changes: `uv run pytest`
- For each converted file, run targeted fix mode and review the diff:
  - `uv run pytest tests/runtime/test_agent_file.py --inline-snapshot=fix`
  - `uv run pytest tests/runtime/test_manifest.py --inline-snapshot=fix`
  - `uv run pytest tests/test_shell.py --inline-snapshot=fix`
  - `uv run pytest tests/runtime/test_cli_errors.py --inline-snapshot=fix`
- Re-run each touched file without `--inline-snapshot=fix` to confirm normal pass.
- Run full suite after all conversions: `uv run pytest`
- Spot-check regression sensitivity by temporarily breaking one parsed field in a converted test and confirming failure.

## Decision Record
- Decision: Use inline-snapshot (not syrupy)
- Inputs: Pydantic team recommendation, inline storage preferred over separate snapshot files for readability
- Options:
  - Keep granular assertions only
  - Use external snapshot files (for example syrupy)
  - Use inline snapshots in source (chosen)
- Outcome: Inline snapshots in test source, auto-updatable via `--inline-snapshot=fix`
- Follow-ups:
  - If snapshot churn becomes noisy, document narrower snapshot conventions in `AGENTS.md`
  - If fuzzy matcher usage expands, standardize on `inline-snapshot[dirty-equals]` in dev deps

## Tasks
- [x] Add `inline-snapshot` to dev dependencies in `pyproject.toml` and install (choose plain package vs `inline-snapshot[dirty-equals]` based on actual matcher use)
- [x] Convert `tests/runtime/test_agent_file.py` — pilot file, establish the pattern. Most tests here are "parse YAML, get these exact fields" so full-object snapshots are the right contract. Other files will need more selective field choices.
- [x] Convert `tests/runtime/test_manifest.py` — config defaults and manifest structure assertions
- [x] Convert `tests/test_shell.py` selectively — snapshot deterministic parse/structured results; keep platform-dependent stderr checks as substring assertions
- [x] Selectively convert `tests/runtime/test_cli_errors.py` — only stable error messages; keep fragile path/shell text checks as `in` assertions
- [x] Run per-file `--inline-snapshot=fix` commands and review rewritten snapshots in diff
- [x] Run full test suite, verify no regressions
- [x] Update `AGENTS.md` or similar if a testing convention note is warranted

## Current State
Implementation complete.
Changes landed in:
- `pyproject.toml` (added `inline-snapshot` in dev dependencies)
- `tests/runtime/test_agent_file.py` (dataclass snapshot assertions)
- `tests/runtime/test_manifest.py` (manifest/config snapshot assertions)
- `tests/test_shell.py` (deterministic shell parsing/rule snapshots; platform-sensitive stderr checks kept as substring assertions)
- `tests/runtime/test_cli_errors.py` (stable CLI error/success snapshots; fragile message checks retained as substring assertions)
- `AGENTS.md` (added inline-snapshot verification convention)

Verification run:
- `uv run pytest tests/runtime/test_agent_file.py --inline-snapshot=fix`
- `uv run pytest tests/runtime/test_manifest.py --inline-snapshot=fix`
- `uv run pytest tests/test_shell.py --inline-snapshot=fix`
- `uv run pytest tests/runtime/test_cli_errors.py --inline-snapshot=fix`
- `uv run pytest tests/runtime/test_agent_file.py tests/runtime/test_manifest.py tests/test_shell.py tests/runtime/test_cli_errors.py`
- `uv run ruff check .`
- `uv run mypy llm_do`
- `uv run pytest`

## Notes
- `inline-snapshot` rewrites source files — always review the diff after `--inline-snapshot=fix`
- pytest config in `pyproject.toml` uses `addopts = ["-v", "--strict-markers", ...]` — no conflict expected with inline-snapshot flags
- Shell/CLI error text can vary by environment and should not be over-snapshotted
- The 64-file test suite doesn't need full conversion at once; the four listed files cover the highest-value patterns
