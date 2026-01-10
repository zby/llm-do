# Manual Simplification Examples

Examples of manual code simplifications to use as reference for constructing prompts that propose similar improvements.

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
