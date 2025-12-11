# Program-Level Sandbox Configuration

## Goal
Move sandbox configuration from worker definitions to `program.yaml`, following golem-forge's pattern. Workers should inherit the program sandbox and can only restrict access further (not expand it).

## Background

**Current llm-do design:**
- Each worker defines its own `sandbox` config
- No program-level sandbox default
- Workers can define arbitrary sandbox paths

**Golem-forge design:**
- Program defines `sandbox.root` (relative to program root)
- Workers can only `restrict` to a subtree and/or make `readonly`
- Workers cannot expand access beyond program sandbox

## Golem-Forge Syntax

### Program-Level (golem-forge.config.yaml)
```yaml
sandbox:
  root: "."         # Relative to program root, mounted at /
  readonly: false   # Optional, default false
```

### Worker-Level (in .worker frontmatter)
```yaml
sandbox:
  restrict: "/src"   # Restrict to subtree (must start with /)
  readonly: true     # Make read-only (can only downgrade, never upgrade)
```

### Semantics

| Field | Location | Description |
|-------|----------|-------------|
| `root` | Program only | Relative path from program root that becomes virtual `/` |
| `readonly` | Both | Makes sandbox read-only; can only be made more restrictive |
| `restrict` | Worker only | Limits worker to a subtree (e.g., `/src`) |

### Permission Inheritance Rules

| Parent State | Worker Requests | Result | Allowed? |
|--------------|-----------------|--------|----------|
| read-write | (default) | read-write | Yes |
| read-write | `readonly: true` | read-only | Yes (downgrade) |
| read-only | (default) | read-only | Yes (inherit) |
| read-only | `readonly: false` | ERROR | No (escalation blocked) |

## Tasks

### Phase 1: Schema Updates
- [ ] Add `SandboxProgramConfig` to types.py with `root` and `readonly` fields
- [ ] Update `ProgramConfig.sandbox` to use `SandboxProgramConfig` type
- [ ] Add `WorkerSandboxConfig` with `restrict` and `readonly` fields
- [ ] Update `WorkerDefinition.sandbox` to use `WorkerSandboxConfig` type

### Phase 2: Resolution Logic
- [ ] Add `resolve_sandbox_config()` in program.py:
  - Takes program root path and `SandboxProgramConfig`
  - Returns absolute path for sandbox root
  - Validates root exists and is within program
- [ ] Add `create_child_sandbox()` function:
  - Takes parent sandbox and worker's `WorkerSandboxConfig`
  - Applies `restrict` by changing root path
  - Applies `readonly` (can only downgrade)
  - Raises error on permission escalation attempt

### Phase 3: Runtime Integration
- [ ] Update `_prepare_worker_context()` in runtime.py:
  - Get program sandbox config from registry
  - Resolve to absolute sandbox
  - Apply worker restrictions via `create_child_sandbox()`
- [ ] Update delegation (`call_worker`, `call_worker_async`):
  - Pass parent sandbox to child
  - Child applies its own restrictions

### Phase 4: Migration
- [ ] Deprecate old worker-level `sandbox` field format
- [ ] Add migration guide in docs
- [ ] Update existing examples to use program-level sandbox

## Open Questions

1. **Backwards compatibility**: What happens to workers with old-style sandbox config?
   - Option A: Error immediately (breaking)
   - Option B: Warn and treat as program-level (if no program sandbox)
   - Option C: Ignore worker sandbox if program sandbox exists
   - **Recommendation**: Option B for smooth migration

2. **No program sandbox**: What if program.yaml has no sandbox config?
   - Option A: No filesystem access (most secure)
   - Option B: Default to `root: "."` (convenient)
   - **Recommendation**: Option A (explicit is better)

3. **Single-file mode**: What sandbox does a standalone `.worker` file get?
   - Option A: No sandbox (no program context)
   - Option B: Default to file's parent directory
   - **Recommendation**: Option A (consistent with golem-forge)

## Example Configuration

### program.yaml
```yaml
name: my-program
model: anthropic:claude-haiku-4-5

sandbox:
  root: "."
  readonly: false
```

### workers/analyzer.worker
```yaml
---
name: analyzer
instructions: |
  Analyze source code in /src directory.
sandbox:
  restrict: "/src"
  readonly: true
---
```

### workers/editor.worker
```yaml
---
name: editor
instructions: |
  Edit files in the program.
# No sandbox config - inherits full program sandbox (read-write)
---
```

## References
- golem-forge sandbox config: `packages/cli/src/config/program.ts`
- golem-forge worker schema: `packages/core/src/worker-schema.ts`
- golem-forge child sandbox: `packages/core/src/tools/worker-call.ts`
- Current llm-do sandbox: `llm_do/worker_sandbox.py`
