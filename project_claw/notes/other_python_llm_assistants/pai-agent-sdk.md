# PAI Agent SDK / Paintress CLI

SDK for agent runtimes with a reference TUI (paintress-cli). Evaluated for fit with llm-do's worker-first orchestration and approval model.

## Context
We want to understand how close PAI Agent SDK is to llm-do's approach, and whether we could integrate llm-do's runtime into their environment (or vice versa).

## Quick Facts

| | |
|---|---|
| **Repository** | https://github.com/youware-labs/pai-agent-sdk |
| **Primary use case** | Agent SDK + reference TUI (paintress-cli) |
| **Python version** | >=3.11,<3.14 |
| **License** | BSD 3-Clause |
| **LLM integration** | pydantic-ai |
| **Stars/Activity** | Not checked (offline) |

## Tech Stack

| Component | Library | Notes |
|-----------|---------|-------|
| **TUI framework** | prompt_toolkit | Paintress CLI uses prompt_toolkit for UI |
| **Rendering** | Rich | Panels, markdown, syntax highlighting |
| **CLI framework** | click | setup wizard and CLI entry |
| **Environment abstraction** | agent-environment | FileOperator, Shell, ResourceRegistry |
| **LLM integration** | pydantic-ai | Agents, streaming, tool system |
| **Async** | asyncio + anyio | Async file/shell ops |
| **Browser automation** | Docker sandbox | Headless Chrome via SDK |
| **MCP** | pydantic-ai MCP | Optional MCP server toolsets |

## Architecture Notes (SDK)

### Environment and Context Split
- Long-lived `Environment` owns FileOperator, Shell, ResourceRegistry.
- Short-lived `AgentContext` holds model/tool config and session state.
- `create_agent()` returns `AgentRuntime` with AsyncExitStack lifecycle management.

### Toolsets and Hooks
- Tools are classes (`BaseTool`) collected by `Toolset`.
- Toolsets support global pre/post hooks and per-tool hooks.
- Tools can inject instructions into the system prompt.

### Approvals / HITL
- `need_user_approve_tools` is stored on context; tools raise `ApprovalRequired` when called.
- MCP servers can be gated via `need_user_approve_mcps`.

### Subagents and Skills
- Subagents are markdown configs with tool inheritance and optional tools.
- Skills are markdown instructions scanned from `skills/` under allowed paths, with progressive loading.

### Resumable State
- Session state can be exported/restored (`ResumableState`).
- Resource state can be exported/restored (resumable resources/factories).

## GUI Architecture (Paintress CLI)

- prompt_toolkit Application with dual-pane layout and scrollable output.
- Rich rendering layer for markdown/code blocks and tool outputs.
- Plan/Act split: separate runtimes with different tools and instructions.
- Steering manager injects additional context into the agent history.
- Approval flow uses blocking events integrated into the prompt_toolkit loop.

## Distance From llm-do

### Control Flow
- PAI is agent-centric; llm-do is worker-centric and imperative.
- PAI encourages long-lived context; llm-do prefers per-call toolset instantiation and tight worker scopes.

### Tool Plane
- Both rely on tool calls with approvals, but:
  - PAI gates via `ApprovalRequired` inside toolset logic.
  - llm-do gates via ApprovalToolset wrapping all toolsets in the runtime.

### Environment Abstraction
- PAI has a first-class Environment protocol (FileOperator/Shell/Resources).
- llm-do is path-based toolsets without a unified environment layer.

### Hierarchy
- PAI subagents are configured tools with inherited toolsets.
- llm-do workers are tools and can recurse arbitrarily with isolated history.

## Borrowable Patterns

- **Environment protocol** (agent-environment): clean boundary for filesystem/shell/resource management.
- **Resumable resources**: explicit export/restore for browser sessions and other handles.
- **Skills with progressive loading**: scalable instruction injection.
- **Toolset hooks**: pre/post hooks that can implement logging, validation, or observability.

## Integration Options

### Us -> Them (embed llm-do in PAI)
1. **Tool wrapper**: implement a `BaseTool` that runs an llm-do entry via `Runtime.run_entry`.
   - Pros: minimal changes to PAI, easy to ship.
   - Cons: nested LLM loops, approvals double-gated, environment mismatch.
2. **Toolset bridge**: convert llm-do ToolsetDef (TOOLSETS/ToolsetFunc) into a PAI Toolset, exposing llm-do workers as tools.
   - Pros: tighter integration with PAI tool selection.
   - Cons: requires adapter for llm-do runtime config and approvals.

### Them -> Us (reuse PAI in llm-do)
1. **Environment adapter**: add optional support for agent-environment in llm-do toolsets.
   - Pros: unlocks remote file operators and resource registry.
   - Cons: would require refactoring llm-do toolsets to async and path-validated operations.
2. **Borrow TUI patterns**: plan/act split and steering for llm-do UI.
   - Pros: can be incremental.
   - Cons: llm-do UI is Textual, PAI uses prompt_toolkit.

## Open Questions
- Is it worth adopting agent-environment, or would that dilute llm-do's minimal runtime?
- How would approvals compose if llm-do runs as a tool inside PAI (double prompts)?
- Do we want resumable session state, or do we prefer ephemeral runs with external orchestration?
- If integrating, who owns the UI: llm-do or paintress-cli?
