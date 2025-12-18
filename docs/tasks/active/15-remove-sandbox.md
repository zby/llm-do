# Remove Sandbox Layer

## Goal

Remove the sandbox layer from llm-do. Container isolation (Docker) replaces per-worker path validation. This simplifies the codebase before implementing neuro-symbolic tool unification.

## Security Model Change

**llm-do assumes it runs inside a Docker container.** The container is the security boundary:

```
Host (user's machine)
│
└── docker run -v $(pwd):/workspace llm-do
    │
    └── llm-do (coding assistant)
        ├── filesystem tools (operate on /workspace)
        ├── shell tools (run in container)
        └── no sandbox validation needed
```

| Concern | Responsibility |
|---------|----------------|
| File isolation | User (docker -v mount) |
| Network policy | User (docker --network) |
| Resource limits | User (docker --memory, --cpus) |
| Tool execution | llm-do (inside container) |

**Documentation must clearly state:** llm-do is designed to run in a container. Running on bare metal is at user's own risk.

## Background

**Current state:**
- `SandboxConfig` defines allowed paths per worker
- `pydantic_ai_filesystem_sandbox` validates file access
- Shell toolset validates paths against sandbox
- Attachment validation checks sandbox boundaries
- Workshop/worker configs merge sandbox settings

**Target state:**
- No path validation in llm-do code
- Filesystem tools operate on whatever is mounted
- Container provides isolation (user's responsibility)
- Simpler worker definitions (no `sandbox:` config)

## Why Now

1. Container isolation is the real security boundary
2. Sandbox code adds complexity without adding security (if in container)
3. Neuro-symbolic unification will be complex enough
4. Clean foundation makes future changes easier

## Files to Change

| File | Refs | Action |
|------|------|--------|
| `worker_sandbox.py` | 58 | Delete entirely |
| `shell/execution.py` | 35 | Remove `validate_paths_in_sandbox` |
| `runtime.py` | 24 | Remove sandbox creation |
| `base.py` | 19 | Remove sandbox re-exports |
| `types.py` | 18 | Remove `SandboxConfig`, `sandbox` fields |
| `protocols.py` | 17 | Remove or simplify `FileSandbox` protocol |
| `registry.py` | 14 | Remove sandbox merging logic |
| `toolset_loader.py` | 9 | Change filesystem toolset loading |
| `delegation_toolset.py` | 9 | Simplify attachment handling |
| `shell/toolset.py` | 8 | Remove sandbox path validation |
| `config_overrides.py` | 5 | Remove sandbox override examples |
| `shell/__init__.py` | 4 | Update exports |
| `shell/types.py` | 2 | Remove `sandbox_paths` field |
| `__init__.py` | 1 | Update exports |
| `cli.py` | 1 | Remove sandbox override example |

## Tasks

### Phase 1: Core Types

- [ ] Remove `SandboxConfig` from `types.py`
- [ ] Remove `sandbox` field from `WorkerDefinition`
- [ ] Remove `sandbox` field from `WorkshopConfig`
- [ ] Remove `default_sandbox` from `WorkerCreationDefaults`
- [ ] Remove `sandbox` from `WorkerContext`
- [ ] Update `validate_attachments` signature

### Phase 2: Delete Sandbox Module

- [ ] Delete `llm_do/worker_sandbox.py`
- [ ] Delete `llm_do/sandbox/` directory if exists
- [ ] Remove imports from `base.py`
- [ ] Remove imports from `__init__.py`

### Phase 3: Runtime Changes

- [ ] Remove sandbox creation in `_prepare_worker_context()`
- [ ] Remove sandbox parameter from `WorkerContext` construction
- [ ] Simplify `call_worker_async` (no sandbox passing)

### Phase 4: Registry Changes

- [ ] Remove sandbox merging in `WorkerRegistry._apply_workshop_defaults()`
- [ ] Remove sandbox-related field handling

### Phase 5: New Filesystem Toolset

- [ ] Create `llm_do/filesystem_toolset.py` with simple tools:
  - `read_file(path)` - read text file
  - `write_file(path, content)` - write text file
  - `glob_files(pattern)` - list matching files
- [ ] Update `toolset_loader.py` to use new toolset
- [ ] Remove `pydantic_ai_filesystem_sandbox` from dependencies

### Phase 6: Shell Toolset Changes

- [ ] Remove `_get_sandbox()` from `shell/toolset.py`
- [ ] Remove `validate_paths_in_sandbox()` from `shell/execution.py`
- [ ] Remove `enhance_error_with_sandbox_context()`
- [ ] Remove `sandbox_paths` from shell rule types

### Phase 7: Delegation Changes

- [ ] Simplify attachment validation (no sandbox boundaries)
- [ ] Remove `AttachmentValidator` class or simplify
- [ ] Update `_prepare_attachments()` in delegation toolset

### Phase 8: Cleanup

- [ ] Remove sandbox examples from `config_overrides.py`
- [ ] Update `worker_bootstrapper.worker` (remove sandbox config)
- [ ] Update tests

### Phase 9: Update Examples

Workers with `sandbox:` config:
- `examples/approvals_demo/main.worker`
- `examples/calculator/main.worker`
- `examples/pitchdeck_eval/main.worker`
- `examples/web_research_agent/main.worker`
- `examples/whiteboard_planner/main.worker`

- [ ] Remove `sandbox:` from example workers
- [ ] Verify examples still work

### Phase 10: Documentation

- [ ] Add security model documentation:
  - llm-do assumes Docker container environment
  - Container is the security boundary
  - User responsible for mounts, network, resource limits
  - Running on bare metal is at user's own risk
- [ ] Update worker definition docs (remove sandbox references)
- [ ] Update README with container usage
- [ ] Update any workshop.yaml examples in docs

## Dependency Decision

**`pydantic_ai_filesystem_sandbox`** - Remove entirely.

Write simple filesystem toolset in llm-do:
- `read_file(path)` → read text
- `write_file(path, content)` → write text
- `glob_files(pattern)` → list matching files

Without sandbox validation, these are trivial (~50 lines). Can extract logic from `../pydantic_ai_filesystem_sandbox` if needed.

## Migration

Workers with `sandbox:` config will get a warning and the field will be ignored. No breaking change for users - their workers still work, just without path restrictions.

## Tests

Expect many test failures initially. Tests that explicitly test sandbox behavior should be:
- Deleted if testing sandbox validation
- Updated if testing file operations (remove sandbox setup)

## Current State

Not started.

## References

- Design context: `docs/notes/neuro-symbolic-tool-unification.md`
- Design context: `docs/notes/workers-vs-subagents-brainstorm.md`
- Current sandbox: `llm_do/worker_sandbox.py`
- Filesystem toolset: `pydantic_ai_filesystem_sandbox`
