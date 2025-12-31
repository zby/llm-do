# CLI Reference

The `llm-do` command-line interface executes workers and tools from explicit `.worker` and `.py` files using the context-centric runtime.

## Basic Usage

```bash
# Run a worker (entry name defaults to "main")
llm-do main.worker "input message"

# Run a worker with Python toolsets
llm-do main.worker tools.py "input message"

# Choose a non-default entry name
llm-do orchestrator.worker helper.worker --entry orchestrator "input message"

# Code entry point (tool function as entry)
llm-do tools.py pitch_evaluator.worker --entry main "Go"
```

Provide the prompt via stdin when needed:

```bash
echo "input message" | llm-do main.worker
```

## OAuth

Use the OAuth helper to authenticate with Anthropic subscriptions:

```bash
llm-do-oauth login --provider anthropic
llm-do-oauth logout --provider anthropic
llm-do-oauth status --provider anthropic
```

Credentials are stored at `~/.llm-do/oauth.json`.

## Arguments

- `files` - One or more `.worker` or `.py` files. At least one required.
- `prompt` - Optional prompt string. If omitted and stdin is not a TTY, the prompt is read from stdin.

## Entry Resolution

- `--entry NAME` selects the entry point by name.
- Default entry name is `main`.
- Names can refer to:
  - Worker files (the `name` field in frontmatter)
  - `WorkerEntry` objects defined in Python files
  - Function tools discovered from `FunctionToolset`
- If the entry name is not found, the run fails with a list of available names.

## Worker File Toolsets

Worker frontmatter maps toolset names to configuration:

```yaml
---
name: main
toolsets:
  shell: {}
  filesystem: {}
  calc_tools: {}  # Python toolset name
  analyzer: {}    # Another worker name
---
```

Toolset names resolve to:
- Built-ins: `shell`, `filesystem`
- Python toolsets discovered from passed `.py` files (by variable name)
- Other worker entries from passed `.worker` files (by `name`)

## Model Selection

Model resolution uses this precedence for the entry worker:
1. `--model` flag (entry worker only)
2. `model` in the worker frontmatter
3. `LLM_DO_MODEL` environment variable

Delegated workers use their own `model` fields. If unset, they inherit the entry context's model (the resolved model after applying `--model` and/or `LLM_DO_MODEL`).

## Configuration Overrides

**`--set KEY=VALUE`** overrides entry worker frontmatter fields at runtime. Supports dot notation for nested fields and automatic type inference:

```bash
# Override model
llm-do main.worker --set model=anthropic:claude-haiku-4-5 "hello"

# Override toolset config
llm-do main.worker \
  --set toolsets.filesystem.write_approval=false \
  --set toolsets.shell.default.approval_required=false \
  "task"
```

**Type inference:**
- JSON: `--set server_side_tools='[{"tool_type":"web_search"}]'`
- Booleans: `true`, `false`, `yes`, `no`, `on`, `off` (case-insensitive)
- Numbers: `42`, `3.14`
- Strings: anything else

## Approvals

**`--approve-all`** auto-approves all LLM-invoked tool calls without prompting.

**`--reject-all`** auto-rejects all LLM-invoked tool calls that require approval without prompting.

Approvals apply only to LLM-invoked actions; user-invoked top-level entries are not gated.

Without either flag, approvals are interactive only in TUI mode. In headless or JSON mode, any tool that requires approval will fail with a permission error.

## Output Modes

| Mode | Flag | Notes |
|------|------|-------|
| TUI (default) | — | Uses Textual when stdout is a TTY and no `--headless`/`--json` is set. |
| Headless | `--headless` | Plain-text events to stderr with `-v`/`-vv`, final output to stdout. |
| JSON | `--json` | JSONL event stream to stderr. Cannot combine with `--tui`. |

**Verbosity:**
- `-v` shows tool calls and status updates.
- `-vv` streams model text deltas.

## Chat Mode

Use `--chat` to keep the TUI open for multi-turn conversations. Chat mode requires the TUI (either a TTY or `--tui`).

```bash
llm-do main.worker "hello" --chat
```

Input behavior in chat mode:
- `Enter` inserts a newline.
- `Ctrl+J` sends the message.

## Debugging

**`--debug`** prints full tracebacks on errors.
