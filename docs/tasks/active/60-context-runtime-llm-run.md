# Context Runtime + llm-run CLI (Headless)

## Prerequisites
- [ ] None

## Goal
Ship a headless `llm-run` CLI that uses the new context-centric runtime from `llm_do/ctx_runtime`, supports the experiment flags plus `--approve-all`, and loads tools declared by `.worker` files from Python code.

## Design Decisions
- **Tool loading**: New mechanism - no `toolset_loader.py` porting
  - Python files passed via CLI contain `AbstractToolset` instances (including `FunctionToolset`)
  - Worker files declare toolset **names** + config (no paths)
  - Matching by name; conflicts → error
- **Discovery**: Scan module attributes with `isinstance(obj, AbstractToolset)`
  - Covers `FunctionToolset`, `ShellToolset`, and any custom toolsets
  - Toolsets expanded to individual `ToolsetToolEntry` instances at discovery time (see below)
- **No custom tool types**: Use PydanticAI's `FunctionToolset` for custom tools (standard API, no custom abstractions)
  - Removed `ToolEntry` and `@tool_entry` decorator - all tools are `ToolsetToolEntry`
- **Toolsets**: Single instance per toolset type, flat namespace
  - `ShellToolset` exposes `shell(command, timeout)` tool
  - Multi-instance toolsets (e.g., two browsers) deferred to future task
- **ToolsetToolEntry**: Toolsets are expanded into per-tool entries at load time
  - Each tool from `toolset.get_tools()` becomes a `ToolsetToolEntry`
  - Conforms to `CallableEntry` protocol, registered by tool name (e.g., `"shell"`)
  - Delegates `call()` to `toolset.call_tool(tool_name, args, ...)`
  - Enables simple registry lookup: `registry.get("shell")` works naturally
  - Implementation sketch:
    ```python
    @dataclass
    class ToolsetToolEntry:
        toolset: AbstractToolset
        tool_name: str
        tool_def: ToolDefinition
        requires_approval: bool = False
        kind: str = "tool"
        model: ModelType | None = None

        @property
        def name(self) -> str:
            return self.tool_name

        async def call(self, input_data: Any, ctx: Context, run_ctx: RunContext) -> Any:
            # Get the ToolsetTool wrapper for validation
            tools = await self.toolset.get_tools(run_ctx)
            tool = tools[self.tool_name]
            return await self.toolset.call_tool(self.tool_name, input_data, run_ctx, tool)
    ```
- **Built-in toolsets**: `shell`, `filesystem` etc. available without loading Python files
  - Registry in `builtins.py`:
    ```python
    BUILTIN_TOOLSETS: dict[str, type[AbstractToolset]] = {
        "shell": ShellToolset,
        "filesystem": FilesystemToolset,
    }
    ```
  - Worker file references by name; runtime resolves to class and instantiates with config
- **Workers as toolsets**: Other `.worker` files passed to CLI are automatically available as toolsets
  - No special syntax - just reference worker name in `toolsets:` section
  - Enables delegation/composition: main worker can call sub-workers as tools
  - All worker files passed to `build_entry_worker()` are available to each other
- **CLI entry point**: `llm-run` is a separate command for now; consolidation with `llm-do` deferred to task 70
- **Examples**: Create `examples-new/` directory for examples validated against new runtime
- **Tests**: Port tests incrementally with status tracking
- **Approval**:
  - `--approve-all` sets `approval=lambda e,d: True` on Context
  - Without `--approve-all`, tools with `requires_approval=True` raise `PermissionError` (headless has no interactive prompt)

## Toolset Config Flow

How toolset configuration flows from worker files to toolset instances:

```
1. CLI loads Python files → discovers AbstractToolset instances by name
   (e.g., `calc_tools = FunctionToolset()` discovered as "calc_tools")

2. Worker file declares toolsets with optional config:
   toolsets:
     shell: { rules: [...] }      # built-in with config
     calc_tools: {}               # from Python file, no config

3. At load time, runtime:
   a. Looks up toolset by name (built-ins or discovered)
   b. Instantiates with config: toolset_class(config=worker_config)
   c. Calls toolset.get_tools() to expand into ToolsetToolEntry instances
   d. Registers each tool entry by its tool name

4. Worker runs with registry containing individual tool entries
```

Note: `FunctionToolset` instances are already instantiated when discovered. Config from worker file is applied via a `configure(config)` method or passed to a wrapper. For simple cases (no config), toolsets work as-is.

## Core API: build_entry

The main programmatic entry point for building entries:

```python
async def build_entry(
    worker_files: list[str],   # List of .worker file paths
    python_files: list[str],   # List of Python file paths containing toolsets
    model: str | None = None,  # Optional model override (applied to entry only)
    entry_name: str = "main",  # Name of the entry
) -> tuple[ToolsetToolEntry | WorkerEntry, list[ToolsetToolEntry]]:
```

