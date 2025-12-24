# Test Suite Review: Duplicates, Trivial, and Complex Tests

## Context
Requested review of the current test suite to spot duplicate coverage, trivial tests, and tests that are overly complex or costly to maintain, with proposals for changes.

## Findings

### Duplicates / Overlapping Coverage
- Streaming/event emission is covered multiple times: `tests/runtime/test_events.py` (streaming TextResponseEvent + tool call events) overlaps with `tests/test_scenario_models.py` (`TestStreamingModels` + `TestWorkerEntryWithScenarioModel`). Proposal: keep the runtime event tests as the canonical event-pipeline coverage and drop or slim the scenario-model event assertions to one targeted case (e.g., only the "no complete event when streaming" invariant).
- Tool-call event emission is tested in two places: `tests/runtime/test_events.py` (`test_tool_call_ids_correlate`) and `tests/test_scenario_models.py` (`test_worker_emits_events_with_scenario_model`). Only the runtime test asserts `tool_call_id` correlation. Proposal: keep the runtime-level correlation test and remove the scenario-model duplicate, or vice versa if scenario-model coverage is preferred.
- Example smoke tests are repetitive and overlap with live tests: `tests/runtime/test_examples.py` repeats near-identical "worker_loads" and "builds" checks for each example, and `tests/live/*` exercises the same examples end-to-end. Proposal: parameterize the smoke tests and keep one representative check per example type (single worker, delegation, code entry, server-side tools) instead of one per example directory.
- Shell metacharacter blocking is tested at two layers: `tests/test_shell.py` (`TestCheckMetacharacters`) and `tests/test_shell.py` (`TestShellToolsetNeedsApproval`) check the same blocked characters. Proposal: keep the unit tests for `check_metacharacters` and add a single integration test that `ShellToolset.needs_approval` delegates to it, removing per-character duplication.
- Calculator tool behavior is repeated across `tests/runtime/test_tools_unit.py`, `tests/test_scenario_models.py` (calculator model), and `tests/live/test_calculator.py`. Proposal: keep deterministic unit coverage (toolset + context) and reduce the scenario model or live tests to one high-value behavior (e.g., multi-tool call) instead of re-checking basic arithmetic.
- Headless display formatting overlaps: `tests/test_display_backends.py::TestHeadlessDisplayBackend.test_writes_event_to_stream` and `tests/test_display_backends.py::TestHeadlessDisplayBackend.test_handles_status_event` both assert status rendering. Proposal: keep the more specific formatting test and remove the generic write-to-stream check.

### Trivial / Low-Signal Tests
- `tests/test_filesystem_toolset.py` only checks a config flag in `needs_approval`. Proposal: fold into a broader filesystem toolset behavior test or drop if the config flag is already covered elsewhere.
- `tests/runtime/test_context.py` contains very low-signal property tests (`test_context_max_depth`, `test_context_child`) that merely re-assert assignments. Proposal: remove or merge into tests that depend on depth behavior (e.g., recursion guard tests).
- `tests/runtime/test_events.py` has multiple tests that only assert `on_event` defaults/assignment (`test_context_accepts_on_event_callback`, `test_context_on_event_defaults_to_none`, `test_context_from_entry_accepts_on_event`). Proposal: collapse into a single test or rely on higher-level event emission tests to cover wiring.
- `tests/test_oauth_pkce.py` verifies PKCE output length and character set in isolation. Proposal: merge into `tests/test_oauth_anthropic.py` so PKCE format is asserted in the actual login flow (reduces an extra file/test for a helper).
- `tests/runtime/test_examples.py` has repeated `assert worker_file.name == "main"` across examples. Proposal: keep only unique validations (e.g., toolsets, delegation wiring) and remove the name checks.

### Too Complex / High Maintenance
- `tests/test_scenario_models.py::TestStreamingModels.test_cli_no_duplicate_output_when_streaming` patches CLI entry points, filesystem temp worker files, and stdout/stderr. Proposal: move this to a smaller unit-level test in `llm_do.ctx_runtime.cli` that verifies "streaming suppresses final print" by testing a helper function, or keep a single integration test but trim the file I/O and patching.
- `tests/runtime/test_events.py::TestCLIEventIntegration` patches `build_entry` and points at example directories. Proposal: replace with a focused test that calls `run()` with a synthetic `WorkerEntry` (or a temporary worker file) to reduce fixture complexity and dependency on example project structure.
- Live tests with heavy file output (`tests/live/test_pitchdeck_eval.py`, `tests/live/test_web_research_agent.py`, `tests/live/test_whiteboard_planner.py`) are comprehensive but brittle. Proposal: keep one "full workflow" test per domain and reduce the rest to a single worker-level assertion (or mark secondary tests as manual-only) to cut API cost and flakiness.

## Open Questions
- Which coverage should be canonical for tool-call event emission: runtime event tests or scenario-model integration tests?
- Do we want to keep per-example smoke tests in `tests/runtime/test_examples.py`, or rely on the live tests plus a smaller parameterized smoke suite?
- Should PKCE validation live only in the Anthropic OAuth flow test, or keep a small unit test for the helper?
- Is the CLI streaming duplication test important enough to justify a heavier integration test, or do we accept a smaller unit-level assertion?

## Conclusion
Pending decisions on which layers to keep for overlapping coverage and how much integration testing to retain for examples/live workflows.
