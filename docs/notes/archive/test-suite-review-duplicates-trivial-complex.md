# Test Suite Review: Duplicates, Trivial, and Complex Tests

## Context
Requested review of the current test suite to spot duplicate coverage, trivial tests, and tests that are overly complex or costly to maintain, with proposals for changes.

## Progress

### Done
- [x] `test_streaming_events_include_complete_event` removed from `test_scenario_models.py` (duplicated `test_events.py` coverage)
- [x] `tests/test_filesystem_toolset.py` removed (trivial)
- [x] `tests/test_oauth_pkce.py` merged into oauth_anthropic
- [x] Headless display `test_writes_event_to_stream` removed (duplicate of `test_handles_status_event`)

### Not Yet Addressed

#### Duplicates / Overlapping Coverage
- [x] Example smoke tests in `tests/runtime/test_examples.py` overlap with `tests/live/*` - **Accepted**: smoke tests verify build/load, live tests verify LLM behavior.
- [x] Shell metacharacter blocking tested at two layers in `test_shell.py` - **Accepted**: unit tests for `check_metacharacters` + integration test for `ShellToolset.needs_approval` is appropriate layering.
- [x] Calculator tool behavior in `test_tools_unit.py`, `test_scenario_models.py`, `live/test_calculator.py` - **Accepted**: tests different layers (unit, test harness, E2E).

#### Trivial / Low-Signal Tests
- [x] `tests/runtime/test_context.py` low-signal tests (`test_context_max_depth`, `test_context_child`) - **Already removed**.
- [x] `tests/runtime/test_events.py` on_event defaults tests (`test_context_accepts_on_event_callback`, etc.) - **Already removed**.

#### Too Complex / High Maintenance
- [x] `tests/runtime/test_events.py::TestCLIEventIntegration` patches `build_entry` - **Fixed**: Added `entry` parameter to `run()` for dependency injection.
- [x] Live tests with heavy file output - **Accepted**: Inherent to integration testing; properly skip when dependencies missing.

## Conclusion
All items resolved. Test suite cleanup complete.