**Behavior:**
1. Loads all Python toolsets from `python_files`
2. Expands toolsets to discover tool entry points
3. Loads all Python WorkerEntry instances
4. Creates `WorkerToolset` wrappers for all workers (two-pass resolution)
5. Resolves each worker's toolsets from: Python toolsets, built-ins, or other workers
6. Returns tuple of (entry, available_tools)
   - For worker entries: available_tools is empty (workers have their own tools)
   - For tool entries: available_tools contains all workers and tools

**Entry types supported:**
- `.worker` files (WorkerEntry)
- Python WorkerEntry instances
- Python tools from FunctionToolset (ToolsetToolEntry) - for code entry pattern

**Error handling:**
- Raises `ValueError` if entry not found
- Raises `ValueError` on duplicate worker names
- Raises `ValueError` if worker name conflicts with Python entry
- Raises `ValueError` on unknown toolset reference

**Example - Worker entry:**
```python
# Build pitchdeck_eval with delegation
worker, _ = await build_entry(
    worker_files=[
        "examples-new/pitchdeck_eval/main.worker",
        "examples-new/pitchdeck_eval/pitch_evaluator.worker",
    ],
    python_files=[],
    model="anthropic:claude-sonnet-4-20250514",
)
# main.worker can now call pitch_evaluator as a tool
```

**Example - Tool entry (code entry pattern):**
```python
# Tool entry gets access to workers
tool, available = await build_entry(
    worker_files=["pitch_evaluator.worker"],
    python_files=["orchestrator.py"],  # contains FunctionToolset with "main" tool
    entry_name="main",
)
# tool can call pitch_evaluator via ctx.call()
```

## Worker File Format

```yaml
---
name: main
model: anthropic:claude-haiku-4-5
toolsets:
  shell:                  # built-in toolset
    rules: [...]
  math_tools: {}          # FunctionToolset from CLI-loaded Python
  my_toolset:             # custom AbstractToolset from CLI-loaded Python
    some_option: true
  sub_worker: {}          # another .worker file in same directory (workers as toolsets)
---
Instructions for the worker...
```

- `toolsets:` section references toolset instances by name with optional config
- All toolset code comes from Python files passed to CLI; worker file only has names + config
- Individual tools are defined via `FunctionToolset` (no standalone tool declarations)
- Other `.worker` files in the same directory can be referenced by name (workers as toolsets)

## Example: FunctionToolset

`FunctionToolset` is the standard way to define custom tools:

```python
# examples-new/calculator/tools.py
from pydantic_ai import FunctionToolset

calc_tools = FunctionToolset()

@calc_tools.tool
def factorial(n: int) -> int:
    """Calculate factorial of n."""
    if n <= 1:
        return 1
    return n * factorial(n - 1)

@calc_tools.tool
def fibonacci(n: int) -> int:
    """Calculate nth Fibonacci number."""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
```

```yaml
# examples-new/calculator/main.worker
---
name: main
model: anthropic:claude-haiku-4-5
toolsets:
  calc_tools: {}
---
You are a calculator assistant. Use your tools to help with calculations.
```

Usage:
```bash
llm-run examples-new/calculator/main.worker examples-new/calculator/tools.py "What is 7!"
```

## Tasks

### Runtime Core
- [x] Move/port `experiments/context_runtime/src` into `llm_do/ctx_runtime` (Context/Registry/Entries)
- [x] Add `ToolsetToolEntry` class that wraps individual tools from `AbstractToolset`
- [x] Extend `worker_file.py` to parse `toolsets:` section
- [x] Create `discovery.py` - module loading and `isinstance(obj, AbstractToolset)` scanning
- [x] Create `builtins.py` - `BUILTIN_TOOLSETS` dict mapping names to toolset classes
- [x] Wire toolset expansion: discovered toolsets → `ToolsetToolEntry` instances → registry

### CLI
- [x] Wire `llm-run` CLI to the new runtime with flags (`--entry`, `--all-tools`, `--trace`)
- [x] Add `--approve-all` flag and approval plumbing
- [x] Add entry point to `pyproject.toml`: `llm-run = "llm_do.ctx_runtime.cli:main"`

### Examples
- [x] Create `examples-new/greeter/` - basic worker, no tools
- [x] Create `examples-new/calculator/` - custom tools using `FunctionToolset`
- [x] Validate examples work with `llm-run`

