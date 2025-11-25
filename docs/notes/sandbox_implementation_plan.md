# Sandbox Implementation Plan

**Status:** Planning
**Related:** [sandbox_architecture.md](sandbox_architecture.md), [pydanticai_contrib_sandbox.md](pydanticai_contrib_sandbox.md), [shell_tool_and_approval_patterns.md](shell_tool_and_approval_patterns.md), [runtime_refactor_with_di.md](runtime_refactor_with_di.md)

## Overview

Implement the two-layer sandbox architecture in 7 phases. Each phase is independently testable and deployable.

**Architecture:**
1. **FileSandbox** (reusable core) — File boundaries, query API, built-in I/O, LLM-friendly errors
2. **Sandbox** (llm-do extension) — Extends FileSandbox with network, OS enforcement, shell integration

**Goal:** Replace current `SandboxManager`/`SandboxToolset` with unified architecture that provides:
- Reusable FileSandbox for potential PydanticAI contribution
- llm-do Sandbox with OS-level enforcement and shell tool
- Pattern-based approval rules for shell commands

---

## Phase 1: Add FileSandbox Protocol

**Goal:** Define reusable interface without changing behavior.

### Tasks

1. **Add FileSandbox protocol to protocols.py**
   ```python
   class FileSandbox(Protocol):
       """Protocol for sandboxed file operations with LLM-friendly errors.

       This is the reusable core that could be contributed to PydanticAI.
       """
       def can_read(self, path: str) -> bool: ...
       def can_write(self, path: str) -> bool: ...
       def resolve(self, path: str) -> Path: ...
       def read(self, path: str, max_chars: int = 200_000) -> str: ...
       def write(self, path: str, content: str) -> None: ...
       def list_files(self, path: str = ".", pattern: str = "**/*") -> list[str]: ...
       @property
       def readable_roots(self) -> list[str]: ...
       @property
       def writable_roots(self) -> list[str]: ...
   ```

2. **Add FileSandboxError classes to new file_sandbox.py**
   - `FileSandboxError` (base)
   - `PathNotInSandboxError`
   - `PathNotWritableError`
   - `SuffixNotAllowedError`
   - `FileTooLargeError`

3. **Add FileSandboxConfig and PathConfig**
   ```python
   class PathConfig(BaseModel):
       root: str
       mode: Literal["ro", "rw"] = "ro"
       suffixes: Optional[list[str]] = None
       max_file_bytes: Optional[int] = None

   class FileSandboxConfig(BaseModel):
       paths: dict[str, PathConfig]
   ```

4. **Export from base.py and __init__.py**

### Tests
- Protocol can be imported
- Config classes validate correctly
- Error classes can be instantiated with LLM-friendly messages

### Deliverables
- [ ] `FileSandbox` protocol in protocols.py
- [ ] `FileSandboxConfig`, `PathConfig` in file_sandbox.py
- [ ] Error classes with LLM-friendly messages
- [ ] Exports updated
- [ ] All existing tests pass

---

## Phase 2: Implement FileSandbox Class

**Goal:** Create reusable FileSandbox implementation.

### Tasks

1. **Create llm_do/file_sandbox.py**
   ```python
   class FileSandboxImpl:
       """Reusable file sandbox implementation."""

       def __init__(self, config: FileSandboxConfig):
           self.config = config
           self._setup_paths()

       # Query API
       def can_read(self, path: str) -> bool
       def can_write(self, path: str) -> bool
       def resolve(self, path: str) -> Path  # raises FileSandboxError

       # Built-in I/O
       def read(self, path: str, max_chars: int = 200_000) -> str
       def write(self, path: str, content: str) -> None
       def list_files(self, path: str = ".", pattern: str = "**/*") -> list[str]

       # Application policies
       def check_suffix(self, path: Path) -> None
       def check_size(self, path: Path) -> None

       # Metadata for error messages
       @property
       def readable_roots(self) -> list[str]
       @property
       def writable_roots(self) -> list[str]
   ```

2. **Implement LLM-friendly error messages**
   - Each error includes list of valid alternatives
   - See sandbox_architecture.md "LLM-Friendly Errors"

3. **Handle path resolution**
   - Relative paths resolved against config roots
   - Absolute paths checked against boundaries
   - Symlinks resolved and re-checked

### Tests
- `can_read()` returns True for paths in readable areas
- `can_read()` returns False for paths outside
- `resolve()` raises `PathNotInSandboxError` with helpful message
- `read()` works for valid paths
- `write()` works for writable paths
- `write()` raises `PathNotWritableError` for read-only paths
- Suffix filtering works
- Size limits work

