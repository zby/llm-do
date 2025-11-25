# Shell Tool and Pattern-Based Approvals

**Related:** See [sandbox_architecture.md](sandbox_architecture.md) for the unified sandbox model. This document focuses on the shell tool and approval UX.

## Context

With the unified sandbox architecture:
- **Sandbox** = OS-enforced execution environment (paths, network)
- **Shell** = just another tool operating within that sandbox
- **Pattern rules** = UX layer to reduce approval fatigue

The OS sandbox handles security (path boundaries, network blocking). Pattern rules handle UX (auto-approving known-safe commands).

## Motivation

A shell tool with simple approval (approve/reject per call) causes:
- Approval fatigue: `git status` requires approval every time
- Session approval by exact match: `git add file1.txt` ≠ `git add file2.txt`
- No way to express "auto-approve `git add` for files in the sandbox"

Pattern rules solve this by letting workers declare which command patterns are safe to auto-approve.

---

## Proposal

### Part 1: Shell Tool

Add `shell` as a built-in tool. It operates within the worker's sandbox (see sandbox_architecture.md).

**Tool signature:**
```python
def shell(
    command: str,
    working_dir: Optional[str] = None,  # sandbox name, defaults to project root
    timeout_seconds: int = 30,
) -> ShellResult:
    """Execute a shell command."""
```

**ShellResult:**
```python
class ShellResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    truncated: bool  # True if output exceeded limit
```

**Basic behavior:**
- Commands run via `subprocess` with `shell=False` (parsed via shlex)
- Output truncated at reasonable limit (e.g., 50KB)
- Timeout enforced
- Working directory defaults to project root (registry.root)
- If `working_dir` is a sandbox name, runs in that sandbox's root

**Worker configuration:**
```yaml
# workers/example.yaml
tool_rules:
  shell:
    allowed: true
    approval_required: true  # default: require approval for all shell calls
```

This gives us a working shell tool with the existing approval system. Every shell call requires approval (or session approval for exact command match).

---

### Part 2: Pattern-Based Approval Rules (Enhancement)

Extend the approval system to support command patterns, reducing approval fatigue for known-safe operations.

**New configuration in worker definition:**
```yaml
# workers/portfolio_orchestrator.yaml
shell_rules:
  # Harmless read-only commands - auto-approve
  - pattern: "git status"
    approval_required: false
  - pattern: "git log"
    approval_required: false
  - pattern: "git diff"
    approval_required: false

  # Commands with path arguments - validate against sandboxes
  - pattern: "git add"
    sandbox_paths: [portfolio]  # all path args must be in these sandboxes
    approval_required: false    # auto-approve if paths validate

  - pattern: "stat"
    sandbox_paths: [pipeline, portfolio]
    approval_required: false

  # Mutating commands - still require approval
  - pattern: "git commit"
    approval_required: true

  - pattern: "git push"
    approval_required: true

# Fallback for unmatched commands
shell_default:
  allowed: true           # or false for strict mode
  approval_required: true # prompt for anything not matching a rule
```

**Types:**
```python
class ShellRule(BaseModel):
    pattern: str                    # command prefix to match
    sandbox_paths: List[str] = []   # sandboxes for path argument validation
    approval_required: bool = True
    allowed: bool = True

class ShellConfig(BaseModel):
    rules: List[ShellRule] = []
    default_allowed: bool = True
    default_approval_required: bool = True
```

**Matching logic:**
1. Parse command with shlex
2. Match against rules in order (first match wins)
3. If rule has `sandbox_paths`:
   - Extract potential file paths from command arguments
   - Validate each path resolves within one of the allowed sandboxes
   - Block if any path escapes (treat as "no match", fall through to next rule)
4. Apply `allowed` and `approval_required` from matching rule
5. If no rule matches, apply defaults

**Path extraction heuristics:**
- Treat all non-flag arguments as potential paths
- Flag arguments start with `-` (skip these)
- For known commands (git, stat, ls), can use command-specific logic later
- Conservative: if unsure whether something is a path, treat it as one

---

## Implementation Plan

**Note:** OS-level sandboxing is covered in [sandbox_architecture.md](sandbox_architecture.md). This plan focuses on the shell tool and pattern rules.

### Phase 1: Basic Shell Tool
1. Add `shell` tool registration in `_register_worker_tools()`
2. Implement subprocess execution with timeout and output limits
3. Wire through existing `ApprovalController.maybe_run()`
4. Add `shell` to `tool_rules` schema
5. Test with simple commands

