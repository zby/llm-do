# CLI Reference

The `llm-do` command-line interface executes a manifest-defined project: `.worker` and `.py` files listed in `project.json`, linked into a single entry.
Internally, it follows the same `build_entry(...)` linking flow available to Python callers.

## Basic Usage

```bash
# Run a project via manifest
llm-do project.json "input message"

# Use manifest default input (entry.input)
llm-do project.json

# Provide JSON input
llm-do project.json --input-json '{"input":"Go"}'
```

Provide the prompt via stdin when needed:

```bash
echo "input message" | llm-do project.json
```

## OAuth

Use the OAuth helper to authenticate with provider subscriptions:

```bash
# Anthropic (Claude Pro/Max subscriptions)
llm-do-oauth login --provider anthropic
llm-do-oauth status --provider anthropic

# Logout
llm-do-oauth logout --provider anthropic
```

**Provider notes:**
- **anthropic**: Uses your Claude Pro/Max subscription. Requires pasting an authorization code.

Credentials are stored at `~/.llm-do/oauth.json`.

### OpenAI

OpenAI does not use OAuth. Set your API key via environment variable:

```bash
export OPENAI_API_KEY=sk-...
```

## Arguments

- `manifest` - Path to the project manifest (`project.json`).
- `prompt` - Optional prompt string. If omitted and stdin is not a TTY, the prompt is read from stdin.

## Entry Resolution

Exactly one entry candidate must exist in the file set:
- **Worker files**: mark the entry worker with `entry: true` in frontmatter.
- **Python files**: define a single `@entry` function.
- If multiple candidates exist (or none), loading fails with a descriptive error.

## Worker File Toolsets

Worker frontmatter declares toolsets as a list of names (config is defined in Python):

```yaml
---
name: main
toolsets:
  - shell_readonly
  - filesystem_project
  - calc_tools   # Python toolset name
  - analyzer     # Another worker name
---
```

Toolset names resolve to:
- Built-ins: `shell_readonly`, `shell_file_ops`, `filesystem_cwd`, `filesystem_project` (+ `_ro` variants)
- Python toolsets discovered from passed `.py` files (by variable name)
- Other worker entries from passed `.worker` files (by `name`)

## Worker Input Schemas

Worker frontmatter can declare a Pydantic input schema for tool calls:

```yaml
---
name: main
schema_in_ref: schemas.py:PitchInput
---
```

Supported forms:
- `module.Class`
- `path.py:Class` (relative to the worker file)

Schemas must subclass `WorkerArgs` and implement `prompt_spec()`. If `schema_in_ref` is omitted, the default schema is `WorkerInput`:

```python
from pydantic import Field

from llm_do.runtime import PromptSpec, WorkerArgs

class WorkerInput(WorkerArgs):
    input: str
    attachments: list[str] = Field(default_factory=list)

    def prompt_spec(self) -> PromptSpec:
        return PromptSpec(text=self.input, attachments=tuple(self.attachments))
```

Use `schema_in_ref` to guide tool-call structure (and optionally constrain
`attachments` with regex/enum rules). Attachments must remain a list of paths.

`prompt_spec().text` is used to build the LLM prompt (and `RunContext.prompt`
for logging/UI only). Tools should use their typed args, not prompt text.

## Model Selection

Model resolution uses this precedence:
1. `entry.model` in the manifest
2. `runtime.model` in the manifest
3. `LLM_DO_MODEL` environment variable

Delegated workers use their own `model` fields. If unset, they inherit the entry context's resolved model.

## Input Overrides

The manifest can provide default input via `entry.input`. CLI input (prompt or
`--input-json`) overrides it when `allow_cli_input` is true.

If `allow_cli_input` is false and a prompt is provided, the CLI exits with an error.

## Approvals

Approvals are configured in the manifest via `runtime.approval_mode`:
- `prompt` (interactive approvals in TUI)
- `approve_all`
- `reject_all`

Approvals apply only to LLM-invoked actions; user-invoked top-level entries are not gated.

In headless mode, `prompt` will fail when a tool requires approval (unless you set `return_permission_errors` in the manifest to return errors instead).

## Depth Limits

Set `runtime.max_depth` in the manifest to cap worker nesting depth (default: 5).

## Output Modes

| Mode | Flag | Notes |
|------|------|-------|
| TUI (default) | — | Uses Textual when stdout is a TTY and no `--headless` is set. |
| Headless | `--headless` | Plain-text events to stderr with `-v`/`-vv`, final output to stdout. |

**Verbosity:**
- `-v` shows tool calls and status updates.
- `-vv` streams model text deltas.

## Chat Mode

Use `--chat` to keep the TUI open for multi-turn conversations. Chat mode requires the TUI (either a TTY or `--tui`).

```bash
llm-do project.json "hello" --chat
```

Input behavior in chat mode:
- `Enter` inserts a newline.
- `Ctrl+J` sends the message.

## Debugging

**`--debug`** prints full tracebacks on errors.
