# CLI Configuration Overrides Design

## Overview

Add `--set` and `--override` flags to the CLI to allow runtime overrides of worker configuration without editing YAML files.

## Use Cases

1. **Quick experimentation**: Try different models without editing files
2. **Scripting**: Parameterize worker behavior in CI/CD
3. **Security hardening**: Force strict mode or limit sandboxes per invocation
4. **Development**: Temporarily enable/disable tools or change sandbox paths

## User Interface

### Option A: `--set` for Simple Overrides (Recommended)

Dot notation for nested fields, type-aware parsing:

```bash
# Override model
llm-do greeter "hello" --set model=openai:gpt-4o

# Override sandbox path
llm-do save_note "save a note" --set sandbox.paths.notes.root=/tmp/notes

# Add allowed worker
llm-do orchestrator --set allow_workers+=child_worker

# Disable network
llm-do worker --set sandbox.network_enabled=false

# Override tool rule
llm-do worker --set tool_rules.sandbox.write.approval_required=true

# Multiple overrides
llm-do worker \
  --set model=anthropic:claude-haiku-4-5 \
  --set sandbox.network_enabled=false \
  --set tool_rules.shell.allowed=false
```

**Syntax:**
- `key=value` - Set simple value
- `nested.key.path=value` - Dot notation for nested fields
- `list_key+=value` - Append to list
- `list_key-=value` - Remove from list
- Value parsing: strings, numbers, booleans (`true`/`false`), JSON for complex types

### Option B: `--override` for Complex JSON Patches

For bulk overrides or complex structures:

```bash
# JSON string
llm-do worker --override '{"model": "openai:gpt-4o", "sandbox": {"network_enabled": false}}'

# JSON file (automatic detection)
llm-do worker --override overrides.json

# Can combine with --set
llm-do worker \
  --override base-config.json \
  --set model=anthropic:claude-sonnet-4
```

**File example** (`overrides.json`):
```json
{
  "model": "openai:gpt-4o",
  "sandbox": {
    "network_enabled": false,
    "paths": {
      "work": {
        "root": "/tmp/work",
        "mode": "rw"
      }
    }
  },
  "tool_rules": {
    "shell": {
      "allowed": false
    }
  }
}
```

### Option C: Both (Recommended Implementation)

Support both `--set` and `--override` with precedence rules:
1. Load worker definition from YAML
2. Apply `--override` patches (in order)
3. Apply `--set` overrides (in order, can override `--override` values)

```bash
# Load base overrides from file, then tweak specific values
llm-do worker \
  --override production.json \
  --set model=$CUSTOM_MODEL \
  --set sandbox.paths.output.root=$OUTPUT_DIR
```

## Implementation Design

### 1. CLI Argument Parsing

Add to `cli.py`:

```python
parser.add_argument(
    "--set",
    action="append",
    dest="config_overrides",
    metavar="KEY=VALUE",
    help="Override worker config field (e.g., --set model=openai:gpt-4o). "
         "Use dot notation for nested fields. Can be specified multiple times."
)

parser.add_argument(
    "--override",
    action="append",
    dest="config_patches",
    metavar="JSON",
    help="Override worker config with JSON (string or file path). "
         "Can be specified multiple times. Applied before --set."
)
```

### 2. Override Application Module

Create `llm_do/config_overrides.py`:

