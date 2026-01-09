# Toolset Definitions and Approval Policy

## Context
Approvals should be capability-based, not worker-based. Today per-worker `_approval_config`
is extracted from worker YAML into `Worker.toolset_approval_configs`, which means the same tool
can have different approval rules depending on which worker calls it. Toolsets are defined in
Python, so configuration and approval policy should live together there instead of being split
between Python and YAML.

## Findings
- Approval rules belong to toolset definitions (capability + config), not to workers. A tool should
  have one policy, and if we need different policies we should define distinct toolset names
  (e.g., `filesystem_project`, `filesystem_read_only`).
- Toolsets should stay as PydanticAI `AbstractToolset`/`FunctionToolset` instances. We should not
  invent a parallel toolset abstraction; we only need to attach approval policy to existing toolsets.
- Toolsets are defined in Python and should be instantiated eagerly. The registry should hold
  instances directly; factories are allowed earlier in the build path but should be resolved
  before registry construction.
- Worker definitions should only reference toolset names. Per-worker `_approval_config` should be
  removed, and worker-local toolset overrides should be disallowed (or strictly validated).
- The registry is the capability catalog. It should map toolset names to instances and approval
  metadata, and workers should resolve toolsets by name from this shared catalog.
- Built-in toolsets (filesystem, shell) should always be available from the registry, even when
  no Python toolset file is provided.
- Approval metadata needs an explicit attachment point. Options:
  - side registry keyed by toolset name or object id
  - a wrapper type (e.g., `ApprovedToolset`) that carries policy
  - a structured registry entry like `ToolsetRegistration(name, instance, approval_config)`
- Built-in toolsets (filesystem, shell) should be registered under named profiles with explicit
  approval policies rather than implied defaults.
- Server-side tools are a separate case (they are not toolsets). Their approval policy still needs
  a single source of truth, likely configured centrally with the toolset catalog rather than per
  worker.

Example registration sketch:
```
# toolsets.py
toolsets = {
    "filesystem_project": ToolsetRegistration(
        instance=FileSystemToolset(config={"root": ".", "read_only": False}),
        approval_config={"mode": "prompt"},
    ),
    "filesystem_read_only": ToolsetRegistration(
        instance=FileSystemToolset(config={"root": ".", "read_only": True}),
        approval_config={"mode": "auto_approve"},
    ),
}
```

```
# worker.yaml
toolsets:
  filesystem_project: {}
```

## Concrete Solutions
1) **Attribute-based approval policy (minimal abstraction)**
   - Keep PydanticAI toolsets unchanged.
   - Attach approval config directly to the instance, e.g. `toolset.approval_config = {...}` or
     `toolset.__llm_do_approval__ = {...}`.
   - Registry stores only instances. Approval wrapper reads policy via `getattr`.
   - Built-ins can register as module-level instances or be instantiated during registry build.
   - Instantiation flow:
     - User toolsets: module-level instances created on import.
     - Built-ins: instantiated once during registry build (always available).
   - Attach approval attributes immediately after instantiation (before registry insertion).

2) **Side-map policy keyed by toolset name (minimal separation)**
   - Module exports `TOOLSETS: dict[str, AbstractToolset]` and `TOOLSET_APPROVALS: dict[str, ApprovalConfig]`.
   - Registry merges built-ins + user toolsets into two maps (instances + policies).
   - Approval wrapper looks up by toolset name (stable registry key).
   - Avoids mutating toolset instances, but still no new toolset class.
   - Config lives in Python (toolset module), not in worker YAML.

3) **Thin registration record (small abstraction)**
   - A tiny dataclass like `ToolsetRegistration(name, instance, approval_config)` that only
     groups existing PydanticAI toolsets with approval metadata.
   - Keeps policy attached to the registry entry rather than the toolset object.
   - This is the most explicit but adds a small abstraction.

All three reuse PydanticAI toolset objects directly. The difference is only where approval policy
is stored and how it is looked up at wrap time.

Helper sketch for attribute-based policy:
```
def with_approval(toolset, config):
    setattr(toolset, "__llm_do_approval_config__", config)
    return toolset
```

Built-in registration sketch:
```
filesystem_project = with_approval(
    FileSystemToolset(config={"root": ".", "read_only": False}),
    {"write_file": {"pre_approved": False}},
)
```

User toolset sketch:
```
tools = FunctionToolset()
tools.__llm_do_approval_config__ = {"sanitize_filename": {"pre_approved": True}}
```

Optional sugar for per-tool config (no PydanticAI changes):
```
tools = FunctionToolset()

@llm_do_tool(tools, pre_approved=True)
def sanitize_filename(name: str) -> str:
    ...
```
This helper would:
- call `tools.tool(...)` to register the function
- update `tools.__llm_do_approval_config__` for that tool name

