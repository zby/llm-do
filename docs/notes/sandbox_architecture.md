# Sandbox Architecture

## Overview

Sandbox is the **execution environment** for a worker, not just configuration for file tools. All tools (read, write, shell, etc.) operate within this environment.

```
┌─────────────────────────────────────┐
│ Sandbox (OS-enforced environment)   │
│                                     │
│  Readable: ./portfolio, ./pipeline  │
│  Writable: ./portfolio              │
│  Network:  blocked                  │
│                                     │
│  ┌─────────────────────────────────┐│
│  │ Worker process                  ││
│  │  ├── read_text                  ││
│  │  ├── write_text                 ││
│  │  ├── list_files                 ││
│  │  ├── shell        ← just a tool ││
│  │  └── worker_call                ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

## Motivation

**Current state:** Multiple overlapping concepts
- `SandboxConfig` - per-path config for `sandbox_*` tools
- `AttachmentPolicy` - controls files passed to sub-workers
- (Proposed) OS sandbox for shell commands

**Problem:** Adding shell tool requires "another sandbox" - confusing.

**Solution:** Unify into single sandbox concept that:
1. Defines the execution environment (paths, network)
2. Is enforced at OS level (kernel boundaries)
3. All tools operate within it

---

## Architecture

### Two Layers

| Layer | Responsibility | Enforcement |
|-------|----------------|-------------|
| **Sandbox environment** | Path boundaries, network access | OS kernel (Seatbelt/bwrap) |
| **Application policies** | Suffix filters, size limits, approval UX | Python code |

The OS sandbox is the **security boundary**. Application policies provide **fine-grained control** within that boundary.

### Sandbox Configuration

```yaml
name: portfolio_orchestrator

sandbox:
  # Paths accessible to this worker
  paths:
    portfolio:
      root: ./portfolio
      mode: rw                    # read-write
      suffixes: [.md, .pdf]       # application filter (not OS-enforced)
      max_file_bytes: 10000000    # application limit
    pipeline:
      root: ./pipeline
      mode: ro                    # read-only
      suffixes: [.pdf]
    framework:
      root: ./framework
      mode: ro
      suffixes: [.md]

  # Network access
  network: false                  # OS-enforced

  # What happens if OS sandbox unavailable
  require_os_sandbox: false       # warn and continue, or fail?

# Attachment policy (for sub-worker calls)
attachment_policy:
  max_count: 5
  max_total_bytes: 15000000
  # Attachments must come from readable paths (enforced by sandbox)

# Tool-specific rules (approval UX, not security)
tool_rules:
  shell:
    approval_required: true
  write_text:
    approval_required: false
```

### Tools Within Sandbox

Tools no longer configure their own paths - they inherit from sandbox:

| Tool | Behavior |
|------|----------|
| `read_text(path)` | Read from any readable sandbox path |
| `write_text(path, content)` | Write to any writable sandbox path |
| `list_files(path, pattern)` | List files in any readable sandbox path |
| `shell(command)` | Execute command, inherits sandbox restrictions |
| `worker_call(worker, attachments)` | Attachments must be from readable paths |

**Rename consideration:**
- `sandbox_read_text` → `read_text` (sandbox is implicit)
- `sandbox_write_text` → `write_text`
- `sandbox_list` → `list_files`

---

## OS Sandbox Implementation

### macOS: Apple Seatbelt

```python
def create_seatbelt_policy(sandbox_config) -> str:
    readable = [p.root for p in sandbox_config.paths.values()]
    writable = [p.root for p in sandbox_config.paths.values() if p.mode == 'rw']

    policy = """
(version 1)
(deny default)

; Read access
(allow file-read*)

; Write access - only to declared writable paths
{writable_rules}

; Network
{network_rule}

; Process management
(allow process-fork)
(allow process-exec)
(allow signal (target self))
"""
    # Generate (allow file-write* (subpath "...")) for each writable path
    ...
```

### Linux: bubblewrap

```python
def create_bwrap_command(sandbox_config, command) -> List[str]:
    readable = [p.root for p in sandbox_config.paths.values()]
    writable = [p.root for p in sandbox_config.paths.values() if p.mode == 'rw']

    bwrap = ["bwrap"]

    # Read-only bind for all readable paths
    for path in readable:
        if path not in writable:
            bwrap.extend(["--ro-bind", path, path])

    # Read-write bind for writable paths
    for path in writable:
        bwrap.extend(["--bind", path, path])

    # Block network
    if not sandbox_config.network:
        bwrap.append("--unshare-net")

    bwrap.extend(["--die-with-parent", "--"])
    bwrap.extend(command)

    return bwrap
```

### Fallback: Application-Only

When OS sandbox is unavailable:
```python
if not os_sandbox_available():
    if sandbox_config.require_os_sandbox:
        raise SecurityError("OS sandbox required but unavailable")
    else:
        logger.warning("OS sandbox unavailable, using application-level checks only")
```

---

## Runtime Flow

### Worker Startup

```python
def run_worker(worker_def, input_data, ...):
    sandbox = worker_def.sandbox

    # 1. Create OS sandbox environment
    os_sandbox = create_os_sandbox(sandbox)

    # 2. Run worker inside sandbox
    with os_sandbox:
        # 3. Register tools (they inherit sandbox context)
        agent = create_agent(worker_def)
        register_tools(agent, sandbox)

        # 4. Execute
        return agent.run(input_data)