```python
"""CLI configuration override utilities."""
from typing import Any, Dict, List, Optional
from pathlib import Path
import json

from .types import WorkerDefinition


def parse_set_override(spec: str) -> tuple[str, str, Any]:
    """Parse --set KEY=VALUE or KEY+=VALUE or KEY-=VALUE.

    Returns:
        (key_path, operator, value) where operator is '=', '+=', or '-='

    Examples:
        'model=gpt-4' → ('model', '=', 'gpt-4')
        'allow_workers+=child' → ('allow_workers', '+=', 'child')
        'sandbox.network_enabled=false' → ('sandbox.network_enabled', '=', False)
    """
    if '+=' in spec:
        key, value_str = spec.split('+=', 1)
        return (key.strip(), '+=', _parse_value(value_str))
    elif '-=' in spec:
        key, value_str = spec.split('-=', 1)
        return (key.strip(), '-=', _parse_value(value_str))
    elif '=' in spec:
        key, value_str = spec.split('=', 1)
        return (key.strip(), '=', _parse_value(value_str))
    else:
        raise ValueError(f"Invalid --set format: {spec}. Expected KEY=VALUE")


def _parse_value(value_str: str) -> Any:
    """Parse value with type inference.

    Order of attempts:
    1. JSON parsing (for complex types, lists, dicts)
    2. Boolean literals (true, false, True, False)
    3. Numbers (int, float)
    4. Strings (default)
    """
    value_str = value_str.strip()

    # Try JSON first (handles lists, dicts, null, numbers, booleans)
    try:
        return json.loads(value_str)
    except json.JSONDecodeError:
        pass

    # Boolean literals
    if value_str.lower() in ('true', 'yes', 'on'):
        return True
    if value_str.lower() in ('false', 'no', 'off'):
        return False

    # Numbers
    try:
        if '.' in value_str:
            return float(value_str)
        return int(value_str)
    except ValueError:
        pass

    # Default: string
    return value_str


def apply_set_override(data: Dict[str, Any], key_path: str, operator: str, value: Any) -> None:
    """Apply a single --set override to the data dictionary.

    Args:
        data: Worker definition as dict (modified in place)
        key_path: Dot-separated path (e.g., 'sandbox.network_enabled')
        operator: '=', '+=', or '-='
        value: Parsed value to apply
    """
    keys = key_path.split('.')
    target = data

    # Navigate to the parent of the target field
    for key in keys[:-1]:
        if key not in target:
            target[key] = {}
        target = target[key]
        if not isinstance(target, dict):
            raise ValueError(f"Cannot navigate through non-dict at '{key}' in path '{key_path}'")

    final_key = keys[-1]

    if operator == '=':
        # Simple assignment
        target[final_key] = value

    elif operator == '+=':
        # Append to list
        if final_key not in target:
            target[final_key] = []
        if not isinstance(target[final_key], list):
            raise ValueError(f"Cannot append to non-list field: {key_path}")
        target[final_key].append(value)

    elif operator == '-=':
        # Remove from list
        if final_key not in target or not isinstance(target[final_key], list):
            raise ValueError(f"Cannot remove from non-list field: {key_path}")
        try:
            target[final_key].remove(value)
        except ValueError:
            raise ValueError(f"Value {value!r} not found in list at {key_path}")


def apply_json_override(data: Dict[str, Any], json_spec: str) -> None:
    """Apply a --override JSON patch to the data dictionary.

    Args:
        data: Worker definition as dict (modified in place)
        json_spec: JSON string or path to JSON file
    """
    # Check if it's a file path
    path = Path(json_spec)
    if path.exists():
        override_data = json.loads(path.read_text(encoding='utf-8'))
    else:
        override_data = json.loads(json_spec)

    # Deep merge: override_data patches data
    _deep_merge(data, override_data)


def _deep_merge(target: Dict, source: Dict) -> None:
    """Deep merge source into target (modifies target in place)."""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def apply_cli_overrides(
    definition: WorkerDefinition,
    *,
    json_patches: Optional[List[str]] = None,
    set_overrides: Optional[List[str]] = None,
) -> WorkerDefinition:
    """Apply CLI overrides to a worker definition.

    Args:
        definition: Original worker definition
        json_patches: List of --override JSON specs (applied first)
        set_overrides: List of --set KEY=VALUE specs (applied second)

    Returns:
        New WorkerDefinition with overrides applied and validated

    Raises:
        ValueError: If overrides are invalid or violate schema
    """
    # Convert to dict for manipulation
    data = definition.model_dump(mode='python', exclude_unset=False)

    # Apply JSON patches first (in order)
    if json_patches:
        for patch_spec in json_patches:
            apply_json_override(data, patch_spec)

    # Apply --set overrides second (in order, can override JSON patches)
    if set_overrides:
        for set_spec in set_overrides:
            key_path, operator, value = parse_set_override(set_spec)
            apply_set_override(data, key_path, operator, value)

    # Validate by reconstructing WorkerDefinition
    try:
        return WorkerDefinition.model_validate(data)
    except Exception as e:
        raise ValueError(f"Overrides resulted in invalid worker definition: {e}")
```

### 3. Integration into CLI

Update `cli.py`:

```python
from .config_overrides import apply_cli_overrides

def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    # ... existing setup ...

    registry = WorkerRegistry(registry_root)

    # Load worker definition
    original_definition = registry.load_definition(worker_name)

    # Apply CLI overrides if provided
    if args.config_patches or args.config_overrides:
        definition = apply_cli_overrides(
            original_definition,
            json_patches=args.config_patches,
            set_overrides=args.config_overrides,
        )

        # Optionally log what was overridden in debug mode
        if args.debug and not args.json:
            console.print(f"[dim]Applied {len(args.config_patches or [])} JSON patches and "
                         f"{len(args.config_overrides or [])} --set overrides[/dim]")
    else:
        definition = original_definition

    # Continue with execution using modified definition
    # NOTE: run_worker currently takes worker NAME, not definition
    # We need to either:
    # 1. Pass definition directly (requires API change), OR
    # 2. Temporarily inject modified definition into registry

    # Option 2 (minimal change):
    registry._definitions_cache[worker_name] = definition  # Inject override

    result = run_worker(
        registry=registry,
        worker=worker_name,  # Will now load our overridden definition
        input_data=input_data,
        # ... rest of args
    )
```

