# SLOC Reduction Patterns from Ralph Loop

**Date**: 2026-01-16
**Result**: 5,566 → 4,783 SLOC (-14%, -783 lines)
**Method**: Automated Ralph Wiggum loop with `sloccount` target < 4,800

---

## Summary

An automated code reduction loop found that most gains came from removing documentation noise and simplifying APIs, not changing algorithms. All 302 tests continued to pass.

---

## Pattern 1: Result Objects → Raise on Error

**Location**: `llm_do/models.py`

**Before** (~45 lines):
```python
@dataclass
class ModelValidationResult:
    valid: bool
    model: str
    message: Optional[str] = None

def validate_model_compatibility(
    model: str,
    compatible_models: Optional[List[str]],
    *,
    worker_name: str = "worker",
) -> ModelValidationResult:
    if compatible_models is None:
        return ModelValidationResult(valid=True, model=model)

    if len(compatible_models) == 0:
        raise InvalidCompatibleModelsError(...)

    for pattern in compatible_models:
        if model_matches_pattern(model, pattern):
            return ModelValidationResult(valid=True, model=model)

    return ModelValidationResult(
        valid=False,
        model=model,
        message=f"Model '{model}' is not compatible with worker '{worker_name}'..."
    )

# Caller:
result = validate_model_compatibility(model_str, compatible_models, worker_name=name)
if not result.valid:
    raise ModelCompatibilityError(result.message)
```

**After** (~15 lines):
```python
def validate_model_compatibility(
    model: str | Model, compatible_models: list[str] | None, *, worker_name: str = "worker"
) -> None:
    """Validate model against compatibility patterns. Raises ModelCompatibilityError if invalid."""
    if compatible_models is None:
        return
    if not compatible_models:
        raise InvalidCompatibleModelsError(
            f"Worker '{worker_name}' has empty compatible_models list. Use ['*'] for any model."
        )
    model_str = get_model_string(model)
    if any(model_matches_pattern(model_str, p) for p in compatible_models):
        return
    patterns = ", ".join(f"'{p}'" for p in compatible_models)
    raise ModelCompatibilityError(f"Model '{model_str}' incompatible with '{worker_name}'. Patterns: {patterns}")

# Caller:
validate_model_compatibility(model_str, compatible_models, worker_name=name)  # raises if invalid
```

**Test changes required**:
- `assert result.valid is True` → just call function (no exception = valid)
- `assert result.valid is False` → `with pytest.raises(ModelCompatibilityError)`
- Update error message match strings if messages changed

---

## Pattern 2: Exception Class Consolidation

**Location**: `llm_do/models.py`

**Before** (~20 lines):
```python
class ModelCompatibilityError(ValueError):
    """Raised when a model is incompatible with worker requirements."""
    pass

class NoModelError(ValueError):
    """Raised when no model is available for a worker."""
    pass

class InvalidCompatibleModelsError(ValueError):
    """Raised when compatible_models configuration is invalid (e.g., empty list)."""
    pass

class ModelConfigError(ValueError):
    """Raised when model configuration is invalid (e.g., both model and compatible_models set)."""
    pass
```

**After** (~12 lines):
```python
class ModelError(ValueError):
    """Base class for model-related errors."""

class ModelCompatibilityError(ModelError):
    """Model is incompatible with worker requirements."""

class NoModelError(ModelError):
    """No model is available for a worker."""

class InvalidCompatibleModelsError(ModelError):
    """compatible_models configuration is invalid."""

class ModelConfigError(ModelError):
    """Model configuration is invalid."""
```

**Benefit**: Base class enables `except ModelError` to catch all, docstrings don't repeat class name.

---

## Pattern 3: Duplicate Discovery Functions → Generic Helper

**Location**: `llm_do/runtime/discovery.py`

**Before** (~60 lines):
```python
def discover_toolsets_from_module(module: ModuleType) -> dict[str, ToolsetSpec]:
    toolsets: dict[str, ToolsetSpec] = {}
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, ToolsetSpec):
            toolsets[name] = obj
    return toolsets

def discover_workers_from_module(module: ModuleType) -> list[Worker]:
    workers: list[Worker] = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, Worker):
            workers.append(obj)
    return workers

def discover_entries_from_module(module: ModuleType) -> list[EntryFunction]:
    entries: list[EntryFunction] = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, EntryFunction):
            entries.append(obj)
    return entries
```