### Tests
- [x] Create `tests/runtime/` directory structure
- [x] Port/create `test_context.py` - Context, Registry, Entries unit tests
- [ ] Port `test_custom_tools.py` for new runtime (deferred - not blocking)
- [x] Port `test_examples.py` for `examples-new/` (11 tests)
- [x] Verify `test_shell.py` works unchanged (39 tests pass)

### Documentation
- [ ] Update docs to reference `llm-run` (headless) without removing old runtime (deferred to task 70)

## Directory Structure

```
llm_do/ctx_runtime/
  __init__.py
  ctx.py              # Context, CallTrace, ToolsProxy
  entries.py          # ToolsetToolEntry, WorkerEntry, WorkerToolset
  registry.py         # Entry registry
  worker_file.py      # .worker parser with toolsets section
  builtins.py         # Built-in toolset registry (BUILTIN_TOOLSETS dict)
  discovery.py        # Module loading and AbstractToolset discovery
  cli.py              # llm-run entry point

examples-new/
  greeter/
    main.worker
  calculator/
    main.worker
    tools.py          # FunctionToolset instance

tests/runtime/
  __init__.py
  test_context.py
  test_discovery.py
  test_worker_file.py
  test_examples.py
```

## Acceptance Criteria
- [x] `llm-run examples-new/greeter/main.worker "Hello"` produces output
- [x] `llm-run examples-new/calculator/main.worker examples-new/calculator/tools.py "What is 5!"` calls factorial tool
- [x] `--approve-all` flag auto-approves all tool calls
- [x] `--trace` flag shows execution trace
- [x] All tests in `tests/runtime/` pass (58 tests)

## Test Porting Status

### Tier 1: Core Runtime (~1850 lines) - Must Port
| Test File | Lines | Status | Notes |
|-----------|-------|--------|-------|
| `test_pydanticai_base.py` | 484 | [ ] | Adapt to new Context/Entry API |
| `test_worker_delegation.py` | 634 | [ ] | Adapt to new delegation model |
| `test_custom_tools.py` | 408 | [ ] | Port to `tests/runtime/` |
| `test_examples.py` | 364 | [ ] | New version for `examples-new/` |

### Tier 2: Toolset Tests (~230 lines) - Adapt for New Runtime
| Test File | Lines | Status | Notes |
|-----------|-------|--------|-------|
| `test_shell.py` | 211 | [ ] | Adapt to new ToolsetToolEntry wrapper |
| `test_filesystem_toolset.py` | 15 | [ ] | Adapt to new ToolsetToolEntry wrapper |

### Tier 3: CLI/UI Tests (~840 lines) - Defer to Task 70
| Test File | Lines | Status | Notes |
|-----------|-------|--------|-------|
| `test_cli_async.py` | 488 | N/A | Port when adding UI |
| `test_display_backends.py` | 351 | N/A | Port when adding UI |

### Tier 4: Supporting Features (~660 lines) - Lower Priority
| Test File | Lines | Status | Notes |
|-----------|-------|--------|-------|
| `test_config_overrides.py` | 256 | [ ] | If config overrides are ported |
| `test_model_compat.py` | 295 | [ ] | Model resolution logic |
| `test_bootstrapper.py` | 236 | [ ] | If bootstrapping is ported |

### Tier 5: Not Applicable
- `test_oauth_*.py` - OAuth flows (not relevant)
- `test_server_side_tools.py` - Server-side tools (not relevant)

## Current State
**IMPLEMENTED.** The context-centric runtime is complete:
- `llm_do/ctx_runtime/` - Context, Registry, Entries, CLI (ported from experiment)
- `examples-new/` - greeter, calculator, approvals_demo, code_analyzer, pitchdeck_eval, whiteboard_planner examples
- `tests/runtime/` - 58 tests passing (context, discovery, worker_file, examples)
- Workers as toolsets: `.worker` files passed to CLI are usable as toolsets (no special "delegation" syntax)
- Unified type system: All tools are `ToolsetToolEntry` (removed `ToolEntry`)

## Type System

The runtime uses 3 core types:

| Type | Purpose |
|------|---------|
| **ToolsetToolEntry** | Any tool (from FunctionToolset, ShellToolset, WorkerToolset, etc.) |
| **WorkerEntry** | LLM-powered worker that can call tools |
| **WorkerToolset** | Adapter wrapping WorkerEntry as AbstractToolset |

All tools are unified as `ToolsetToolEntry`, whether from:
- `FunctionToolset` (custom Python tools)
- `ShellToolset` (shell commands)
- `FilesystemToolset` (file operations)
- `WorkerToolset` (worker delegation)

## Notes
- Runtime is at `llm_do/ctx_runtime/` (not `llm_do/runtime/`) to avoid conflict with existing `llm_do/runtime.py`
- Legacy runtime remains in place; removal is deferred to task 70
- Headless only for this phase (no textual UI)