## Integration with PydanticAI Toolsets
- Use PydanticAI wrappers where appropriate (`PrefixedToolset`, `RenamedToolset`, `FilteredToolset`,
  `PreparedToolset`) to adjust tool exposure without inventing new layers.
- Continue to wrap toolsets with `pydantic_ai_blocking_approval.ApprovalToolset` at runtime so
  approvals remain blocking and interactive (CLI/TUI). This wrapper already supports toolsets
  implementing `SupportsNeedsApproval` (as `ShellToolset` and `FileSystemToolset` do).
- Avoid using PydanticAI's `requires_approval`/`ApprovalRequiredToolset` unless we want deferred
  approval flows; that is a different execution model than the blocking approval UI we already use.
- Do not add a custom wrapper; rely on `ApprovalToolset` + `SupportsNeedsApproval`.
  - Simple toolset → no custom method; `ApprovalToolset` uses the registry approval config
    (if config is omitted or empty, default is “approval required” for all tools).
  - Policy-aware toolset → implement `needs_approval` and optionally consult the registry config
    (via `needs_approval_from_config`) to allow pre-approved tools before applying custom logic.

## Tool-Level Approval Config (Toolsets Without needs_approval)
- `ApprovalToolset` only inspects the `config` argument for toolsets that do **not** implement
  `SupportsNeedsApproval`. That means per-tool approval policy must be available as a dict at
  wrap time (tool name → config).
- Practical storage options:
  - **Registry config map** keyed by toolset name (side-map).
  - **Toolset attribute** (e.g., `toolset.__llm_do_approval_config__`) read at wrap time to build
    the config dict.
- Storing approval hints inside `ToolDefinition.metadata` does **not** affect `ApprovalToolset`
  unless we add a wrapper/adapter that reads metadata and builds a config dict. If we want to
  avoid custom wrappers, keep the config in the registry or on the toolset instance.

## Recommended Path (Low Change, High Clarity)
- Adopt **Solution 1** (attribute-based) or **Solution 2** (side-map). Both keep toolsets as pure
  PydanticAI instances and require the smallest new surface area.
- Define built-ins as named, preconfigured instances (e.g., `filesystem_project`, `filesystem_read_only`,
  `shell_readonly`) so worker YAML does not need configuration for built-ins.
- Allow factories in Python to build those instances, but ensure the registry stores only the
  final instances + approval metadata.
- If worker-specific toolset config is needed, define additional named toolsets in Python rather
  than per-worker overrides (e.g., `filesystem_project`, `filesystem_tmp`).
- For read-only filesystem behavior, prefer a single `FileSystemToolset` with a `read_only` config
  flag that removes write tools from `get_tools` and blocks `write_file` in `call_tool`. Then
  expose two built-in instances: `filesystem_project` (read/write) and `filesystem_read_only`
  (read/list only).
- `FileSystemToolset` should also support `base_path` in config so we can define multiple named
  instances (e.g., `filesystem_project`, `filesystem_tmp`, `filesystem_inputs`) with different
  roots and approval policies.

## Migration Sketch
- Remove `_approval_config` from worker YAML; workers only list toolset names.
- Update loader to reject toolset config in YAML (or allow only empty config).
- Add built-in toolset instances with approval metadata to the registry by default.
- Update examples to import/use Python toolsets for any non-default config; approvals move into
  Python toolset registration (attribute or side-map), not worker YAML.
- Remove `Worker.toolset_approval_configs` and pass approval policies from registry to the
  approval wrapper directly.

## Open Questions
- Should a module expose `TOOLSETS` (dict of registrations) or use a decorator-based registry?
- Should CLI overrides still exist for toolset config? If yes, should approval policy be locked?
- Where should approval metadata live (registry entry vs wrapper vs side map)?
- Do we fully forbid worker-local toolset config overrides, or allow with strict validation?
- Do we allow factories in toolset registration (resolved before registry creation), or require
  only instantiated toolsets in `TOOLSETS`?

## Conclusion
Implemented attribute-based approval config on toolset instances, with worker YAML
limited to toolset names only. Built-in toolset profiles (`filesystem_rw`,
`filesystem_ro`, `shell_readonly`, `shell_file_ops`) are registered in the
registry, and a read-only filesystem toolset blocks writes and omits the write
tool. Per-worker `_approval_config` and toolset YAML config were removed; any
per-tool pre-approvals now live on the toolset instance via
`__llm_do_approval_config__`.

Open follow-up: decide whether to add a helper decorator for per-tool approval
metadata on `FunctionToolset`.
