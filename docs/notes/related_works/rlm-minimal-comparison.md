# Recursive Language Models (RLM) minimal vs llm-do

## Context
We need to compare the public `alexzhang13/rlm-minimal` implementation to llm-do’s approach, identify the repo’s key design decisions, and distill what llm-do would need to add to enable similar behaviors.

## Findings

### Snapshot
- Repo: `https://github.com/alexzhang13/rlm-minimal` (commit `1bed65d92c6ea41044c2f3713762fc37f63eefc5`)
- Scope: intentionally stripped-down, “minimal version” with optional logging and no cost tracking.

### Core design decisions in rlm-minimal
- **RLM as a Python class with a `completion()` interface.** The core abstraction is `RLM` (abstract base class) with `completion`, `cost_summary`, and `reset`, and `RLM_REPL` implements the recursive behavior in plain Python rather than a DSL.
- **REPL-mediated recursion.** The top-level model is repeatedly prompted to decide its “next action,” and it executes code by emitting ```repl``` blocks. The system detects those blocks, executes them, and appends execution results back into the message list.
- **Explicit termination protocol.** The system prompt mandates `FINAL(...)` or `FINAL_VAR(...)` to end the loop; the loop runs for `max_iterations`, then forces a final answer if none appears.
- **Single-depth recursion by default.** The REPL environment injects `llm_query`, a sub-LLM call implemented by `Sub_RLM`. The README explicitly says depth > 1 would require swapping `Sub_RLM` for `RLM_REPL` and dealing with nested REPL environments.
- **Context as an executable variable.** The context is loaded into a temporary directory as `context.txt` or `context.json`, then exposed to the REPL as the `context` variable. Large contexts are expected to be chunked and analyzed via sub-LLM calls.
- **Execution environment choices.** The REPL uses `exec`/`eval` with a curated `__builtins__` set, captures stdout/stderr, keeps locals across steps, and prints the last expression like a notebook. It allows `__import__` and `open`, so it is not a hard sandbox.
- **Model/provider coupling.** The minimal implementation is OpenAI-only (`OpenAIClient`), uses GPT-5 model names by default, and expects `OPENAI_API_KEY`. No provider-agnostic interface is present.
- **Logging is optional and presentation-first.** Two loggers (ANSI and rich) focus on readability, truncation, and “notebook-like” REPL output rather than structured traces.

### What this implies about their approach
- The primary unit of recursion is **LLM-generated code**, not tool calls or declarative tasks.
- The LLM’s “plan” is externalized into stateful REPL variables and `llm_query` subcalls, which is a manual but flexible long-context strategy.
- The system trusts the model enough to execute arbitrary code (within a permissive builtins whitelist), prioritizing speed of experimentation over safety.

### Mapping to llm-do’s approach
- **Control flow:** rlm-minimal runs a model-driven loop; llm-do runs code-driven orchestration where workers call workers/tools as functions.
- **Recursion model:** rlm-minimal nests LLM calls inside a REPL function; llm-do nests workers/tools with a shared runtime and explicit depth limits.
- **Safety boundary:** rlm-minimal executes code inside an unsandboxed REPL; llm-do enforces approvals and explicit toolsets.
- **Prompting:** rlm-minimal relies on a heavy system prompt + FINAL protocol; llm-do uses explicit workers and tool schemas with minimal in-prompt control flow.
- **Extensibility:** rlm-minimal is a single Python module with hand-wired components; llm-do is a framework for composing many workers and toolsets.

## Open Questions
- Do we want a built-in REPL toolset (stateful Python exec) or keep that as an example/project-level tool?
- If we add a REPL toolset, what sandboxing or approval defaults are acceptable?
- Is there demand for a standard “long-context recursive exploration” pattern (RLM-style) in our examples?

## Conclusion
Intuitive contrast: rlm-minimal is a **model-driven REPL** (the model writes and executes code to explore context), while llm-do is a **code-driven harness** (humans write orchestration and the model is a delegated worker). To enable RLM-style features in llm-do, we could add a stateful REPL toolset with persisted locals + stdout capture, a first-class “nested model call” tool (configurable model/context window), and an optional iterative runner that loops a worker until a structured FINAL/FINAL_VAR termination signal is returned, all wrapped in explicit approvals/sandboxing for exec and file access.
