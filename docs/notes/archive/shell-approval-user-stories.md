# Shell Approval User Stories

## Overview

User stories for shell command approval in llm-do. These help clarify the different scenarios and expected behaviors.

## Personas

- **Developer**: Using llm-do for coding tasks, wants convenience
- **Security-conscious user**: Running untrusted workers, wants protection
- **Power user**: Knows what they're doing, wants minimal friction

---

## Story 1: Pre-approved safe commands

**As a** developer
**I want** common read-only commands pre-approved
**So that** the LLM can explore the codebase without constant prompts

```yaml
toolsets:
  shell:
    rules:
      - pattern: "ls "
        approval_required: false
      - pattern: "cat "
        approval_required: false
      - pattern: "git status"
        approval_required: false
      - pattern: "git diff"
        approval_required: false
```

**Acceptance criteria:**
- `ls -la src/` executes without prompt
- `cat README.md` executes without prompt
- `rm file.txt` still requires approval

---

## Story 2: Dangerous commands blocked entirely

**As a** security-conscious user
**I want** destructive commands blocked (not just prompted)
**So that** even if I accidentally approve, damage is prevented

```yaml
toolsets:
  shell:
    rules:
      # Only whitelist safe commands - dangerous ones are blocked by omission
      - pattern: "rm "
        approval_required: true  # Single file rm allowed with approval
      # rm -rf, sudo, chmod 777 NOT in rules = blocked
    default:
      approval_required: true
```

