# Toolset Plugin Comparison: golem-forge vs llm-do

## Summary

golem-forge's plugin system is easier to use for the common case (simple custom tools) while also being more flexible for advanced cases. The key differences are in registration patterns and configuration flexibility.

## Side-by-Side Comparison

### Simple Custom Tools

**golem-forge** - Two export formats:

```typescript
// Format 1: Function + Schema (simplest)
export function summarize(args: { text: string }) {
  return { summary: args.text.slice(0, 50) };
}
export const summarizeSchema = z.object({
  text: z.string().describe('Text to summarize'),
});

// Format 2: Full NamedTool (more control)
export const summarize: NamedTool = {
  name: 'summarize',
  description: 'Summarize text',
  inputSchema: z.object({ text: z.string() }),
  execute: async (args) => ({ summary: args.text.slice(0, 50) }),
  manualExecution: { mode: 'both', label: 'Summarize' },
};
```

**llm-do** - Python function with whitelist:

```python
# tools.py
def summarize(text: str) -> str:
    """Summarize text."""
    return text[:50]
```

**Winner**: Tie for simplest case. golem-forge has more flexibility (Format 2), llm-do is slightly simpler for basic functions.

### Registration

**golem-forge** - Self-registering factories:

```typescript
// Toolset self-registers on import
ToolsetRegistry.register('git', gitToolsetFactory);

// Worker just references by name
toolsets:
  git:
    default_target: { type: local }
```

**llm-do** - Alias map + dynamic import:

```python
# Hardcoded in toolset_loader.py
ALIASES = {
    "shell": "llm_do.shell.toolset.ShellToolset",
    "custom": "llm_do.custom_toolset.CustomToolset",
}

# Worker references by alias or full class path
toolsets:
  shell: { rules: [...] }
  mycompany.toolsets.Database: { connection: "..." }
```

**Winner**: golem-forge. Self-registration is more extensible - third-party toolsets just need to be imported, no changes to core code.

### Execution Mode Configuration

**golem-forge** - Per-tool override in config:

```yaml
toolsets:
  git:
    tools:
      git_stage:
        mode: manual  # Override default
```

**llm-do** - No runtime mode override:

```yaml
toolsets:
  custom:
    my_function: { pre_approved: true }  # Only approval, not execution mode
```

**Winner**: golem-forge. Mode override allows users to tune security without code changes.

### Toolset Context

**golem-forge** - Rich context injected to factory:

```typescript
interface ToolsetContext {
  sandbox?: FileOperations;
  approvalController: ApprovalController;
  workerFilePath?: string;
  programRoot?: string;
  config: Record<string, unknown>;
}
```

**llm-do** - Runtime context via `ctx.deps`:

```python
# In call_tool():
worker_ctx: WorkerContext = ctx.deps
# Has: registry, approval_controller, attachments, etc.
```

**Winner**: Tie. Both provide necessary context, just different patterns (factory injection vs runtime dependency).

### Tool Definition Interface

**golem-forge**:

```typescript
interface NamedTool extends Tool {
  name: string;
  manualExecution?: { mode: ExecutionMode; label?: string; category?: string };
  needsApproval?: boolean | ((args, ctx) => boolean);
}
```

**llm-do**:

```python
class MyToolset(AbstractToolset[WorkerContext]):
    async def get_tools(self, ctx) -> dict[str, ToolsetTool]: ...
    async def call_tool(self, name, tool_args, ctx, tool) -> Any: ...
    def needs_approval(self, name, tool_args, ctx) -> ApprovalResult: ...
    def get_approval_description(self, name, tool_args, ctx) -> str: ...
```

**Winner**: golem-forge. Single object vs multiple methods to implement.

### Third-Party Extensibility

**golem-forge**:

```typescript
// Third-party package just registers on import
import '@third-party/database-toolset';  // Self-registers

// Then use in worker
toolsets:
  database: { connection: "..." }
```

**llm-do**:

```yaml
# Full class path required
toolsets:
  third_party.toolset.DatabaseToolset:
    connection: "..."
```

**Winner**: golem-forge. Cleaner aliases, third-party can provide its own short name.

## Key Design Differences

| Aspect | golem-forge | llm-do |
|--------|-------------|--------|
| **Registration** | Self-registering factories | Alias map + dynamic import |
| **Tool definition** | Single object (NamedTool) | Abstract class with methods |
| **Execution mode** | Config-overridable | Toolset method + config override (planned) |
| **Approval** | Property on tool | Method on toolset |
| **Custom tools** | Module exports | `tools.py` + whitelist |
| **Schema** | Zod (required) | Type hints (auto-extracted) |

## What llm-do Could Adopt

### 1. Self-Registering Toolsets

Instead of:
```python
# toolset_loader.py
ALIASES = {"shell": "llm_do.shell.toolset.ShellToolset"}
```

Use:
```python
# In shell/toolset.py
ToolsetRegistry.register("shell", ShellToolset)

# In toolset_loader.py
def get_toolset(name):
    return ToolsetRegistry.get(name) or dynamic_import(name)
```

**Benefit**: Third-party toolsets self-register on import, no core changes needed.

### 2. Execution Mode via Toolset Method

Since `AbstractToolset` and `ToolDefinition` come from pydantic-ai, avoid upstream changes by adding a method:

```python
class MyToolset(AbstractToolset[WorkerContext]):
    async def get_tools(self, ctx) -> dict[str, ToolsetTool]: ...

    def get_manual_only_tools(self) -> set[str]:
        """Return tool names that should not be sent to the LLM."""
        manual = {"git_push", "deploy"}
        # Config can override defaults
        for name, cfg in self._config.items():
            if cfg.get("mode") == "manual":
                manual.add(name)
            elif cfg.get("mode") == "llm":
                manual.discard(name)
        return manual
```

Runtime filters before passing to LLM:
```python
all_tools = await toolset.get_tools(ctx)
manual_only = toolset.get_manual_only_tools()
llm_tools = {k: v for k, v in all_tools.items() if k not in manual_only}
```

**Benefit**: Users can tune security per-deployment without code changes. No pydantic-ai modifications needed.

### 3. Simpler Tool Definition

Allow single-object tool definitions alongside class-based:

```python
my_tool = Tool(
    name="my_tool",
    description="...",
    schema={"type": "object", ...},
    execute=lambda args, ctx: do_something(args),
    needs_approval=True,
    mode="both",
)
```

**Benefit**: Less boilerplate for simple tools.

### 4. Category/Label Metadata

For UI grouping:
```python
my_tool = Tool(
    name="git_push",
    label="Push to Remote",  # Human-friendly
    category="Git",          # UI grouping
    ...
)
```

**Benefit**: Better TUI/UI presentation of manual tools.

## Implementation Priority

1. **Self-registering toolsets** - Most impactful for extensibility
2. **Execution mode metadata** - Critical for manual tools feature
3. **Category/label metadata** - Needed for Textual UI
4. **Simpler tool definition** - Nice to have, reduces boilerplate

## Conclusion

golem-forge's system is more mature and easier to extend. The key improvements for llm-do:

1. **Self-registration pattern** for toolsets (entry points or import-based)
2. **Execution mode via `get_manual_only_tools()` method** - avoids pydantic-ai changes, config can override defaults
3. **UI metadata** (label, category) for manual tool presentation

The execution mode approach via a toolset method is the chosen path forward - it aligns with the "one tool interface, mode as metadata" principle while staying self-contained within llm-do.

## Open Questions
- Do we want to prioritize self-registering toolsets over other tooling work?
- Should execution mode metadata be part of the toolset interface or external config only?
