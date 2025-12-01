# CLI Reference

The `llm-do` command-line interface provides flexible control over worker execution with runtime configuration, approval modes, and output formatting.

## Basic Usage

```bash
llm-do WORKER [MESSAGE] [OPTIONS]
```

**Arguments:**
- `WORKER` — Worker name or path to `.yaml` file (e.g., `greeter` or `examples/greeter.yaml`)
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
Output structured JSON instead of rich formatted display (useful for scripting):
```bash
llm-do worker "hello" --json | jq '.output'
```

### Worker Configuration

**`--model MODEL`**
Override the worker's default model. Required if worker has no model specified:
```bash
llm-do greeter "hello" --model anthropic:claude-sonnet-4-20250514
llm-do greeter "hello" --model openai:gpt-4o
```

Model names follow [PydanticAI conventions](https://ai.pydantic.dev/models/).

**`--registry PATH`**
Specify worker registry root (defaults to current working directory):
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
| `description` | `--set description="Updated desc"` | Document runtime purpose |
| `locked` | `--set locked=true` | Prevent worker creation |
| `allow_workers` | `--set allow_workers='["child"]'` | Control delegation |
| `attachment_policy.max_attachments` | `--set attachment_policy.max_attachments=10` | Adjust limits |
| `attachment_policy.max_total_bytes` | `--set attachment_policy.max_total_bytes=5000000` | Adjust size limits |
| `sandbox.network_enabled` | `--set sandbox.network_enabled=false` | Disable network (future) |
| `sandbox.paths.NAME.root` | `--set sandbox.paths.work.root=/tmp` | Change directories |
| `sandbox.paths.NAME.mode` | `--set sandbox.paths.work.mode=ro` | Make read-only |
| `shell_cwd` | `--set shell_cwd=/path/to/dir` | Override shell working directory |

### Shell Working Directory

By default, shell commands run from the **user's current directory** (`cwd`). Workers can override this with the `shell_cwd` field:

```yaml
# Worker definition
name: analyzer
shell_cwd: "."  # Run from registry root
```

Override at runtime:
```bash
# Run shell commands from specific directory
llm-do code_analyzer "analyze" --set shell_cwd=/some/project

# Run from registry root
llm-do code_analyzer "analyze" --set shell_cwd=.
```

**Behavior:**
- **No `shell_cwd` specified**: Shell runs from user's current directory
- **Relative path** (e.g., `subdir`): Resolved relative to registry root
- **Absolute path** (e.g., `/tmp/work`): Used as-is
- **`.` (dot)**: Explicitly use registry root

**Worker creation:** New workers always go to `{registry.root}/workers/generated/`, regardless of `shell_cwd`.

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

## Exit Codes

- `0` — Success
- `1` — Error (file not found, invalid input, model API error, etc.)

## Examples

**Basic conversation:**
```bash
llm-do greeter "Tell me a joke" --model anthropic:claude-3-5-haiku-20241022
```

**JSON output for scripting:**
```bash
result=$(llm-do worker "query" --json)
echo "$result" | jq '.output'
```

**Attachment processing:**
```bash
llm-do pitch_evaluator --attachments input/deck.pdf --model $MODEL
```

**Auto-approve for CI/CD:**
```bash
llm-do worker "automated task" --approve-all --json > output.json
```

**Runtime model override:**
```bash
llm-do worker "task" --set model=openai:gpt-4o --approve-all
```

**Production hardening:**
```bash
llm-do production_worker "task" \
  --set locked=true \
  --set attachment_policy.max_attachments=1 \
  --strict
```

## Related Documentation

- [Worker Delegation](worker_delegation.md) — Worker-to-worker calls
- [Architecture](architecture.md) — Sandbox, runtime, and approval system
