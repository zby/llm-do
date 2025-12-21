# CLI Reference

The `llm-do` command-line interface runs tools (workers or code) with runtime configuration, approval modes, and output formatting.

## Basic Usage

```bash
# Run main tool in current directory
llm-do "input message"

# Run specific tool in current directory
llm-do --tool greeter "input message"

# Run main tool from a different directory
llm-do --dir /path/to/project "input message"

# Run specific tool from a different directory
llm-do --dir /path/to/project --tool analyzer "input message"
```

**Arguments:**
- `MESSAGE` — Plain text input message. Use `--input` for JSON instead.
- `--dir` — Registry root directory (defaults to current working directory)
- `--tool` — Tool name to run (defaults to `main`)

**Entry point resolution:**
- `tools.py::main` → code tool entry point
- `main.worker` → worker entry point
- Both present → error (no ambiguity)

## Core Options

### Input and Output

**`--input JSON`**
Provide JSON input instead of plain text message. Accepts inline JSON or path to JSON file:
```bash
llm-do --tool greeter --input '{"query": "hello", "format": "brief"}'
llm-do --tool greeter --input input.json
```

**`--attachments FILE [FILE ...]`**
Pass attachment files to the worker:
```bash
llm-do --tool pitch_evaluator --attachments deck.pdf
llm-do --tool processor --attachments file1.txt file2.csv
```

**`--json`**
Output structured JSON instead of TUI display (useful for scripting):
```bash
llm-do --tool greeter "hello" --json --approve-all | jq '.output'
```

**`--headless`**
Force non-interactive mode regardless of TTY detection. If stdin is a TTY and no approval flags are provided, the CLI prompts for approvals. If stdin is not a TTY, you must use `--approve-all` or `--strict`:
```bash
llm-do --tool greeter "task" --headless --approve-all
```

**`--no-rich`**
Disable Rich formatting (plain text, no ANSI colors). Applies to headless output and the post-TUI log buffer:
```bash
llm-do --tool greeter "task" --no-rich
```

### Worker Configuration

**`--model MODEL`**
Override the model for this run. If omitted, `llm-do` resolves an effective model with this precedence (highest to lowest):

1. CLI `--model` flag
2. Worker's `model` field
3. `LLM_DO_MODEL` environment variable

If none of these are set, the run errors with "No model configured".
```bash
llm-do --tool greeter "hello" --model anthropic:claude-sonnet-4-20250514
llm-do --tool greeter "hello" --model openai:gpt-4o
```