### Deliverables
- [ ] `FileSandboxImpl` class implementing `FileSandbox` protocol
- [ ] All query methods tested
- [ ] All I/O methods tested
- [ ] Error messages include alternatives

---

## Phase 3: Implement Sandbox (llm-do Extension)

**Goal:** Extend FileSandbox with llm-do specific features.

### Tasks

1. **Create llm_do/sandbox.py**
   ```python
   from .file_sandbox import FileSandboxImpl, FileSandboxConfig

   class SandboxConfig(FileSandboxConfig):
       """Extended configuration for llm-do sandbox."""
       network: bool = False
       require_os_sandbox: bool = False

   class Sandbox(FileSandboxImpl):
       """Extended sandbox with llm-do specific features."""

       def __init__(self, config: SandboxConfig):
           super().__init__(config)
           self.network_enabled = config.network
           self.require_os_sandbox = config.require_os_sandbox
   ```

2. **Update WorkerDefinition in types.py**
   - Add `sandbox: Optional[SandboxConfig]`
   - Keep `sandboxes` for backward compatibility (deprecated)

3. **Add migration logic in registry.py**
   - If old `sandboxes` format, convert to new `sandbox` format
   - Log deprecation warning

4. **Update example workers to new format**

### Tests
- Old format still loads (backward compat)
- New format loads correctly
- Deprecation warning logged for old format
- `network_enabled` and `require_os_sandbox` accessible

### Deliverables
- [ ] `SandboxConfig` extending `FileSandboxConfig`
- [ ] `Sandbox` class extending `FileSandboxImpl`
- [ ] `WorkerDefinition` updated
- [ ] Migration logic in registry
- [ ] Example workers updated
- [ ] Backward compatibility maintained

---

## Phase 4: Update tools.py

**Goal:** Use FileSandbox protocol for tool registration.

### Tasks

1. **Update register_worker_tools signature**
   ```python
   def register_worker_tools(
       agent: Agent,
       context: WorkerContext,
       delegator: WorkerDelegator,
       creator: WorkerCreator,
       sandbox: FileSandbox,  # Uses protocol, not Sandbox
   ) -> None:
   ```

2. **Replace sandbox_* tools with sandbox methods**
   ```python
   @agent.tool(name="read_file", description="Read text file from sandbox")
   def read_tool(ctx: RunContext, path: str) -> str:
       return sandbox.read(path)

   @agent.tool(name="write_file", description="Write text file to sandbox")
   def write_tool(ctx: RunContext, path: str, content: str) -> None:
       sandbox.write(path, content)

   @agent.tool(name="list_files", description="List files in sandbox")
   def list_tool(ctx: RunContext, path: str = ".", pattern: str = "**/*") -> list[str]:
       return sandbox.list_files(path, pattern)
   ```

3. **Keep old tool names as aliases (deprecated)**
   - `sandbox_read_text` → calls `sandbox.read()`
   - `sandbox_write_text` → calls `sandbox.write()`
   - `sandbox_list` → calls `sandbox.list_files()`

### Tests
- New tool names work
- Old tool names still work (with deprecation warning)
- Tools use FileSandbox protocol methods
- FileSandboxError propagates to tool result

### Deliverables
- [ ] `register_worker_tools` takes `FileSandbox` parameter
- [ ] New tool implementations
- [ ] Old tool names as deprecated aliases
- [ ] Tests updated

---

## Phase 5: Update runtime.py

**Goal:** Create Sandbox and inject into tools.

### Tasks

1. **Update run_worker_async**
   ```python
   async def run_worker_async(...) -> WorkerRunResult:
       definition = registry.load_definition(worker)

       # Create sandbox from definition
       sandbox_config = definition.sandbox or _default_sandbox_config()
       sandbox = Sandbox(sandbox_config)

       # Create protocol implementations
       delegator = RuntimeDelegator(context)
       creator = RuntimeCreator(context)

       # Tool registration with sandbox
       def register_tools_for_worker(agent, ctx):
           register_worker_tools(agent, ctx, delegator, creator, sandbox)

       # Run
       result = await default_agent_runner_async(...)
   ```

2. **Update run_worker (sync version)**

3. **Update WorkerContext if needed**
   - May need to store sandbox reference for attachments

### Tests
- Worker runs with new sandbox
- Tools can read/write via sandbox
- Error messages are LLM-friendly

### Deliverables
- [ ] `run_worker_async` creates and injects Sandbox
- [ ] `run_worker` creates and injects Sandbox
- [ ] Integration tests pass

---

## Phase 6: Add Shell Tool

**Goal:** Implement shell tool with pattern-based approval.

### Tasks

