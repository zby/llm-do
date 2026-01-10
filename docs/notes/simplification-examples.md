# Manual Simplification Examples

Examples of manual code simplifications to use as reference for constructing prompts that propose similar improvements.

---

## Simplification Proposal Prompt

Use this prompt to ask an LLM to analyze code and propose simplifications:

```
Analyze this codebase for simplification opportunities. Look for patterns like:

1. **Redundant validation** - Checks that are already handled by a dependency or framework. If a library you depend on already validates something, your duplicate check adds complexity without value.

2. **Unused flexibility** - Data structures that support configuration or options that are never actually used. Examples:
   - Dict values that are always empty `{}`
   - Optional parameters that always receive the same value
   - Generic types that are always instantiated the same way
   Consider whether the flexibility will ever be needed, or if it should be pushed to a different layer.

3. **Redundant parameters** - Function parameters that pass values already accessible via other parameters. If you pass `obj` and also `obj.x`, the second parameter is redundant and creates maintenance risk (they could get out of sync).

4. **Duplicated derived values** - The same computed/formatted value appearing in multiple places. Examples:
   - Format strings like `f"[{worker}:{depth}]"` repeated across methods
   - Computed properties recalculated instead of stored
   These should be centralized into a single property or method. This prevents inconsistency bugs.

5. **Over-specified interfaces** - Passing multiple primitive values when a single object would do, especially when those values are always used together or derived from the same source.

For each opportunity found:
- Explain what pattern it matches
- Show the current code
- Propose the simplified version
- Note any judgment calls required (e.g., "this removes flexibility that might be needed")
- Flag if the simplification would have prevented any existing inconsistencies

Prioritize changes that:
- Remove code rather than add it
- Reduce the number of places where a concept is defined
- Make it impossible (not just unlikely) for certain bugs to occur
```

---

## 1. Remove Redundant Duplicate Check (487c463)

**Commit:** `487c463` - "Remove redundant duplicate tool name check from registry"
**Date:** 2026-01-09

**What was simplified:**
- Removed explicit duplicate tool name detection from `llm_do/runtime/registry.py`
- pydantic-ai's `CombinedToolset.get_tools()` already detects duplicate tool names at runtime, making llm-do's check redundant

**Changes:**
1. Removed the duplicate check logic and error raising
2. Simplified tuple from 3-element `(toolset, tool_name, toolset_name)` to 2-element `(toolset, tool_name)` since `toolset_name` was only used for the removed error message
3. Removed the associated test `test_build_entry_duplicate_tool_name_raises`
4. Updated documentation to reflect the change

**Before:**
```python
python_tool_map: dict[str, tuple[AbstractToolset[Any], str, str]] = {}
for toolset_name, toolset in python_toolsets.items():
    tool_names = await _get_tool_names(toolset)
    for tool_name in tool_names:
        if tool_name in python_tool_map:
            _, _, existing_toolset_name = python_tool_map[tool_name]
            raise ValueError(
                f"Duplicate tool name: {tool_name} "
                f"(from toolsets '{existing_toolset_name}' and '{toolset_name}')"
            )
        python_tool_map[tool_name] = (toolset, tool_name, toolset_name)
```

**After:**
```python
# Note: duplicate tool names are detected by pydantic-ai at runtime
python_tool_map: dict[str, tuple[AbstractToolset[Any], str]] = {}
for toolset_name, toolset in python_toolsets.items():
    tool_names = await _get_tool_names(toolset)
    for tool_name in tool_names:
        if tool_name not in python_tool_map:
            python_tool_map[tool_name] = (toolset, tool_name)
```

**Pattern:** Removing validation/checks that are already handled by a dependency or framework.

## 2. Toolsets Dict to List (a31a841)

**Commit:** `a31a841` - "Simplify toolsets list and filesystem builtins"
**Date:** 2026-01-09

**What was simplified:**
- Changed Worker's `toolsets` field from `dict[str, dict[str, Any]]` to `list[str]`
- The dict values were always empty `{}` - the config capability was never used
- Realized that if toolset configuration is needed, users should define a Python toolset instance instead

**Judgment required:**
This was a semantic change that required evaluating whether the unused flexibility (per-toolset config in YAML) would ever be needed. Decision: toolset configuration belongs in Python code, not in worker YAML files.

**Changes:**
1. Changed `WorkerDefinition.toolsets` from `dict[str, dict[str, Any]]` to `list[str]`
2. Simplified `_parse_toolsets()` function accordingly
3. Updated all example `.worker` files to use list syntax
4. Also renamed filesystem builtins (`filesystem_rw` → `filesystem_project`, etc.)

**Before (worker file):**
```yaml
toolsets:
  web_research_extractor: {}
  web_research_consolidator: {}
  filesystem_rw: {}
```