**Acceptance criteria:**
- `rm -rf /` returns error immediately (not in rules, doesn't match "rm " pattern due to first-match)
- `sudo apt install` returns error immediately (not in rules)
- `rm single-file.txt` prompts for approval (matches "rm " rule)

**Note:** Whitelist model - dangerous commands are blocked by NOT including them in rules.

---

## Story 3: Restrict file commands to sandbox

**As a** developer
**I want** file-reading commands limited to my project directory
**So that** the LLM doesn't accidentally read sensitive files

```yaml
toolsets:
  sandbox:
    paths:
      project: { root: ./src, mode: ro }
      output: { root: ./output, mode: rw }
  shell:
    rules:
      - pattern: "cat "
        sandbox_paths: [project, output]
        approval_required: false
      - pattern: "head "
        sandbox_paths: [project, output]
        approval_required: false
    default:
      approval_required: true
```

**Acceptance criteria:**
- `cat src/main.py` executes (in project sandbox)
- `cat /etc/passwd` falls through to default, requires approval
- `cat ~/.ssh/id_rsa` requires approval (not in sandbox_paths)

**Open question:** Should out-of-sandbox paths be blocked or just require approval?

---

## Story 4: Git commands - read vs write

**As a** developer
**I want** read-only git commands pre-approved, but commits/pushes prompted
**So that** the LLM can explore freely but I review changes before they're permanent

```yaml
toolsets:
  shell:
    rules:
      # Read-only - pre-approve
      - pattern: "git status"
        approval_required: false
      - pattern: "git diff"
        approval_required: false
      - pattern: "git log"
        approval_required: false
      - pattern: "git branch"
        approval_required: false
      - pattern: "git show"
        approval_required: false
      # Staging - maybe pre-approve (reversible)
      - pattern: "git add"
        approval_required: false
      # Modifications - require approval
      - pattern: "git commit"
        approval_required: true
      - pattern: "git push"
        approval_required: true
      - pattern: "git reset"
        approval_required: true
      - pattern: "git checkout"
        approval_required: true
      - pattern: "git rebase"
        approval_required: true
```

**Acceptance criteria:**
- `git status` executes without prompt
- `git diff HEAD~1` executes without prompt
- `git add .` executes without prompt (staging is reversible)
- `git commit -m "..."` **prompts for approval**
- `git push origin main` **prompts for approval**

**Note:** Git accesses many files implicitly. Path validation doesn't make sense here. The read/write distinction is about repository state, not file access.

---

## Story 5: Network commands require approval

**As a** security-conscious user
**I want** network commands to always require approval
**So that** I can review what data might be sent externally

```yaml
toolsets:
  shell:
    rules:
      - pattern: "curl "
        approval_required: true
      - pattern: "wget "
        approval_required: true
      # ssh NOT in rules = blocked (whitelist model)
```

**Acceptance criteria:**
- `curl https://example.com` prompts with full URL visible
- `wget http://malicious.com/script.sh` prompts for approval
- `ssh user@host` blocked entirely (not in rules)

---

## Story 6: Build commands pre-approved

**As a** developer
**I want** build/test commands pre-approved
**So that** the LLM can iterate quickly on code changes

```yaml
toolsets:
  shell:
    rules:
      - pattern: "npm "
        approval_required: false
      - pattern: "pytest "
        approval_required: false
      - pattern: "make "
        approval_required: false
      - pattern: "cargo "
        approval_required: false
```

**Acceptance criteria:**
- `npm install` executes without prompt
- `pytest tests/` executes without prompt
- `make build` executes without prompt

**Risk:** These commands can execute arbitrary code (postinstall scripts, Makefiles). User accepts this risk by pre-approving.

---

## Story 7: Default deny for unknown commands

**As a** security-conscious user
**I want** unknown commands blocked by default
**So that** only explicitly allowed commands can run

```yaml
toolsets:
  shell:
    rules:
      - pattern: "ls "
        approval_required: false
      - pattern: "cat "
        approval_required: false
    # NO default section = block everything not in rules (whitelist model)
```

**Acceptance criteria:**
- `ls -la` executes without prompt
- `cat file.txt` executes without prompt
- `echo hello` blocked (not in rules, no default)
- `python script.py` blocked

---

## Story 8: Approval with session memory

**As a** developer
**I want** to approve a command once for the session
**So that** repeated similar commands don't need re-approval

```yaml
# Uses ApprovalMemory from pydantic-ai-blocking-approval
```

**Acceptance criteria:**
- First `python script.py` prompts for approval
- User approves with "session" option
- Second `python script.py` executes without prompt
- `python other_script.py` may still prompt (depending on memory key)

**Open question:** What's the memory key? Exact command? Command prefix? Tool name only?

---

## Story 9: Docker-based isolation

**As a** security-conscious user
**I want** kernel-level isolation
**So that** even approved commands can't escape the sandbox

```bash
docker run \
  -v ./src:/workspace/src:ro \
  -v ./output:/workspace/output:rw \
  --network none \
  llm-do worker run code-analyzer
```

**Acceptance criteria:**
- Shell commands can only access mounted paths
- Network is disabled at kernel level
- Even `cat /etc/passwd` inside container is isolated

**Note:** This is user's responsibility, not llm-do's implementation.

---

## Story 10: YOLO mode for Docker environments

**As a** developer running in Docker
**I want** nearly everything pre-approved
**So that** the LLM can work autonomously (container is my security boundary)

```yaml
toolsets:
  shell:
    # No rules needed - default allows everything
    default:
      approval_required: false  # <-- Pre-approve all commands
```

Or via CLI flag:

```bash
# Inside Docker container
llm-do worker run code-analyzer --approve-all

# Or environment variable
LLM_DO_APPROVE_ALL=1 llm-do worker run code-analyzer
```

**Acceptance criteria:**
- `rm -rf /tmp/stuff` executes without prompt
- `curl https://api.example.com` executes without prompt
- `git commit -m "..."` executes without prompt
- `git push` executes without prompt

**Note:** With whitelist model, YOLO mode is achieved via permissive default, not by blocking specific commands. Container isolation is the security boundary.

**Use case:**
```bash
# User's workflow
docker run --rm -it \
  -v $(pwd):/workspace \
  -w /workspace \
  --network host \
  llm-do-image \
  llm-do worker run autonomous-coder --approve-all
```

**Security model:** Container = security boundary. Everything inside is fair game.

**Warning:** Should probably print a warning when `--approve-all` is used:
```
⚠️  Running in approve-all mode. All tool calls will be auto-approved.
    Only use this in isolated environments (Docker, VM, etc.)
```

---

## Story 11: Audit trail for shell commands

**As a** security-conscious user
**I want** all shell commands logged
**So that** I can review what was executed after the fact

**Acceptance criteria:**
- Every shell command logged with timestamp
- Approval decision logged (approved/rejected/pre-approved)
- Exit code and output summary logged

**Status:** Partially implemented via message callback?

---

## Open Questions

1. **Memory key granularity**: Should session approval be per exact command, per command prefix, or per tool?

2. **Path validation default**: Should `sandbox_paths` validation be opt-in (current) or opt-out?

3. **Output visibility**: Should user see command output before approving next command? (Currently yes, via streaming)

4. **Timeout handling**: Long-running commands - should there be a way to cancel mid-execution?

---

## Summary Matrix (Whitelist Model)

| Scenario | In rules? | Has default? | Result |
|----------|-----------|--------------|--------|
| Safe read commands | Yes (approval_required: false) | - | Pre-approved |
| Dangerous commands | No | No | **Blocked** |
| Dangerous commands | No | Yes | Falls through to default |
| File commands in sandbox | Yes (with sandbox_paths) | - | Allowed if path validates |
| Git/build commands | Yes (approval_required: false) | - | Pre-approved |
| Network commands | Yes (approval_required: true) | - | Requires approval |
| Unknown commands | No | Yes | Default's approval_required |
| Unknown commands | No | No | **Blocked** |
