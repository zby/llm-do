# Test Suite Cleanup Review

## Context
Review of tests to keep them aligned with current llm-do behavior and public contracts.

## Run Log
- 2026-01-29: Inventory + action plan captured. No code changes yet.

## Inventory

Core tests
- [A] `tests/test_model_registry.py` — Registers custom model factories and rejects duplicates; protects model factory registration contract.
- [D] `tests/test_scenario_models.py` — Validates scenario/calculator/conversation test models and streaming paths; protects test harness utilities.
- [A] `tests/test_filesystem.py` — FileSystemToolset approval short-circuiting and unknown tool behavior; protects tool approval contract.
- [A] `tests/test_toolset_args_validation.py` — Shell/FileSystem arg validators enforce required fields and defaults; protects tool schema contract.
- [A] `tests/test_oauth_storage.py` — OAuth credential save/load/refresh flow; protects OAuth storage contract.
- [A] `tests/test_shell.py` — Shell parsing, metachar blocking, rule matching, and execution outcomes; protects shell tool safety contract.
- [A] `tests/test_oauth_anthropic.py` — Anthropic OAuth login/refresh and header overrides; protects provider OAuth integration.
- [A] `tests/test_model_compat.py` — Model pattern matching, compatibility validation, env fallback; protects model selection contract.
- [B] `tests/test_display_backends.py` — Headless display formatting + runtime->UI event adaptation; protects user-visible output mapping.

Runtime tests
- [B] `tests/runtime/test_context.py` — Call depth increments only on call_agent; protects runtime context depth semantics.
- [B] `tests/runtime/test_approval_wrapping.py` — Approval wrapping rejects pre-wrapped toolsets and enforces approvals; protects approval gating behavior.
- [B] `tests/runtime/test_agent_toolset.py` — AgentToolset creation/description truncation/call delegation; protects agent-as-tool behavior.
- [B] `tests/runtime/test_toolset_classpath_loading.py` — Registry rejects unknown toolset names in agent files; protects config validation.
- [D] `tests/runtime/test_toolset_approval_config.py` — Approval config metadata must be a dict; protects internal toolset config invariant.
- [A] `tests/runtime/test_manifest.py` — Manifest schema defaults, validation, load/resolve paths; protects project manifest contract.
- [B] `tests/runtime/test_discovery.py` — Module loading/toolset discovery/duplicate detection; protects discovery behavior.
- [A] `tests/runtime/test_agent_file.py` — Agent frontmatter parsing for toolsets/server_side_tools/schema refs; protects agent file schema contract.
- [C] `tests/runtime/test_examples.py` — Example projects build/wiring smoke tests; protects example integrity.
- [B] `tests/runtime/test_message_history.py` — Message history isolation across turns/nested calls; protects conversation semantics.
- [B] `tests/runtime/test_toolset_instances.py` — Per-call toolset instantiation and cleanup; protects runtime lifecycle behavior.
- [A] `tests/runtime/test_cli_errors.py` — CLI error handling, exit codes, input validation; protects CLI contract.
- [B] `tests/runtime/test_cli_approval_session.py` — Approval cache persists across runs; protects approval workflow behavior.
- [B] `tests/runtime/test_events.py` — User/tool events emitted with callback wiring; protects event stream behavior.
- [B] `tests/runtime/test_approval_wrappers.py` — Approval callback wrappers and denial payloads; protects approval policy behavior.
- [B] `tests/runtime/test_invocables.py` — FunctionEntry helpers and non-empty prompt fallback; protects prompt behavior.
- [A] `tests/runtime/test_entry_input_model.py` — Entry input_model normalizes inputs/prompt; protects entry invocation contract.
- [B] `tests/runtime/test_call_scope.py` — CallScope cleanup on exit; protects runtime lifecycle behavior.
- [C] `tests/runtime/test_tools_unit.py` — Example tool functions exercised via toolset call path; protects example integration.
- [C] `tests/runtime/test_build_entry_resolution.py` — Registry build resolves nested agent toolsets/schema refs; protects entry build integration.
- [B] `tests/runtime/test_cli_logging.py` — Message log callback emits JSONL per message; protects CLI logging behavior.
- [A] `tests/runtime/test_model_resolution.py` — CallContext model propagation and NullModel behavior; protects model resolution contract.
- [A] `tests/runtime/test_agent_input_model.py` — Agent input_model shapes tool schemas/normalize_input; protects agent input contract.
- [B] `tests/runtime/test_agent_recursion.py` — Self-toolset recursion and max_depth enforcement; protects recursion safety behavior.
- [A] `tests/runtime/test_attachment_path.py` — Attachment path resolution/media types + project_root config; protects attachment contract.
- [B] `tests/runtime/test_dynamic_agents.py` — Dynamic agent create/call and toolset validation; protects dynamic agent behavior.

