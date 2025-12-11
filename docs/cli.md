# CLI Reference

The `llm-do` command-line interface runs programs and workers with runtime configuration, approval modes, and output formatting.

## Basic Usage

```bash
# Run a program (finds main.worker in directory)
llm-do ./my-program "input message"

# Run a single worker file
llm-do ./path/to/worker.worker "input message"

# Run with options
llm-do TARGET [MESSAGE] [OPTIONS]
```

**Arguments:**
- `TARGET` — Program directory (with `main.worker`) or path to `.worker` file
- `MESSAGE` — Optional plain text input message. Use `--input` for JSON instead.

## Core Options

### Input and Output

**`--input JSON`**
Provide JSON input instead of plain text message. Accepts inline JSON or path to JSON file:
```bash
llm-do worker --input '{"query": "hello", "format": "brief"}'
llm-do worker --input input.json
```

**`--attachments FILE [FILE ...]`**
Pass attachment files to the worker:
```bash
llm-do pitch_evaluator --attachments deck.pdf
llm-do processor --attachments file1.txt file2.csv
```

**`--json`**
Output structured JSON instead of TUI display (useful for scripting):
```bash
llm-do worker "hello" --json --approve-all | jq '.output'
```

**`--headless`**
Force non-interactive mode regardless of TTY detection (requires `--approve-all` or `--strict`):
```bash
llm-do worker "task" --headless --approve-all
```

### Worker Configuration

**`--model MODEL`**
Override the worker's default model. Required if worker has no model specified:
```bash
llm-do greeter "hello" --model anthropic:claude-sonnet-4-20250514
llm-do greeter "hello" --model openai:gpt-4o
```