### Phase 2: Shell Rules Configuration
1. Add `ShellRule` and `ShellConfig` types
2. Add `shell_rules` and `shell_default` to `WorkerDefinition`
3. Implement rule matching in shell tool
4. Implement path extraction (basic heuristics)
5. Implement sandbox path validation

### Phase 3: Path Validation (for pattern rules with `sandbox_paths`)
1. Reuse `SandboxManager` for path resolution
2. Handle relative vs absolute paths
3. Handle symlinks (resolve and re-check)
4. Add tests for escape attempts

**Note:** This validation is for pattern rule matching, not security. The OS sandbox (see sandbox_architecture.md) provides the actual security boundary.

---

## Examples

### Git workflow for pitchdeck evaluator:
```yaml
name: portfolio_orchestrator
shell_rules:
  - pattern: "git status"
    approval_required: false
  - pattern: "git add"
    sandbox_paths: [portfolio]
    approval_required: false
  - pattern: "git commit -m"
    approval_required: true  # user reviews commit message
  - pattern: "stat"
    sandbox_paths: [pipeline]
    approval_required: false  # for file modification times
shell_default:
  allowed: false  # block anything else
```

### What this enables:
```
# Auto-approved (matches rule, paths in sandbox):
git status
git add portfolio/Acme/Acme-Evaluation.md
stat pipeline/deck.pdf

# Requires approval (rule says so):
git commit -m "Add Acme evaluation"

# Blocked (no matching rule, default disallows):
rm -rf /
curl http://evil.com
```

---

## Security Notes

**Pattern rules are UX, not security.**

The OS sandbox (see [sandbox_architecture.md](sandbox_architecture.md)) provides the security boundary. Pattern rules only reduce approval fatigue.

| Layer | Purpose | Can be bypassed by |
|-------|---------|-------------------|
| Pattern rules | UX | Prompt injection crafting matching commands |
| OS sandbox | Security | Kernel exploit or misconfiguration |

**What pattern rules help with:**
- Avoiding approval fatigue (auto-approve `git status`)
- Reducing rubber-stamping of dangerous operations
- Making safe operations frictionless

**What pattern rules do NOT provide:**
- Security guarantees
- Protection against prompt injection
- Path escape prevention (that's the OS sandbox's job)

---

## Pattern Rules vs Sandbox Permissions

**Important:** Pattern rules control **approval UX**, not **sandbox permissions**.

With static sandbox (MVP design):
- Sandbox permissions are fixed in worker config
- Pattern rules only decide: does user see an approval prompt?
- Commands that exceed sandbox permissions fail regardless of approval

**Example: `git push` needs network**

```yaml
sandbox:
  network: false  # no network access

shell_rules:
  - pattern: "git push"
    approval_required: true
```

What happens:
1. LLM runs `git push`
2. Pattern rule matches → approval prompt shown
3. User approves
4. Command runs → **fails** (network blocked by OS sandbox)

**To make `git push` work:**

```yaml
sandbox:
  network: true  # enable network for this worker

shell_rules:
  - pattern: "git push"
    approval_required: true  # still require approval for visibility
```

**Future: Dynamic grants**

Later, pattern rules might grant sandbox permissions:

```yaml
# FUTURE - not implemented yet
shell_rules:
  - pattern: "git push"
    approval_required: true
    grants:
      network: true  # if approved, enable network for this command only
```

See [sandbox_architecture.md](sandbox_architecture.md) for details on static vs dynamic sandbox.

---

## Design Decisions (Start Simple)

| Question | Decision | Future Extension |
|----------|----------|------------------|
| **Command parsing** | `shlex.split()` with `shell=False`. Block commands containing shell metacharacters (`|`, `>`, `<`, `;`, `&`, `` ` ``, `$(`). | Later: whitelist specific patterns that need pipes, or add a `shell=True` mode with explicit opt-in. |
| **Working directory** | Default to project root (registry.root). | Later: allow specifying sandbox name as working dir. |
| **Environment variables** | Inherit current environment unchanged. | Later: filter to allowlist, or provide explicit env dict in config. |
| **Output handling** | Wait for completion, capture stdout/stderr, truncate at limit. | Later: streaming for long-running commands, progress callbacks. |
| **Windows support** | Linux/macOS only initially. Document limitation. | Later: use `shlex` with `posix=False`, handle cmd.exe differences. |
| **Pattern matching** | Simple prefix match (e.g., "git add" matches "git add foo.txt"). | Later: glob patterns, regex for complex matching. |
| **Sandbox grants** | Pattern rules control approval only, not sandbox permissions. | Later: `grants` field to enable permissions per-command. |

**OS sandbox decisions** are in [sandbox_architecture.md](sandbox_architecture.md).