UI tests
- [B] `tests/ui/test_exit_confirmation_controller.py` — Two-step exit confirmation and reset; protects UI exit behavior.
- [B] `tests/ui/test_agent_runner.py` — Runner concurrency guard and message history updates; protects UI controller behavior.
- [B] `tests/ui/test_approval_workflow_controller.py` — Approval queue batching/indices and reset; protects approval UI workflow.
- [B] `tests/ui/test_input_history_controller.py` — Input history navigation and draft restore; protects input UX behavior.
- [B] `tests/ui/test_events_truncate.py` — truncate_text/lines suffix and line limits; protects UI formatting behavior.

Live integration tests
- [C] `tests/live/test_greeter.py` — Greeter example runs with real LLM; basic integration coverage.
- [C] `tests/live/test_calculator.py` — Tool-calling + streaming regression with real LLM; integration coverage.
- [C] `tests/live/test_code_analyzer.py` — Shell tool usage with approvals; integration coverage.
- [C] `tests/live/test_web_searcher.py` — Server-side web search integration coverage.
- [C] `tests/live/test_pitchdeck_eval.py` — PDF/vision attachments + delegation; integration coverage.
- [C] `tests/live/test_web_research_agent.py` — Multi-worker orchestration with web tools; integration coverage.
- [C] `tests/live/test_whiteboard_planner.py` — Vision + nested delegation; integration coverage.
- [C] `tests/live/test_recursive_summarizer.py` — Recursive summarizer workflow; integration coverage.
- [C] `tests/live/test_bootstrapping.py` — Dynamic agent creation in example; integration coverage.

Support modules and docs
- [D] `tests/conftest.py` — Global fixtures and asyncio warning suppression; test infra.
- [D] `tests/conftest_models.py` — Scenario models and streaming helpers; test infra.
- [D] `tests/tool_calling_model.py` — Deterministic tool-call mock model; test infra.
- [D] `tests/runtime/helpers.py` — Runtime test helpers for contexts/scopes; test infra.
- [D] `tests/live/conftest.py` — Live test fixtures, env gating, run_example helper; test infra.
- [D] `tests/__init__.py` — Test package marker.
- [D] `tests/runtime/__init__.py` — Runtime test package marker.
- [D] `tests/live/__init__.py` — Live test package marker.
- [D] `tests/README.md` — Testing patterns and fixture guidance.
- [D] `tests/live/README.md` — Live test instructions and env requirements.

## Obsolescence Scan
- No references to removed APIs or deprecated flags found.
- Potential brittleness: CLI tests assert on error message substrings; confirm whether those strings are part of the stable CLI contract.
- Potential brittleness: `tests/test_shell.py::test_command_not_found` asserts "not found" in stderr, which can vary by platform/shell.
- Model name drift risk: several tests hardcode provider model strings (e.g., anthropic:claude-haiku-4-5); update if providers rename/deprecate.
- Live web-search tests depend on provider server-side web search availability; update if provider behavior changes.

## Action Plan

KEEP (must-have)
- Keep all A/B tests; they map to public contracts and user-visible behaviors.
- Keep C integration tests; they guard example wiring and end-to-end flows.

REWRITE (nice-to-have)
- `tests/test_shell.py`: relax "not found" assertion to check non-zero exit and non-empty stderr for portability.
- `tests/runtime/test_cli_errors.py`: if CLI error text is not intended as a stable contract, relax to error categories/exit codes.

CONSOLIDATE
- None.

DELETE
- None.

NEEDS HUMAN REVIEW
- Decide whether CLI error message text is a stable contract or should be treated as incidental formatting.
- Confirm provider model strings used in tests remain the intended defaults.

