# Dynamic Sandbox Expansion - Design Notes

## Overview

Enable runtime expansion of sandbox boundaries when LLM requests access to files outside the configured sandbox. This is how Claude Code works - user approves access dynamically during the session.

## Motivation

**Current (static sandbox):**
- Paths configured upfront in worker definition
- Access outside configured paths → error
- User must know all needed paths before starting

**Desired (dynamic sandbox):**
- Start with configured paths (or empty)
- LLM requests access to file outside sandbox
- User prompted: "Allow read access to `/home/user/project/src/`?"
- If approved, sandbox expands for this session
- Subsequent accesses to that directory don't need re-approval

### Use Cases

1. **Interactive CLI** - LLM discovers it needs files user didn't anticipate
2. **Exploratory tasks** - "analyze this codebase" where files aren't known upfront
3. **Quick one-off tasks** - user doesn't want to configure sandbox for a simple task
4. **Pure analysis workers** - no pre-configured sandbox, all access approved dynamically

## Design Decisions

### Granularity: Per Directory

Approve entire directories, not individual files:
- "Allow read access to `/home/user/project/src/`?"
- Reduces approval fatigue
- More practical for real workflows
- Child paths automatically included

### Read/Write Separate

Separate approvals for read vs write access:
- Can approve read-only first
- Later approve write if needed
- Writes are more dangerous → natural escalation path

Example flow:
```
LLM: read_file("/home/user/project/src/main.py")
User: [Approve read access to /home/user/project/src/] ✓

LLM: write_file("/home/user/project/src/main.py", ...)
User: [Approve write access to /home/user/project/src/] ✓
```

### Approval Types: Once or Session

Uses existing ApprovalMemory pattern:
- **Once**: Approve this specific operation
- **Session**: Approve for remainder of session (stored in ApprovalMemory)

No persistent approval - dynamic expansion is session-scoped. For persistent access, user should update worker config.

## Security Model

**Decision: No built-in OS sandbox (bwrap/Seatbelt)**

The application-level sandbox validates paths in Python, but doesn't provide kernel-level isolation. This means:
- Toolset plugins can bypass the sandbox if they're malicious
- Shell commands execute with full filesystem access (only application-level validation)

**For users who need stronger isolation**: Run llm-do inside a Docker container with appropriate bind mounts and network settings. This is simpler and more portable than implementing bwrap/Seatbelt integration.

This decision simplifies dynamic expansion significantly - no process restart needed.

## Implementation

Since there's no OS sandbox, dynamic expansion is straightforward:

```python
class FileSystemToolset(AbstractToolset):
    def __init__(
        self,
        sandbox: Sandbox,
        dynamic_expansion: bool = False,
    ):
        self._sandbox = sandbox
        self._dynamic_expansion = dynamic_expansion
        self._expanded_paths: dict[str, PathConfig] = {}

    def needs_approval(self, name: str, tool_args: dict) -> bool | dict:
        path = tool_args.get("path", "")

        # Check if path is in configured sandbox
        try:
            self._sandbox.get_path_config(path)
            # Path is in sandbox - normal approval logic
            if name in ("write_file", "edit_file"):
                return {"description": f"Write to {path}"}
            return False
        except PathNotInSandboxError:
            pass

        # Path outside sandbox
        if not self._dynamic_expansion:
            raise PermissionError(f"Path not in sandbox: {path}")

        # Check if already expanded in this session
        directory = self._get_parent_directory(path)
        if directory in self._expanded_paths:
            config = self._expanded_paths[directory]
            if name in ("write_file", "edit_file") and config.mode != "rw":
                # Need write but only have read - request upgrade
                return {
                    "description": f"Upgrade to write access: {directory}",
                    "expansion": {"directory": directory, "mode": "rw"},
                }
            return False

        # Request expansion approval
        mode = "rw" if name in ("write_file", "edit_file") else "ro"
        return {
            "description": f"Allow {mode} access to: {directory}",
            "expansion": {"directory": directory, "mode": mode},
        }

    def approve_expansion(self, directory: str, mode: str) -> None:
        """Called when user approves expansion."""
        self._expanded_paths[directory] = PathConfig(root=directory, mode=mode)
        # No restart needed - just update in-memory state
```

## Configuration

```yaml
toolsets:
  sandbox:
    dynamic: true    # Enable runtime expansion
    paths:
      output: { root: ./output, mode: rw }  # Initial paths (optional)
  file_tools: true
```

For security-sensitive deployments, run in Docker:

```bash
docker run -v ./input:/workspace/input:ro \
           -v ./output:/workspace/output:rw \
           --network none \
           llm-do worker run my-worker
```

## Open Questions

1. **Default for dynamic?** - Should new workers default to `dynamic: false` (secure) or `dynamic: true` (convenient)?

2. **Directory inference** - When LLM accesses `/a/b/c/file.txt`, approve `/a/b/c/` or let user choose granularity?

3. **Expansion limits** - Should there be a max number of expansions per session? Or max depth from cwd?

4. **Audit trail** - Should expanded paths be logged/saved somewhere for user to review?

5. **Suggested config** - After session with expansions, offer to update worker config with approved paths?

## Related

- [Sandbox Toolset Separation Spec](sandbox-toolset-separation-v2.md) - Base architecture this builds on
- Claude Code's permission model - Inspiration for UX
