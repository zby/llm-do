# PydanticAI Runtime Split and Trace Hooks

## Context
We want to propose changes to PydanticAI to make systems like llm-do easier to build. llm-do already separates shared runtime state from per-call state, but this split is implemented outside PydanticAI. Approvals are addressed separately in `docs/notes/meta/blocking_approvals.md`; this note focuses on runtime, usage, and message history.

## Findings
- Separate agent spec from execution state. Treat `Agent` as immutable spec (instructions, schemas, default model/toolsets) and introduce a `Runtime` or `Session` object that owns mutable run state (usage sink, message log, event hooks, approval handler).
- Share runtime across agents. Multi-agent systems should be able to run different agents against a shared runtime so usage and logs aggregate coherently.
- Usage aggregation should be first-class. Add a `UsageCollector`/`UsageRecorder` interface to `Agent.run(...)` or runtime. Each model call emits a `UsageEvent` including `agent_name`, `run_id`, `parent_run_id`, `model`, and `model_settings`, so totals can be aggregated across agents and model settings.
- Structured message history / trace. Provide a `MessageStore` or `RunTrace` abstraction that captures message parts with metadata (`agent_name`, `depth`, `parent_tool_call_id`, timestamps, tool name), and let `Agent.run(...)` accept and update it. This avoids relying on private hooks like `_agent_graph.capture_run_messages` and makes incremental logging stable.
- First-class run/call identifiers. Add `run_id` and `parent_run_id` to `RunContext` so traces and usage can be correlated across nested calls and tool invocations.
- These changes map cleanly to llm-do's runtime model (`llm_do/runtime/shared.py`, `llm_do/runtime/call.py`) and would remove current workarounds for usage logging and message capture.

## Open Questions
- Naming and lifecycle: `Runtime` vs `Session`, and whether it is a context manager or an explicit object passed into `run()`.
- Backwards compatibility: how to keep simple one-off `agent.run()` calls ergonomic while enabling shared runtime state.
- Model settings identity: how to normalize or hash `model_settings` for aggregation.
- Should usage aggregation include server-side tool usage or be limited to LLM token usage.
- How streaming updates map into the structured message store without losing incremental deltas.