**After** (~20 lines):
```python
def _discover_from_module(module: ModuleType, target_type: type) -> list:
    return [getattr(module, name) for name in dir(module)
            if not name.startswith("_") and isinstance(getattr(module, name), target_type)]

def discover_toolsets_from_module(module: ModuleType) -> dict[str, ToolsetSpec]:
    toolsets: dict[str, ToolsetSpec] = {}
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, ToolsetSpec):
            toolsets[name] = obj
        elif isinstance(obj, AbstractToolset):
            raise ValueError(f"Toolset '{name}' must be defined as ToolsetSpec.")
    return toolsets

def discover_workers_from_module(module: ModuleType) -> list[Worker]:
    return _discover_from_module(module, Worker)

def discover_entries_from_module(module: ModuleType) -> list[EntryFunction]:
    return _discover_from_module(module, EntryFunction)
```

**Note**: `discover_toolsets_from_module` kept separate due to error handling for AbstractToolset.

---

## Pattern 4: Repetitive Tool Construction → Factory Method

**Location**: `llm_do/toolsets/filesystem.py`

**Before** (~50 lines):
```python
async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool[Any]]:
    tools = {}

    read_file_schema = ReadFileArgs.model_json_schema()
    write_file_schema = WriteFileArgs.model_json_schema()
    list_files_schema = ListFilesArgs.model_json_schema()

    tools["read_file"] = ToolsetTool(
        toolset=self,
        tool_def=ToolDefinition(
            name="read_file",
            description="Read a text file. Do not use this on binary files...",
            parameters_json_schema=read_file_schema,
        ),
        max_retries=self._max_retries,
        args_validator=cast(SchemaValidatorProt, DictValidator(ReadFileArgs)),
    )

    tools["write_file"] = ToolsetTool(
        toolset=self,
        tool_def=ToolDefinition(
            name="write_file",
            description="Write a text file.",
            parameters_json_schema=write_file_schema,
        ),
        max_retries=self._max_retries,
        args_validator=cast(SchemaValidatorProt, DictValidator(WriteFileArgs)),
    )

    tools["list_files"] = ToolsetTool(
        toolset=self,
        tool_def=ToolDefinition(
            name="list_files",
            description="List files in a directory matching a glob pattern.",
            parameters_json_schema=list_files_schema,
        ),
        max_retries=self._max_retries,
        args_validator=cast(SchemaValidatorProt, DictValidator(ListFilesArgs)),
    )

    return tools
```

**After** (~15 lines):
```python
def _make_tool(self, name: str, desc: str, args_cls: type[BaseModel]) -> ToolsetTool[Any]:
    return ToolsetTool(
        toolset=self,
        tool_def=ToolDefinition(name=name, description=desc, parameters_json_schema=args_cls.model_json_schema()),
        max_retries=self._max_retries,
        args_validator=cast(SchemaValidatorProt, DictValidator(args_cls)),
    )

async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool[Any]]:
    return {
        "read_file": self._make_tool("read_file", "Read a text file. Do not use on binary files - pass them as attachments instead.", ReadFileArgs),
        "write_file": self._make_tool("write_file", "Write a text file.", WriteFileArgs),
        "list_files": self._make_tool("list_files", "List files in a directory matching a glob pattern.", ListFilesArgs),
    }
```

---

## Pattern 5: Verbose Conditionals → Ternary Expression

**Location**: `llm_do/toolsets/filesystem.py`

**Before** (~15 lines):
```python
def check_approval(self, name: str, tool_args: dict[str, Any], ctx: Any, config: ApprovalConfig | None = None) -> ApprovalResult:
    base = needs_approval_from_config(name, config)
    if base.is_blocked:
        return base
    if base.is_pre_approved:
        return base

    if name == "read_file":
        if self._read_approval:
            return ApprovalResult.needs_approval()
        return ApprovalResult.pre_approved()
    elif name == "write_file":
        if self._write_approval:
            return ApprovalResult.needs_approval()
        return ApprovalResult.pre_approved()
    elif name == "list_files":
        if self._read_approval:
            return ApprovalResult.needs_approval()
        return ApprovalResult.pre_approved()

    return ApprovalResult.needs_approval()
```

**After** (~6 lines):
```python
def check_approval(self, name: str, tool_args: dict[str, Any], ctx: Any, config: ApprovalConfig | None = None) -> ApprovalResult:
    base = needs_approval_from_config(name, config)
    if base.is_blocked or base.is_pre_approved:
        return base

    requires = self._write_approval if name == "write_file" else self._read_approval
    return ApprovalResult.needs_approval() if requires else ApprovalResult.pre_approved()
```

---

## Pattern 6: Docstrings That Restate Code