## Field Override Reference

### Common Overrides

| Field | Example | Use Case |
|-------|---------|----------|
| `model` | `--set model=openai:gpt-4o` | Try different models |
| `sandbox.network_enabled` | `--set sandbox.network_enabled=false` | Disable network |
| `sandbox.paths.work.root` | `--set sandbox.paths.work.root=/tmp/work` | Change working directory |
| `sandbox.paths.work.mode` | `--set sandbox.paths.work.mode=ro` | Make sandbox read-only |
| `allow_workers` | `--set allow_workers+=new_worker` | Add delegatable worker |
| `tool_rules.shell.allowed` | `--set tool_rules.shell.allowed=false` | Disable shell |
| `tool_rules.sandbox.write.approval_required` | `--set tool_rules.sandbox.write.approval_required=true` | Require write approval |
| `attachment_policy.max_attachments` | `--set attachment_policy.max_attachments=10` | Allow more attachments |

### Complex Overrides (via --override)

**Completely replace sandbox:**
```json
{
  "sandbox": {
    "network_enabled": false,
    "paths": {
      "readonly_data": {
        "root": "/data/prod",
        "mode": "ro"
      }
    }
  }
}
```

**Add multiple tool rules:**
```json
{
  "tool_rules": {
    "shell": {"allowed": false},
    "sandbox.write": {"allowed": true, "approval_required": true},
    "worker.create": {"allowed": false}
  }
}
```

## Validation and Error Handling

1. **Parse errors**: Show clear message with failing override
2. **Schema violations**: Validate via Pydantic and show which field failed
3. **Type mismatches**: Explain expected type vs provided type
4. **Missing paths**: Detect non-existent nested keys early

Example error messages:
```
Error: Invalid --set override 'model.unknown=value'
  Worker definition has no field 'model.unknown'

Error: Invalid --set override 'allow_workers=5'
  Field 'allow_workers' expects a list, got int

Error: Invalid --override: JSON parse error at line 3
  Expected ',' or '}' after object member
```

## Security Considerations

1. **Locked workers**: Respect `locked: true` flag
   - Either reject overrides entirely, or
   - Only allow specific safe overrides (model, attachments)

2. **Privilege escalation**: Don't allow overrides that weaken security
   - Consider: Only allow overrides that make config MORE restrictive?
   - Or: Require `--force-overrides` flag with clear warning

3. **File path validation**: Validate sandbox paths exist and are safe

## Testing Strategy

### Unit Tests

```python
def test_parse_set_override_simple():
    key, op, val = parse_set_override("model=gpt-4")
    assert key == "model"
    assert op == "="
    assert val == "gpt-4"

def test_parse_set_override_nested():
    key, op, val = parse_set_override("sandbox.network_enabled=false")
    assert key == "sandbox.network_enabled"
    assert val is False

def test_apply_set_override():
    data = {"model": "old"}
    apply_set_override(data, "model", "=", "new")
    assert data["model"] == "new"

def test_apply_json_override():
    data = {"model": "old"}
    apply_json_override(data, '{"model": "new", "locked": true}')
    assert data["model"] == "new"
    assert data["locked"] is True
```

### Integration Tests

```python
def test_cli_override_model(tmp_path):
    """Test --set model=... overrides worker model."""
    # Create test worker
    # Run with --set model=test-model
    # Verify correct model was used

def test_cli_multiple_overrides(tmp_path):
    """Test multiple --set flags are applied in order."""
    # Create test worker
    # Run with --set model=a --set model=b
    # Verify b wins (last override wins)

def test_cli_override_plus_json(tmp_path):
    """Test --override JSON and --set work together."""
    # Create JSON patch file
    # Run with --override file.json --set additional=override
    # Verify both applied correctly
```

## Future Enhancements

1. **Override profiles**: Predefined override sets
   ```bash
   llm-do worker --profile production
   # Loads ~/.llm-do/profiles/production.json
   ```

2. **Environment variable expansion**:
   ```bash
   --set sandbox.paths.output.root=$OUTPUT_DIR
   ```

3. **Override validation mode**:
   ```bash
   llm-do worker --validate-overrides overrides.json
   # Check overrides without running
   ```

4. **Diff mode**:
   ```bash
   llm-do worker --show-overrides --set model=gpt-4
   # Shows what changed
   ```

## Recommendation

**Implement Option C**: Support both `--set` and `--override` with clear precedence.

**Phase 1 (MVP)**:
- Implement `--set KEY=VALUE` for simple overrides
- Support dot notation and basic types (string, number, boolean)
- Validate via Pydantic schema

**Phase 2**:
- Add `--override JSON` support
- Add list operators (`+=`, `-=`)
- Add detailed error messages

**Phase 3**:
- Add override profiles
- Add validation mode
- Add diff/preview mode