```

### Tool Execution

```python
def read_text(ctx, path: str) -> str:
    sandbox = ctx.sandbox

    # 1. Resolve path within sandbox
    resolved = sandbox.resolve_path(path)  # validates path is in readable area

    # 2. Apply application policies
    sandbox.check_suffix(resolved)
    sandbox.check_size(resolved)

    # 3. Read file (OS sandbox also enforces, defense in depth)
    return resolved.read_text()

def shell(ctx, command: str) -> ShellResult:
    # 1. Parse command
    args = shlex.split(command)

    # 2. Check approval (UX layer)
    ctx.approval_controller.maybe_approve("shell", {"command": command})

    # 3. Execute (OS sandbox enforces path/network restrictions)
    result = subprocess.run(args, capture_output=True, timeout=30)

    return ShellResult(
        stdout=result.stdout.decode(),
        stderr=result.stderr.decode(),
        exit_code=result.returncode
    )
```

### Attachment Loading

```python
def load_attachment(ctx, path: str) -> AttachmentPayload:
    sandbox = ctx.sandbox

    # 1. Resolve path (must be in readable area)
    resolved = sandbox.resolve_path(path)  # OS also enforces this

    # 2. Check attachment policy
    ctx.attachment_policy.validate(resolved)

    # 3. Return payload
    return AttachmentPayload(path=resolved, ...)
```

---

## Migration Path

### Phase 1: Refactor Config (No OS Sandbox Yet)

1. Rename `sandboxes` (plural) → `sandbox` (singular)
2. Nest path configs under `sandbox.paths`
3. Add `sandbox.network` (unused initially)
4. Keep application-level enforcement

```yaml
# Before
sandboxes:
  portfolio:
    path: ./portfolio
    mode: rw

# After
sandbox:
  paths:
    portfolio:
      root: ./portfolio
      mode: rw
```

### Phase 2: Add Shell Tool

1. Add `shell` tool (see shell_tool_and_approval_patterns.md)
2. Pattern rules for approval UX
3. Still application-level only

### Phase 3: OS Sandbox

1. Implement Seatbelt wrapper (macOS)
2. Implement bwrap wrapper (Linux)
3. Wrap worker execution in OS sandbox
4. Shell commands automatically restricted

### Phase 4: Cleanup

1. Rename tools: `sandbox_read_text` → `read_text`
2. Update documentation
3. Deprecate old config format

---

## Comparison with Codex

| Aspect | Codex | llm-do (proposed) |
|--------|-------|-------------------|
| Sandbox modes | 3 presets (read-only, workspace-write, full-access) | Explicit path config |
| Granularity | Coarse (all or nothing) | Fine (per-path mode) |
| OS enforcement | Seatbelt, Landlock | Seatbelt, bwrap |
| Network control | Binary (on/off) | Binary (on/off) |
| Approval UX | 3-tier model | Pattern rules |
| Application filters | None | Suffix, size limits |

Our approach is more flexible (explicit paths vs presets) while using similar OS mechanisms.

---

## Sandbox and Approval Interaction

### The Question

Should sandbox permissions be static (defined in config) or dynamic (adjusted based on approvals)?

**Scenario:** Worker has `network: false`, LLM runs `git push`

| Approach | Behavior |
|----------|----------|
| Static | Command fails (network blocked). User must edit config. |
| Dynamic | Approval prompt shows "git push (requires network)". If approved, sandbox enables network for this call. |

### Decision: Static First, Dynamic Later

**Phase 1 (MVP): Static sandbox**
- Sandbox policy defined in worker config
- If command needs more permissions, it fails
- User must configure worker appropriately
- Simple to implement and reason about

**Phase 2 (Future): Dynamic grants**
- Pattern rules can specify additional permissions
- Approval UI shows what's being granted
- Per-command sandbox policy

```yaml
# Future: pattern rules with grants
shell_rules:
  - pattern: "git push"
    approval_required: true
    grants:
      network: true  # if approved, enable network for this command

  - pattern: "curl"
    approval_required: true
    grants:
      network: true

  - pattern: "git status"
    approval_required: false
    grants: {}  # no extra permissions
```

**Why static first:**
1. Simpler mental model - sandbox is what's in config
2. Easier to audit - permissions visible in YAML
3. Less attack surface - no runtime permission escalation
4. Forces explicit configuration - user thinks about what worker needs

**When dynamic might be needed:**
- Workers that occasionally need network (git push, API calls)
- Interactive workflows where user grants permissions on demand
- Reducing config duplication across similar workers

### Implications for Current Design

With static sandbox:
- Worker config must declare ALL permissions it might need
- Pattern rules only control approval UX, not sandbox policy
- Commands exceeding sandbox fail with clear error

```yaml
# Worker that needs occasional network access
sandbox:
  paths:
    portfolio: { root: ./portfolio, mode: rw }
  network: true  # must enable if ANY command needs it

tool_rules:
  shell:
    approval_required: true  # user still approves commands
```

The downside: enabling `network: true` allows ALL commands to use network, not just approved ones. This is the tradeoff of static sandbox - coarser granularity for simpler model.

---

## Open Questions

1. **Tmpdir handling**: Should `/tmp` always be writable? Or explicit in config?

2. **Home directory**: Allow `~/.config`, `~/.cache` access? Security vs practicality.

3. **Tool inheritance**: When worker_call delegates, does child inherit parent's sandbox or use its own?

4. **Sandbox composition**: Can a child have MORE permissions than parent? (Probably no)

5. **Debugging**: How to run without sandbox for debugging? `--no-sandbox` flag?

6. **Dynamic grants priority**: When/if to implement dynamic grants based on real usage patterns.