1. **Add ShellRule and ShellConfig types**
   ```python
   class ShellRule(BaseModel):
       pattern: str
       sandbox_paths: list[str] = []
       approval_required: bool = True
       allowed: bool = True

   class ShellConfig(BaseModel):
       rules: list[ShellRule] = []
       default_allowed: bool = True
       default_approval_required: bool = True
   ```

2. **Add shell_rules to WorkerDefinition**

3. **Implement shell tool in tools.py**
   ```python
   def shell(command: str, sandbox: Sandbox, timeout: int = 30) -> ShellResult:
       args = shlex.split(command)
       # Block shell metacharacters
       # Match against shell_rules
       # Check approval
       # Execute
       # Enhance errors with sandbox context
   ```

4. **Implement pattern matching**
   - Parse command with shlex
   - Match prefix against rules
   - Validate paths against sandbox_paths if specified

5. **Implement error enhancement**
   - Detect "Permission denied" → add writable_roots
   - Detect "Network unreachable" → add network status

### Tests
- Shell executes simple commands
- Pattern rules match correctly
- Approval required for unmatched commands
- Blocked commands rejected
- Error messages include sandbox context

### Deliverables
- [ ] `ShellRule`, `ShellConfig` types
- [ ] Shell tool implementation
- [ ] Pattern matching logic
- [ ] Error enhancement
- [ ] Tests for all scenarios

---

## Phase 7: OS Enforcement

**Goal:** Wrap shell commands in OS-level sandbox.

### Tasks

1. **Create os_sandbox.py module**
   ```python
   def os_sandbox_available() -> bool:
       """Check if OS sandbox is available on this platform."""

   def run_sandboxed(
       args: list[str],
       config: SandboxConfig,
       **kwargs
   ) -> subprocess.CompletedProcess:
       """Run command with OS-level sandbox."""
   ```

2. **Implement macOS Seatbelt**
   ```python
   def create_seatbelt_policy(config: SandboxConfig) -> str:
       """Generate Seatbelt policy string."""

   def run_with_seatbelt(args: list[str], policy: str, **kwargs) -> subprocess.CompletedProcess:
       """Run command with sandbox-exec."""
   ```

3. **Implement Linux bubblewrap**
   ```python
   def create_bwrap_args(config: SandboxConfig) -> list[str]:
       """Generate bwrap command prefix."""

   def run_with_bwrap(args: list[str], config: SandboxConfig, **kwargs) -> subprocess.CompletedProcess:
       """Run command with bwrap."""
   ```

4. **Update shell tool to use OS sandbox**
   ```python
   def shell(command: str, sandbox: Sandbox, timeout: int = 30) -> ShellResult:
       args = shlex.split(command)
       # ... validation ...

       if os_sandbox_available():
           result = run_sandboxed(args, sandbox.config, timeout=timeout)
       else:
           if sandbox.require_os_sandbox:
               raise SecurityError("OS sandbox required but unavailable")
           logger.warning("OS sandbox unavailable")
           result = subprocess.run(args, ...)

       return ShellResult(...)
   ```

5. **Handle fallback**
   - If OS sandbox unavailable and `require_os_sandbox=False`: warn and continue
   - If OS sandbox unavailable and `require_os_sandbox=True`: raise error

### Tests
- OS sandbox detection works
- Seatbelt policy generation (macOS only)
- bwrap args generation (Linux only)
- Fallback behavior
- Integration: command blocked by OS sandbox

### Deliverables
- [ ] `os_sandbox.py` module
- [ ] Seatbelt implementation (macOS)
- [ ] bwrap implementation (Linux)
- [ ] Shell tool updated
- [ ] Fallback handling
- [ ] Platform-specific tests

---

## Testing Strategy

### Unit Tests (per phase)
- Each phase has specific unit tests
- Mock dependencies where needed
- Test error messages for LLM-friendliness

### Integration Tests
- End-to-end worker execution with new sandbox
- Shell commands with pattern rules
- OS sandbox enforcement (platform-specific)

### Backward Compatibility Tests
- Old `sandboxes` config still works
- Old tool names still work
- Existing workers don't break

### Manual Testing
- Run example workers
- Test on both macOS and Linux
- Verify error messages are helpful

---

## Dependencies Between Phases

```
Phase 1 (FileSandbox Protocol)
    ↓
Phase 2 (FileSandbox Implementation)
    ↓
Phase 3 (Sandbox Extension) ←──┐
    ↓                          │
Phase 4 (tools.py)             │
    ↓                          │
Phase 5 (runtime.py)           │
    ↓                          │
Phase 6 (Shell) ───────────────┘ (can start after Phase 4)
    ↓
Phase 7 (OS enforcement)
```