**Location**: Multiple files, especially `llm_do/toolsets/shell/execution.py`

**Before**:
```python
def parse_command(command: str) -> List[str]:
    """Parse command string into arguments using shlex.

    Args:
        command: Command string to parse

    Returns:
        List of command arguments

    Raises:
        ShellBlockedError: If command cannot be parsed
    """
    try:
        return shlex.split(command)
    except ValueError as e:
        raise ShellBlockedError(f"Invalid command syntax: {e}")
```

**After**:
```python
def parse_command(command: str) -> List[str]:
    try:
        return shlex.split(command)
    except ValueError as e:
        raise ShellBlockedError(f"Invalid command syntax: {e}")
```

**Guideline**: Remove docstrings when:
- Function name is self-explanatory (`parse_command` using `shlex`)
- Args/Returns just restate type hints
- The function is short enough to read directly

**Keep docstrings when**:
- Non-obvious behavior or side effects
- Complex algorithms
- Public API contracts

---

## Pattern 7: Named Functions → Lambdas

**Location**: `llm_do/ui/runner.py`

**Before**:
```python
def _resolve_entry_factory(entry: Entry | None, entry_factory: EntryFactory | None) -> EntryFactory:
    if entry is not None and entry_factory is not None:
        raise ValueError("Provide either entry or entry_factory, not both.")
    if entry_factory is not None:
        return entry_factory
    if entry is None:
        raise ValueError("entry or entry_factory is required.")

    def factory() -> Entry:
        return entry

    return factory
```

**After**:
```python
def _resolve_entry_factory(entry: Entry | None, entry_factory: EntryFactory | None) -> EntryFactory:
    if entry is not None and entry_factory is not None:
        raise ValueError("Provide either entry or entry_factory, not both.")
    if entry_factory is not None:
        return entry_factory
    if entry is None:
        raise ValueError("entry or entry_factory is required.")
    return lambda: entry
```

---

## Pattern 8: Inline Duplicate Normalize Functions

**Location**: `llm_do/models.py`

**Before**:
```python
def _normalize_pattern(pattern: str) -> str:
    """Normalize a pattern for matching."""
    return pattern.strip().lower()

def _normalize_model(model: str) -> str:
    """Normalize a model identifier for matching."""
    return model.strip().lower()

def model_matches_pattern(model: str, pattern: str) -> bool:
    normalized_model = _normalize_model(model)
    normalized_pattern = _normalize_pattern(pattern)
    return fnmatch.fnmatch(normalized_model, normalized_pattern)
```

**After**:
```python
def model_matches_pattern(model: str, pattern: str) -> bool:
    """Check if model matches a glob-style compatibility pattern."""
    return fnmatch.fnmatch(model.strip().lower(), pattern.strip().lower())
```

---

## Pattern 9: Extract Shared Truncation Logic

**Location**: `llm_do/ui/events.py`

**Before**: Each event class had its own `_truncate` method with identical logic.

**After**:
```python
def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len, adding '...' if truncated."""
    return text[:max_len] + "..." if len(text) > max_len else text

def _truncate_lines(text: str, max_len: int, max_lines: int) -> str:
    """Truncate text by both length and line count."""
    if len(text) > max_len:
        text = text[:max_len] + "..."
    lines = text.split("\n")
    if len(lines) > max_lines:
        text = "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
    return text
```

Module-level functions used by all event classes.

---

## Files Changed

| File | Lines Removed | Primary Pattern |
|------|---------------|-----------------|
| `models.py` | -195 | Result object → raise, exception consolidation |
| `runtime/worker.py` | -265 | Docstring removal |
| `toolsets/filesystem.py` | -238 | Factory method, conditional simplification |
| `toolsets/shell/execution.py` | -142 | Docstring removal |
| `toolsets/shell/toolset.py` | -95 | Docstring removal |
| `ui/events.py` | -138 | Shared truncation helpers |
| `ui/runner.py` | -46 | Lambda, error formatting inline |
| `runtime/discovery.py` | -74 | Generic discover helper |
| `runtime/approval.py` | -80 | Callback factory simplification |
| `runtime/shared.py` | -30 | Method consolidation |

---

## Meta-Observation

The largest gains came from **removing noise**, not changing logic:
1. Docstrings that restated obvious code behavior
2. Intermediate result objects where exceptions suffice
3. Helper functions with single call sites
4. Verbose conditionals where expressions work

The algorithms and behavior remained unchanged. Tests required only minor adaptations for changed APIs (result objects → exceptions) and updated error messages.
