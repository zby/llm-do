# Test Suite Cleanup Review

## Context
Review of tests to keep them aligned with current llm-do behavior and public contracts.
No code changes applied yet; this captures the inventory and plan.

## Inventory

Core tests
- [A] `tests/test_toolset_args_validation.py` — Validates tool arg schemas and defaults for shell/filesystem/attachments; protects tool input validation contracts.
- [B] `tests/test_display_backends.py` — Verifies headless/JSON output formatting and event parsing; protects user-visible display behavior.
- [A] `tests/test_oauth_storage.py` — Ensures OAuth credential storage and refresh behavior; protects token persistence contract.
- [A] `tests/test_model_compat.py` — Covers model selection, compatibility patterns, and error cases; protects model resolution contract.
- [A] `tests/test_oauth_anthropic.py` — Tests Anthropic OAuth login/refresh and header overrides; protects provider auth integration contract.
- [A] `tests/test_config_overrides.py` — Validates `--set` parsing/apply semantics; protects CLI override contract.
- [A] `tests/test_shell.py` — Tests shell parsing, metachar blocking, rules, and execution outcomes; protects shell toolset safety/behavior.
- [D] `tests/test_scenario_models.py` — Validates test-only scenario/streaming models; protects test harness utilities rather than library contract.

Runtime tests
- [A] `tests/runtime/test_cli_errors.py` — Exercises manifest/flag/input error handling and exit codes; protects CLI error contract.
- [B] `tests/runtime/test_events.py` — Ensures UI events are emitted correctly during calls/streaming; protects observable runtime event behavior.
- [A] `tests/runtime/test_worker_toolset.py` — Validates Worker-as-tool adapter, approval behavior, and depth limits; protects delegation contract.
- [A] `tests/runtime/test_worker_schema_in.py` — Verifies schema_in affects tool schemas and worker arg validation; protects schema input contract.
- [A] `tests/runtime/test_model_resolution.py` — Covers model inheritance and compatible_models enforcement; protects model selection contract.
- [A] `tests/runtime/test_approval_wrappers.py` — Tests approval callback wrappers and session caching; protects approval wiring contract.
- [A] `tests/runtime/test_toolset_classpath_loading.py` — Ensures unknown toolsets are rejected at registry build; protects config validation.
- [D] `tests/runtime/test_invocables.py` — Uses private `_build_user_prompt`; protects internal prompt-building behavior.
- [A] `tests/runtime/test_worker_file.py` — Parses worker frontmatter, toolsets, server-side tools, and schema refs; protects worker file schema contract.
- [A] `tests/runtime/test_manifest.py` — Validates manifest schema defaults, loading, and path resolution; protects project manifest contract.
- [A] `tests/runtime/test_discovery.py` — Ensures module loading, toolset discovery, and duplicate detection; protects discovery behavior.
- [C] `tests/runtime/test_tools_unit.py` — Executes example tool functions through runtime context; protects example tool integration.
- [A] `tests/runtime/test_context.py` — Validates runtime tool calls, proxy access, and depth tracking; protects WorkerRuntime contract.
- [B] `tests/runtime/test_cli_approval_session.py` — Confirms approval cache persists across runs; protects approval workflow behavior.
- [C] `tests/runtime/test_build_entry_resolution.py` — Builds registry across nested workers and schema refs; protects entry build integration.
- [C] `tests/runtime/test_examples.py` — Smoke-tests example build/wiring; protects example integrity.
- [A] `tests/runtime/test_entry_schema_in.py` — Ensures entry schema_in normalizes inputs and prompt specs; protects entry invocation contract.
- [B] `tests/runtime/test_message_history.py` — Verifies message history behavior across turns/nested calls; protects conversation semantics.
- [A] `tests/runtime/test_approval_wrapping.py` — Tests approval wrapping, bulk approvals, and entry behavior; protects approval gating contract.
- [A] `tests/runtime/test_toolset_approval_config.py` — Validates approval config attribute access; protects toolset approval config contract.
- [A] `tests/runtime/test_worker_recursion.py` — Ensures self-toolset resolution and max-depth enforcement; protects recursion safety contract.

UI tests
- [B] `tests/ui/test_exit_confirmation_controller.py` — Verifies exit confirmation flow; protects UI exit behavior.
- [B] `tests/ui/test_input_history_controller.py` — Validates history navigation/draft restoration; protects input UX behavior.
- [B] `tests/ui/test_approval_workflow_controller.py` — Ensures approval queue batching/indices; protects approval UI workflow.
- [B] `tests/ui/test_worker_runner.py` — Ensures turn concurrency rules and message history updates; protects UI orchestration behavior.

Live integration tests
- [C] `tests/live/test_greeter.py` — End-to-end LLM sanity check for greeter.
- [C] `tests/live/test_calculator.py` — End-to-end tool calling + streaming regression for calculator.
- [C] `tests/live/test_code_analyzer.py` — End-to-end shell tool usage with approvals.
- [C] `tests/live/test_web_searcher.py` — End-to-end server-side web search integration.
- [C] `tests/live/test_pitchdeck_eval.py` — End-to-end attachments/vision + delegation.
- [C] `tests/live/test_web_research_agent.py` — Multi-worker orchestration + web tools.
- [C] `tests/live/test_whiteboard_planner.py` — Vision + nested worker delegation.
- [C] `tests/live/test_recursive_summarizer.py` — Recursive worker behavior with depth control.

Support modules (test infrastructure)
- [D] `tests/conftest.py` — Shared fixtures and asyncio warning suppression for tests.
- [D] `tests/conftest_models.py` — Scenario/streaming model utilities used by tests.
- [D] `tests/tool_calling_model.py` — Deterministic tool-call model used in tests.
- [D] `tests/runtime/helpers.py` — Runtime test helpers.
- [D] `tests/live/conftest.py` — Live-test fixtures, env gating, and run helper.

## Obsolescence Detection
- `tests/runtime/test_invocables.py`: Uses private `_build_user_prompt`. Intent is ensuring empty input still yields a non-empty prompt; still relevant, but should be tested via public runtime APIs.
- `tests/runtime/test_worker_toolset.py` (`test_build_worker_tool_truncates_long_description`): Asserts exact length (203). Intent is truncation behavior; length is an implementation detail, so the assertion is brittle.
- `tests/test_shell.py`: Multiple `match=` assertions on exact error strings for blocked metacharacters. Intent (block unsafe constructs) is relevant, but the precise wording may not be stable.
- `tests/test_display_backends.py`: Exact string formatting for headless output. Intent (user-visible display formatting) is relevant, but whether the exact wording/format is a contract is unclear.

## Action Plan

KEEP (low risk)
- Keep public contract tests across config/model selection/OAuth, manifest/worker file parsing, approvals, runtime context, and UI flows. These align with current intended behavior and surface area.

REWRITE (low risk)
- `tests/runtime/test_invocables.py`: Reframe to use `Runtime.run_invocable` (or `WorkerInput`) and assert non-empty prompt via public runtime state, avoiding private `_build_user_prompt`.
- `tests/runtime/test_worker_toolset.py` (truncation test): Relax to assert truncation and ellipsis without hardcoding the exact length.

CONSOLIDATE
- None planned.

DELETE
- None planned.

## Needs Human Review
- Decide whether headless output formatting in `tests/test_display_backends.py` is a stable user-facing contract or a flexible implementation detail.
