# Interactive Approval Loop — CLI User Stories

> Persona: command-line operator running `llm-do` workers directly from the terminal. The CLI pauses tool execution and prompts the operator inline until a decision is entered.

## Story 1 — Pause run when a guarded tool is invoked
- **As** an operator watching a long-running worker execution in the terminal,
- **I want** the CLI to pause immediately when the agent requests a guarded tool (write, worker creation, delegation outside allowlist),
- **So that** I can inspect the request before anything happens.

**Acceptance Criteria**
1. When the worker reaches a gated tool, the CLI prints a structured prompt (tool name, parameters, rationale) and the backend holds that tool call open.
2. No side effects occur until the operator types an action (`approve`, `deny`, etc.).
3. Previous log output remains visible so the operator can scroll/inspect context before answering.

## Story 2 — Approve and resume inline
- **As** the same operator after inspecting the request,
- **I want** to type an “approve” command so the tool executes immediately and the worker run resumes without restarting,
- **So that** I avoid re-running prior steps or re-uploading attachments.

**Acceptance Criteria**
1. Approving unblocks the waiting tool call and streams the result back into the terminal transcript.
2. The CLI clearly echoes which tool was approved and when execution resumed.
3. Subsequent tool calls in the same run can trigger their own approval pauses without losing history or environment state.

## Story 3 — Reject with feedback
- **As** an operator who spots a suspicious payload,
- **I want** to type a “reject” response (optionally providing a note),
- **So that** the worker fails fast and the note is visible in logs for follow-up fixes.

**Acceptance Criteria**
1. Entering `reject --note "..."` (or similar syntax) aborts the run with an error referencing the note.
2. The rejected tool call, parameters, and note are written to stdout/stderr for later debugging.
3. Re-running the worker triggers the pause again instead of auto-approving anything by default.

## Story 4 — Edit worker config to preapprove known-safe tools
- **As** an operator who repeatedly approves the same safe tool calls,
- **I want** to edit the worker’s YAML definition (or creation profile) to mark specific tools/paths as preapproved,
- **So that** future CLI runs skip the interactive prompt for those actions while still blocking anything else.

**Acceptance Criteria**
1. Documentation explains how to set `tool_rules` (e.g., `sandbox.write` with certain sandboxes/paths) so the runtime executes them without prompting.
2. After editing the worker definition, rerunning the CLI shows that the specified tool executes automatically, while other tools still pause for approval.
3. Operators can revert or tighten the configuration easily if they notice unwanted behavior.

## Story 5 — Approve for the current session
- **As** an operator who trusts a request only for the current run,
- **I want** a quick CLI command (e.g., `approve --session`) that whitelists identical tool calls until the worker finishes,
- **So that** repeated calls with the same parameters during this terminal session don’t keep interrupting me, while future runs still require a fresh decision.

**Acceptance Criteria**
1. After issuing session approval, subsequent identical tool calls auto-execute during the active run without more prompts.
2. The session whitelist resets when the run ends (success, failure, or cancel); future runs revert to normal approval flow.
3. The CLI can list or revoke current session approvals (e.g., `session-approvals --list` or `--revoke key`).

## Story 6 — Auto-approve all tools for trusted development
- **As** a developer testing a worker I fully trust in a safe environment,
- **I want** a CLI flag (e.g., `--approve-all`) that automatically approves all tool calls without prompting,
- **So that** I can run workflows end-to-end without manual intervention during rapid iteration.

**Acceptance Criteria**
1. Passing `--approve-all` flag causes all approval-required tools to execute automatically without blocking.
2. The worker runs to completion without any approval prompts, even for writes and worker creation.
3. This mode is clearly documented as unsafe for untrusted workers or production use.

## Story 7 — Strict mode: reject unapproved tools
- **As** an operator running a worker in production or with untrusted code,
- **I want** a CLI flag (e.g., `--strict`) that rejects all tool calls not explicitly pre-approved in the worker config,
- **So that** the worker fails fast if it attempts any unexpected operations, ensuring security.

**Acceptance Criteria**
1. Passing `--strict` flag causes any approval-required tool to fail immediately with an error.
2. Only tools marked with `approval_required: false` in the worker's `tool_rules` execute successfully.
3. The error message clearly indicates which tool was rejected and that strict mode is active.
4. This provides a "deny by default" security posture for production deployments.