Phase 6 (Shell) can be developed in parallel with Phase 5 after Phase 4 is complete.

---

## File Structure After Implementation

```
llm_do/
├── protocols.py          # FileSandbox protocol (reusable)
├── file_sandbox.py       # FileSandbox implementation + errors (reusable)
├── sandbox.py            # Sandbox extending FileSandbox (llm-do)
├── os_sandbox.py         # OS enforcement (llm-do)
├── tools.py              # Uses FileSandbox protocol
├── execution.py          # Unchanged
├── runtime.py            # Creates Sandbox, injects
└── types.py              # SandboxConfig, ShellConfig, etc.
```

**Reusable core (potential PydanticAI contrib):**
- `protocols.py` (FileSandbox protocol)
- `file_sandbox.py` (implementation, config, errors)

**llm-do specific:**
- `sandbox.py` (extends FileSandbox)
- `os_sandbox.py` (OS enforcement)
- Shell tool and pattern rules

---

## Estimated Effort

| Phase | Complexity | Estimated Size |
|-------|------------|----------------|
| 1. FileSandbox Protocol | Low | ~100 lines |
| 2. FileSandbox Implementation | Medium | ~250 lines |
| 3. Sandbox Extension | Low | ~100 lines |
| 4. tools.py update | Medium | ~200 lines |
| 5. runtime.py update | Low | ~100 lines |
| 6. Shell tool | High | ~400 lines |
| 7. OS enforcement | High | ~500 lines |

**Total:** ~1650 lines of new/modified code

---

## Discovered Architectural Issues

### Issue 1: OS Sandbox Only Covers Subprocesses

**Problem:** Seatbelt and bwrap wrap commands at spawn time. We cannot sandbox an already-running Python process.

**Impact:**
- `sandbox.read()`, `sandbox.write()` → Python validation only, NO OS enforcement
- `shell()` → OS enforcement (subprocess)
- Network blocking → Only works for shell commands

**Decision:** Accept this limitation for initial implementation. Document clearly. Application-level validation is the security boundary for Python I/O.

**Future option:** Spawn workers as subprocesses inside OS sandbox (significant architectural change).

### Issue 2: Nested Worker Sandbox Boundaries

**Problem:** When worker A calls worker B:
- Both run in same Python process
- Worker B has different sandbox config
- OS sandbox (if any) was set up for worker A

**Decision:** Each worker uses its own Sandbox instance for application-level validation. OS enforcement only applies to shell commands, which inherit the current process's restrictions.

### Issue 3: Shell Rules vs Tool Rules Precedence

**Problem:** Two places configure shell approval:
```yaml
tool_rules:
  shell:
    approval_required: true

shell_rules:
  - pattern: "git status"
    approval_required: false
```

**Decision:** Clear precedence order:
1. `tool_rules.shell.allowed` gates whether shell is available at all
2. `shell_rules` patterns override approval for matching commands
3. `shell_default` catches unmatched commands
4. Falls back to `tool_rules.shell.approval_required`

### Issue 4: Working Directory for Shell

**Problem:** If sandbox has multiple paths (`portfolio`, `pipeline`), what's the shell working directory?

**Decision:** Shell working directory defaults to **project root** (registry.root), not any specific sandbox path. Commands access sandbox paths via relative or absolute paths. This is consistent and predictable.

### Issue 5: Network Blocking Gap

**Problem:** `sandbox.network = false` only affects shell commands. Python code can still make HTTP requests.

**Decision:** Accept for initial implementation. Document that network blocking is for shell commands only. Future: full process sandboxing would close this gap.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing workers | Keep old config format working, deprecation warnings |
| OS sandbox not available | Graceful fallback with warning |
| Shell parsing edge cases | Use shlex, block metacharacters, conservative matching |
| Performance overhead | OS sandbox only wraps subprocesses, not per-call |
| Platform differences | Abstract behind os_sandbox.py, test on both platforms |
| **Python I/O not OS-enforced** | Accept limitation, rely on application validation |
| **Network gap for Python** | Document limitation, future: process sandboxing |
| **Nested worker confusion** | Clear docs, each worker has own Sandbox instance |

---

## Success Criteria

- [ ] All existing tests pass
- [ ] FileSandbox protocol and implementation complete (reusable)
- [ ] Sandbox extension complete (llm-do specific)
- [ ] Shell tool works with pattern rules
- [ ] OS enforcement works on macOS and Linux
- [ ] Error messages guide LLM to correct behavior
- [ ] Backward compatibility maintained
- [ ] Documentation updated
- [ ] Clean separation for potential PydanticAI contribution