Model names follow [PydanticAI conventions](https://ai.pydantic.dev/models/).

**Model Compatibility:** Workers can declare `compatible_models` patterns to restrict which models can be used. If specified, the `--model` value is validated against these patterns:
```bash
# Worker declares: compatible_models: ["anthropic:*"]
llm-do pdf_analyzer --model openai:gpt-4o  # Error: incompatible model
llm-do pdf_analyzer --model anthropic:claude-sonnet-4  # OK
```

See [Model Compatibility](#model-compatibility) below for pattern syntax.

**`--entry WORKER`**
Override the entry point when running a program (default is `main`):
```bash
llm-do ./my-program --entry analyzer "input"
llm-do ./my-program --entry workers/helper "input"
```

**`--registry PATH`**
Specify worker registry root (defaults to program directory or current working directory):
```bash
llm-do worker "hello" --registry /path/to/workers
```

**`--creation-defaults FILE`**
Provide JSON file with default settings for worker creation (for workers that create other workers):
```bash
llm-do orchestrator --creation-defaults defaults.json
```

**`--set KEY=VALUE`** *(New in Phase 1)*
Override worker configuration fields at runtime without editing YAML files. Supports dot notation for nested fields and automatic type inference:

```bash
# Override model
llm-do greeter "hello" --set model=openai:gpt-4o

# Override nested sandbox configuration
llm-do worker "task" --set sandbox.network_enabled=false

# Override multiple fields
llm-do worker "task" \
  --set model=anthropic:claude-haiku-4-5 \
  --set attachment_policy.max_attachments=5 \
  --set locked=true

# Override sandbox paths for different environments
llm-do save_note "note text" --set sandbox.paths.notes.root=/tmp/notes
```

**Type inference:**
- JSON: `--set allow_workers='["worker1", "worker2"]'`
- Booleans: `true`, `false`, `yes`, `no`, `on`, `off` (case-insensitive)
- Numbers: `42`, `3.14`
- Strings: anything else

**Dot notation:**
- Simple: `model=gpt-4`
- Nested: `sandbox.network_enabled=false`
- Deep: `attachment_policy.max_total_bytes=1000000`

See [Configuration Overrides](#configuration-overrides) below for examples.

### Approval Modes

Control which tools require human review:

**`--approve-all`**
Auto-approve all tool calls without prompting (use with caution):
```bash
llm-do worker "task" --approve-all
```

**`--strict`**
Reject all non-pre-approved tools (deny-by-default security mode):
```bash
llm-do worker "task" --strict
```

**Default (interactive mode)**
Prompt for approval when workers request gated tools. Requires a TTY:
```
Approval choice [a/s/d/q]:
  [a] Approve and continue
  [s] Approve for remainder of session
  [d] Deny and abort
  [q] Quit run
```

For non-interactive environments (CI/CD, scripts), you must use `--approve-all` or `--strict`.

### Output Modes

The CLI supports multiple output modes for different use cases:

| Mode | Flag | Requirements | Use Case |
|------|------|--------------|----------|
| TUI (default) | — | TTY required | Interactive terminal sessions |
| JSON | `--json` | `--approve-all` or `--strict` | Scripting and automation |
| Headless | `--headless` | `--approve-all` or `--strict` | CI/CD, pipes, containers |

**Auto-detection:** Without explicit flags, the CLI detects whether it's running in a TTY:
- **TTY present:** Textual TUI with interactive approval prompts
- **No TTY:** Fails unless `--approve-all`, `--strict`, or `--json` is specified

The `--json` and `--headless` flags are mutually exclusive.

### Debugging

**`--debug`**
Show full stack traces on errors:
```bash
llm-do worker "task" --debug
```

Without `--debug`, errors are displayed concisely.

## Configuration Overrides

The `--set` flag enables runtime configuration overrides without modifying YAML files.

### Common Use Cases

**Quick experimentation:**
```bash
# Try different models
llm-do greeter "hello" --set model=openai:gpt-4o
llm-do greeter "hello" --set model=anthropic:claude-sonnet-4
```

**Production hardening:**
```bash
# Lock worker and limit attachments
llm-do worker "task" \
  --set locked=true \
  --set attachment_policy.max_attachments=1 \
  --set attachment_policy.max_total_bytes=1000000
```

**Development environments:**
```bash
# Change sandbox paths for local testing
llm-do save_note "text" \
  --set sandbox.paths.notes.root=/tmp/test-notes \
  --set sandbox.paths.notes.mode=rw
```

**CI/CD parameterization:**
```bash
# Inject environment-specific settings
llm-do processor "data" \
  --set model=$CI_MODEL \
  --set sandbox.paths.work.root=$WORKSPACE_DIR
```

### Common Override Fields

| Field | Example | Use Case |
|-------|---------|----------|
| `model` | `--set model=openai:gpt-4o` | Try different models |
| `compatible_models` | `--set compatible_models='["anthropic:*"]'` | Restrict allowed models |
| `description` | `--set description="Updated desc"` | Document runtime purpose |
| `locked` | `--set locked=true` | Prevent worker creation |
| `allow_workers` | `--set allow_workers='["child"]'` | Control delegation |
| `attachment_policy.max_attachments` | `--set attachment_policy.max_attachments=10` | Adjust limits |
| `attachment_policy.max_total_bytes` | `--set attachment_policy.max_total_bytes=5000000` | Adjust size limits |
| `sandbox.network_enabled` | `--set sandbox.network_enabled=false` | Disable network (future) |
| `sandbox.paths.NAME.root` | `--set sandbox.paths.work.root=/tmp` | Change directories |
| `sandbox.paths.NAME.mode` | `--set sandbox.paths.work.mode=ro` | Make read-only |
| `server_side_tools` | `--set server_side_tools='[{"tool_type":"web_search"}]'` | Enable provider tools (PydanticAI `builtin_tools`) |

### Validation

Overrides are validated against the worker schema. Invalid overrides produce clear error messages:

```bash
$ llm-do worker --set attachment_policy.max_attachments=not-a-number
Configuration override error: Overrides resulted in invalid worker configuration: ...
  Field 'attachment_policy.max_attachments' expects int, got str
```

### Precedence

When multiple `--set` flags target the same field, **last wins**:
```bash
llm-do worker --set model=gpt-4 --set model=claude-sonnet
# Uses: claude-sonnet
```

## Model Compatibility

Workers can declare which models they're compatible with using the `compatible_models` field in their definition. This enables workers to enforce model requirements—for example, workers that process PDFs natively require Anthropic models.

### Worker Definition

```yaml
# workers/pdf_analyzer.worker
---
name: pdf_analyzer
compatible_models:
  - "anthropic:*"    # Only Anthropic models
---
You analyze PDF documents...
```

### Pattern Syntax

| Pattern | Matches |
|---------|---------|
| `*` | Any model |
| `anthropic:*` | Any Anthropic model |
| `anthropic:claude-haiku-*` | Claude Haiku variants |
| `openai:gpt-4*` | GPT-4 variants |
| `anthropic:claude-sonnet-4` | Exact model match |

### Behavior

- **Unset (`compatible_models: null`)**: Any model allowed (default, backward compatible)
- **Wildcard (`["*"]`)**: Explicitly allows any model
- **Patterns (`["anthropic:*", "openai:gpt-4o"]`)**: Model must match at least one pattern
- **Empty list (`[]`)**: Invalid configuration (error)

### Validation

The `--model` CLI flag and caller's model (during delegation) are validated against `compatible_models`. The worker's own `model` field bypasses validation (trusted).

```bash
# Worker has compatible_models: ["anthropic:*"]
$ llm-do pdf_analyzer --model openai:gpt-4o
Error: Model 'openai:gpt-4o' is not compatible with worker 'pdf_analyzer'.
Compatible patterns: 'anthropic:*'
```

## Program Initialization

Create a new program with `llm-do init`:

```bash
llm-do init my-program
```

Creates:
```
my-program/
├── main.worker
├── input/
└── output/
```

## Exit Codes

- `0` — Success
- `1` — Error (file not found, invalid input, model API error, etc.)

## Examples

**Run a program:**
```bash
llm-do ./examples/greeter "Tell me a joke"
```

**Run with different entry point:**
```bash
llm-do ./my-program --entry analyzer "input"
```

**JSON output for scripting:**
```bash
result=$(llm-do ./my-program "query" --json)
echo "$result" | jq '.output'
```

**Auto-approve for CI/CD:**
```bash
llm-do ./my-program "automated task" --approve-all --json > output.json
```

**Runtime config override:**
```bash
llm-do ./my-program "task" --set model=openai:gpt-4o --approve-all
```

**Production hardening:**
```bash
llm-do ./my-program "task" \
  --set locked=true \
  --set attachment_policy.max_attachments=1 \
  --strict
```

## Related Documentation

- [Worker Delegation](worker_delegation.md) — Worker-to-worker calls
- [Architecture](architecture.md) — Sandbox, runtime, and approval system
- [UI Architecture](ui.md) — Display backends and event rendering