Model names follow [PydanticAI conventions](https://ai.pydantic.dev/models/).

**Default model example:**
```bash
# Global default for all runs
export LLM_DO_MODEL=anthropic:claude-haiku-4-5
```

**Model Compatibility:** Workers can declare `compatible_models` patterns to restrict which models can be used. If specified, the `--model` value is validated against these patterns:
```bash
# Worker declares: compatible_models: ["anthropic:*"]
llm-do --tool pdf_analyzer --model openai:gpt-4o  # Error: incompatible model
llm-do --tool pdf_analyzer --model anthropic:claude-sonnet-4  # OK
```

See [Model Compatibility](#model-compatibility) below for pattern syntax.

**`--dir PATH`**
Specify tool registry root (defaults to current working directory):
```bash
llm-do --dir /path/to/workers "hello"
```

This is useful for "relocatable workers" — workers that you run against different target directories:
```bash
cd /project-to-analyze
llm-do --dir ~/code-analyzer "analyze the code in current directory"
```
The worker loads from `--dir` but filesystem tools operate on the current working directory.

**`--creation-defaults FILE`**
Provide JSON file with default settings for worker creation (for workers that create other workers):
```bash
llm-do --tool orchestrator --creation-defaults defaults.json
```

**`--set KEY=VALUE`**
Override worker configuration fields at runtime without editing YAML files. Supports dot notation for nested fields and automatic type inference:

```bash
# Override model
llm-do --tool greeter "hello" --set model=openai:gpt-4o

# Override multiple fields
llm-do --tool greeter "task" \
  --set model=anthropic:claude-haiku-4-5 \
  --set attachment_policy.max_attachments=5 \
  --set locked=true
```

**Type inference:**
- JSON: `--set attachment_policy.allowed_suffixes='[".md", ".txt"]'`
- Booleans: `true`, `false`, `yes`, `no`, `on`, `off` (case-insensitive)
- Numbers: `42`, `3.14`
- Strings: anything else

**Dot notation:**
- Simple: `model=gpt-4`
- Nested: `attachment_policy.max_total_bytes=1000000`

See [Configuration Overrides](#configuration-overrides) below for examples.

### Approval Modes

Control which tools require human review:

**`--approve-all`**
Auto-approve all tool calls without prompting (use with caution):
```bash
llm-do --tool greeter "task" --approve-all
```

**`--strict`**
Reject all non-pre-approved tools (deny-by-default security mode):
```bash
llm-do --tool greeter "task" --strict
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
| Headless | `--headless` | Stdin TTY or approval flags | CI/CD, pipes, containers (plain text) |

**Auto-detection:** Without explicit flags, the CLI detects whether it's running in a TTY:
- **TTY present:** Textual TUI with interactive approval prompts. After TUI exits, colorful output is printed to terminal history.
- **No TTY:** Falls back to headless rendering (Rich by default, plain with `--no-rich`). If stdin is not a TTY and no approval flags are set, headless mode enforces strict behavior.

The `--json` and `--headless` flags are mutually exclusive. `--json` also implies `--no-rich`.

### Debugging

**`--debug`**
Show full stack traces on errors:
```bash
llm-do --tool greeter "task" --debug
```

Without `--debug`, errors are displayed concisely.

## Configuration Overrides

The `--set` flag enables runtime configuration overrides without modifying YAML files.

### Common Use Cases

**Quick experimentation:**
```bash
# Try different models
llm-do --tool greeter "hello" --set model=openai:gpt-4o
llm-do --tool greeter "hello" --set model=anthropic:claude-sonnet-4
```

**Production hardening:**
```bash
# Lock worker and limit attachments
llm-do --tool greeter "task" \
  --set locked=true \
  --set attachment_policy.max_attachments=1 \
  --set attachment_policy.max_total_bytes=1000000
```

**CI/CD parameterization:**
```bash
# Inject environment-specific settings
llm-do --tool processor "data" \
  --set model=$CI_MODEL
```

### Common Override Fields

| Field | Example | Use Case |
|-------|---------|----------|
| `model` | `--set model=openai:gpt-4o` | Try different models |
| `compatible_models` | `--set compatible_models='["anthropic:*"]'` | Restrict allowed models |
| `description` | `--set description="Updated desc"` | Document runtime purpose |
| `locked` | `--set locked=true` | Prevent worker creation |
| `toolsets.delegation.NAME` | `--set toolsets.delegation.summarizer={}` | Expose worker tool |
| `attachment_policy.max_attachments` | `--set attachment_policy.max_attachments=10` | Adjust limits |
| `attachment_policy.max_total_bytes` | `--set attachment_policy.max_total_bytes=5000000` | Adjust size limits |
| `server_side_tools` | `--set server_side_tools='[{"tool_type":"web_search"}]'` | Enable provider tools (PydanticAI `builtin_tools`) |

### Validation

Overrides are validated against the worker schema. Invalid overrides produce clear error messages:

```bash
$ llm-do --tool greeter --set attachment_policy.max_attachments=not-a-number
Configuration override error: Overrides resulted in invalid worker configuration: ...
  Field 'attachment_policy.max_attachments' expects int, got str
```

### Precedence

When multiple `--set` flags target the same field, **last wins**:
```bash
llm-do --tool greeter --set model=gpt-4 --set model=claude-sonnet
# Uses: claude-sonnet
```

## Model Compatibility

Workers can declare which models they're compatible with using the `compatible_models` field in their definition. This enables workers to enforce model requirements—for example, workers that process PDFs natively require Anthropic models.

### Worker Definition

```yaml
# pdf_analyzer.worker (at project root)
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

All models selected via the resolution rules are validated against `compatible_models`, including worker defaults and `LLM_DO_MODEL`.

When a worker delegates to another worker, the callee resolves (and validates) its own model using the same precedence; the caller’s model is not inherited.

```bash
# Worker has compatible_models: ["anthropic:*"]
$ llm-do --tool pdf_analyzer --model openai:gpt-4o
Error: Model 'openai:gpt-4o' is not compatible with worker 'pdf_analyzer'.
Compatible patterns: 'anthropic:*'
```

## Project Initialization

Create a new project with `llm-do init`:

```bash
llm-do init my-project
```

Creates a `main.worker` file with basic front matter. Options:
```bash
llm-do init my-project --model anthropic:claude-haiku-4-5
llm-do init my-project --name "My Assistant"
```

## Exit Codes

- `0` — Success
- `1` — Error (file not found, invalid input, model API error, etc.)

## Examples

**Run main.worker in current directory:**
```bash
cd examples/greeter
llm-do "Tell me a joke"
```

**Run a specific worker:**
```bash
cd examples/greeter
llm-do --tool greeter "Tell me a joke"
```

**Run worker from a different directory:**
```bash
llm-do --dir ~/my-project "process this"
```

**JSON output for scripting:**
```bash
result=$(llm-do --tool greeter "query" --json --approve-all)
echo "$result" | jq '.output'
```

**Auto-approve for CI/CD:**
```bash
llm-do "automated task" --approve-all --json > output.json
```

**Runtime config override:**
```bash
llm-do "task" --set model=openai:gpt-4o --approve-all
```

**Production hardening:**
```bash
llm-do "task" \
  --set locked=true \
  --set attachment_policy.max_attachments=1 \
  --strict
```

**Relocatable workers (analyze any directory):**
```bash
cd /project-to-analyze
llm-do --dir ~/code-analyzer "analyze the code"
```

## Related Documentation

- [Worker Delegation](worker_delegation.md) — Worker-to-worker calls
- [Architecture](architecture.md) — Runtime and approval system
- [UI Architecture](ui.md) — Display backends and event rendering