**After (worker file):**
```yaml
toolsets:
  - web_research_extractor
  - web_research_consolidator
  - filesystem_project
```

**Before (Python):**
```python
@dataclass
class WorkerDefinition:
    ...
    toolsets: dict[str, dict[str, Any]] = field(default_factory=dict)

def _parse_toolsets(toolsets_raw: Any) -> dict[str, dict[str, Any]]:
    if not toolsets_raw:
        return {}
    if not isinstance(toolsets_raw, dict):
        raise ValueError("Invalid toolsets: expected YAML mapping")
    toolsets: dict[str, dict[str, Any]] = {}
    for toolset_name, toolset_config in toolsets_raw.items():
        if toolset_config is None:
            toolset_config = {}
        if not isinstance(toolset_config, dict):
            raise ValueError(f"Invalid config for toolset '{toolset_name}': expected YAML mapping")
        if toolset_config:
            raise ValueError(
                f"Toolset '{toolset_name}' cannot be configured in worker YAML; "
                "define a Python toolset instance instead"
            )
        toolsets[toolset_name] = toolset_config
    return toolsets
```

**After (Python):**
```python
@dataclass
class WorkerDefinition:
    ...
    toolsets: list[str] = field(default_factory=list)

def _parse_toolsets(toolsets_raw: Any) -> list[str]:
    if toolsets_raw is None:
        return []
    if not isinstance(toolsets_raw, list):
        raise ValueError("Invalid toolsets: expected YAML list")
    toolsets: list[str] = []
    seen: set[str] = set()
    for item in toolsets_raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Invalid toolset entry: expected non-empty string")
        if item in seen:
            raise ValueError(f"Duplicate toolset entry: {item}")
        seen.add(item)
        toolsets.append(item)
    return toolsets
```

**Pattern:** Removing unused flexibility - when a data structure supports configuration that's never used, simplify to the actual usage pattern. Configuration that requires more structure should be pushed to a more appropriate layer (Python code vs YAML).

## 3. Redundant Parameter from Passed Object (uncommitted)

**What was simplified:**
- Removed a parameter that was already accessible via another parameter

**Before:**
```python
self._emit_tool_events(stream.new_messages(), runtime, runtime.depth)
```

**After:**
```python
self._emit_tool_events(stream.new_messages(), runtime)
# Inside _emit_tool_events, just use runtime.depth
```

**Why it's problematic:**
- Redundant data: `depth` is passed separately but `runtime` is already passed
- Maintenance risk: if someone updates one but not the other, inconsistency
- Conceptual overhead: suggests `depth` might differ from `runtime.depth`

**Pattern:** Don't pass derived/accessible values as separate parameters when the source object is already being passed. Access the value from the object inside the function instead.

## 4. Centralize Format String to Prevent Inconsistencies (2985504 → c6dc0cd)

**Commits:**
- `2985504` - "Add depth indicator to TUI Response widgets" (bug fix)
- `c6dc0cd` - "Refactor worker_tag formatting to single location" (refactoring)

**The bug:**
- `ToolCallEvent` formatted its header as `[worker:depth]`
- `TextResponseEvent` formatted its header as `[worker]` (missing depth!)
- Inconsistent display across event types

**The fix (2985504):**
Added `worker` and `depth` parameters throughout the widget chain, duplicating the format logic:

```python
# In AssistantMessage
def _format_content(self) -> str:
    if self._worker:
        return f"[{self._worker}:{self._depth}] Response:\n{self._content}"
    return self._content

# In ToolCallMessage
def _format_tool_call(self) -> str:
    if self._worker:
        lines = [f"[{self._worker}:{self._depth}] Tool: {self._tool_name}"]
```

**The refactoring (c6dc0cd):**
Created a single `worker_tag` property on the base `UIEvent` class:

```python
@dataclass
class UIEvent(ABC):
    worker: str = ""
    depth: int = 0

    @property
    def worker_tag(self) -> str:
        """Format worker and depth as a tag like [worker:depth]."""
        return f"[{self.worker}:{self.depth}]"
```

Then all render methods and widgets just use `self.worker_tag` or accept `worker_tag: str`:

```python
# In events.py - all render methods use the property
def render_text(self, verbosity: int = 0) -> str:
    lines = [f"\n{self.worker_tag} Tool call: {self.tool_name}"]

# In widgets - accept pre-formatted string
def __init__(self, content: str = "", worker_tag: str = "", **kwargs: Any) -> None:
    self._worker_tag = worker_tag
```

**Key insight:**
If the refactoring had been done initially, the bug couldn't have existed - there would be only one place defining the `[worker:depth]` format. The inconsistency arose from having multiple places compute the same formatted string.

**Pattern:** Centralize derived/computed values (especially formatted strings) into a single property or method. When the same format appears in multiple places, it's a refactoring opportunity that also prevents inconsistency bugs.
