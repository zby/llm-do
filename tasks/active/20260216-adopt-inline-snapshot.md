# Adopt inline-snapshot for test assertions

## Status
ready for implementation

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
- Use `.model_dump()` (or equivalent dict conversion) before snapshotting Pydantic models — constructors in snapshot literals don't work well
- Use `dirty-equals` (`IsDatetime()`, `IsStr(regex=...)`) for non-deterministic fields if needed
- Don't convert fuzzy substring checks (`"not found" in err`) to exact snapshots unless the message is stable — this is a per-test judgment call
- Start with `test_agent_file.py` as the pilot to establish the pattern

### How to verify
- `uv run pytest` passes before and after each file conversion
- `pytest --inline-snapshot=fix` correctly populates empty `snapshot()` placeholders
- Converted tests catch the same regressions as the originals (spot-check by temporarily breaking a parsed field)

## Decision Record
- Decision: Use inline-snapshot (not syrupy)
- Inputs: Pydantic team recommendation, inline storage preferred over separate snapshot files for readability
- Outcome: Inline snapshots in test source, auto-updatable via `--inline-snapshot=fix`

## Tasks
- [ ] Add `inline-snapshot` to dev dependencies in `pyproject.toml` and install
- [ ] Convert `tests/runtime/test_agent_file.py` — pilot file, establish the pattern
- [ ] Convert `tests/runtime/test_manifest.py` — config defaults and manifest structure assertions
- [ ] Convert `tests/test_shell.py` — parse_command and shell result assertions
- [ ] Selectively convert `tests/runtime/test_cli_errors.py` — only stable error messages
- [ ] Run full test suite, verify no regressions
- [ ] Update `AGENTS.md` or similar if a testing convention note is warranted

## Current State
Research complete. The discussion identified the four highest-value test files and established the conversion approach (`.model_dump()` + `snapshot()`, selective conversion for error messages). Ready to implement starting with `test_agent_file.py` as pilot.

## Notes
- `inline-snapshot` rewrites source files — always review the diff after `--inline-snapshot=fix`
- pytest config in `pyproject.toml` uses `addopts = ["-v", "--strict-markers", ...]` — no conflict expected with inline-snapshot flags
- The 64-file test suite doesn't need full conversion at once; the four listed files cover the highest-value patterns
