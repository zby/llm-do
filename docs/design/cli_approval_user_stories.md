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
- **I want** to edit the worker’s YAML definition (or creation defaults config) to mark specific tools/paths as preapproved,
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

---

## Story 8 — Approve shell commands individually
- **As** an operator watching a worker execute shell commands,
- **I want** to see the exact command and approve or reject it before execution,
- **So that** I can prevent destructive or unexpected shell operations.

**Acceptance Criteria**
1. When the worker requests a shell command that requires approval, the CLI pauses and displays the full command string.
2. The operator can approve, approve for session (identical commands auto-execute), deny, or quit.
3. Shell commands that match pre-approved `shell_rules` patterns execute without prompting.
4. Rejected shell commands return an error result to the worker, allowing it to handle the failure gracefully.

## Story 9 — Pre-approve shell commands by pattern
- **As** an operator who repeatedly approves the same safe commands (e.g., `git status`, `ls`),
- **I want** to define `shell_rules` patterns in the worker definition that auto-approve matching commands,
- **So that** known-safe commands execute without interruption while novel commands still require approval.

**Acceptance Criteria**
1. Worker definition supports `shell_rules` as a list of pattern-based rules with `approval_required` flags.
2. Commands matching a rule with `approval_required: false` execute immediately without prompting.
3. Commands matching a rule with `allowed: false` fail immediately with a clear error.
4. `shell_default` specifies behavior for commands not matching any rule.
5. Rule matching uses prefix-based patterns (e.g., `git status` matches `git status --short`).

## Story 10 — Block dangerous shell commands entirely
- **As** an operator who wants to prevent certain commands from ever running,
- **I want** to mark specific shell patterns as `allowed: false` in the worker definition,
- **So that** the worker cannot execute destructive commands even if it tries.

**Acceptance Criteria**
1. Shell rules with `allowed: false` cause immediate rejection without prompting.
2. The error message clearly states the command was blocked by policy.
3. The worker receives the error and can adjust its approach.
4. Blocked commands are logged for audit purposes.

## Story 11 — Approve worker creation before saving
- **As** an operator whose worker wants to create a new sub-worker,
- **I want** to review the proposed worker definition before it's saved to disk,
- **So that** I can verify the new worker has appropriate permissions and instructions.

**Acceptance Criteria**
1. When `worker_create` is invoked, the CLI pauses and displays the proposed worker name and metadata.
2. The operator can approve (save to disk), deny (abort), or quit.
3. Denied creation returns an error to the calling worker.
4. Approved workers are saved and immediately available for use.
5. The `worker.create` tool rule controls whether creation requires approval.

## Story 12 — Approve worker delegation with context
- **As** an operator monitoring a worker that delegates to other workers,
- **I want** to see which worker is being called, with what input, and any attachments being passed,
- **So that** I can verify the delegation is appropriate before it executes.

**Acceptance Criteria**
1. When `worker_call` requires approval, the CLI displays: target worker name, input data, and attachment metadata.
2. The operator can approve, approve for session, deny, or quit.
3. Session approval applies to identical calls (same worker, input, and attachments).
4. Workers in the `allow_workers` list that have `approval_required: false` in tool rules execute without prompting.

## Story 13 — Approve file sharing between workers
- **As** an operator whose worker passes file attachments to a sub-worker,
- **I want** to approve each file being shared before it's transferred,
- **So that** I can prevent sensitive files from being inadvertently exposed to other workers.

**Acceptance Criteria**
1. When attachments are passed to `worker_call`, each file triggers a `sandbox.read` approval check.
2. The prompt shows: file path, size in bytes, and the target worker receiving the file.
3. The operator can approve, approve for session (same file + target), deny, or quit.
4. Denying any attachment aborts the entire delegation call.
5. If `sandbox.read` is pre-approved in tool rules, attachments transfer without prompting.

## Story 14 — See approval history in session
- **As** an operator who has approved several tools during a long-running session,
- **I want** to understand which approvals are currently active for the session,
- **So that** I know what will auto-execute and what will still prompt.

**Acceptance Criteria**
1. Session approvals (from choosing `[s]`) are tracked by tool name and exact payload.
2. The CLI can display currently active session approvals when requested.
3. Only identical tool calls (same name and arguments) benefit from session approval.
4. Session approvals reset when the worker run completes.

## Story 15 — Non-interactive runs require explicit mode
- **As** an operator running `llm-do` in a script or CI pipeline without a TTY,
- **I want** the CLI to fail clearly if neither `--approve-all` nor `--strict` is specified,
- **So that** I'm not surprised by a hanging process waiting for input that will never come.

**Acceptance Criteria**
1. When stdin is not a TTY and no approval flag is provided, the CLI exits with a clear error.
2. The error message explains that `--approve-all` or `--strict` is required for non-interactive use.
3. Both flags cannot be used together (mutually exclusive).
4. The exit code is non-zero to signal failure to calling scripts.
