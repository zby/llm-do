# CLI Reference

The `llm-do` command-line interface executes a manifest-defined project: `.agent` and `.py` files listed in `project.json`, linked into a single entry.
Internally, it builds the agent registry and resolves the entry declared in the manifest.

## Basic Usage

```bash
# Run a project via manifest
llm-do project.json "input message"

# Use manifest default input (entry.args)
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

Entry selection is explicit in the manifest:
- `entry.agent` selects an agent name from `.agent` files.
- `entry.function` selects a Python function via `path.py:function` (must be listed in `python_files`).
- If the target cannot be resolved, loading fails with a descriptive error.

## Worker File Tools & Toolsets

Worker frontmatter declares tools and toolsets as lists of names (config is defined in Python):

```yaml
---
name: main
tools:
  - normalize_path
toolsets:
  - shell_readonly
  - filesystem_project
  - calc_tools   # Python toolset name
  - analyzer     # Another worker name
---
```

Tool names resolve to:
- Python tools exported via `TOOLS` (dict or list) or `__all__` in passed `.py` files

Toolset names resolve to:
- Built-ins: `shell_readonly`, `shell_file_ops`, `filesystem_cwd`, `filesystem_project` (+ `_ro` variants)
- Python toolsets exported via `TOOLSETS` (dict or list), or module-level `AbstractToolset` instances
- Other worker entries from passed `.agent` files (by `name`)

## Worker Input Models

Worker frontmatter can declare a Pydantic input model for tool calls:

```yaml
---
name: main
input_model_ref: schemas.py:PitchInput
---
```

Supported forms:
- `module.Class`
- `path.py:Class` (relative to the worker file)

Input models must subclass `AgentArgs` and implement `prompt_messages()`. Input is passed as a dict
validated into the input model (default expects `"input"` plus optional `"attachments"`):

- With attachments: `{"input": "text", "attachments": ["file.pdf"]}`

Use `input_model_ref` for custom validation or typed tool-call structure.

`prompt_messages()` is used to build the LLM prompt (and `RunContext.prompt`
for logging/UI only). Tools should use their typed args, not prompt text.

## Model Selection

Model resolution happens when agents are constructed:
1. `model` in the worker definition (string in `.agent`) or a `Model` instance in a Python `AgentSpec`
2. `LLM_DO_MODEL` environment variable (fallback)

When building `AgentSpec` in Python, pass a resolved `Model` (use `resolve_model("provider:model")` or a
PydanticAI model instance).

`compatible_models` is only checked against the env fallback for `.agent`/dynamic agents.
If you use `compatible_models`, set `LLM_DO_MODEL` to a compatible value. For Python `AgentSpec`, call
`select_model(...)` yourself if you want compatibility validation.

Workers do not inherit models from callers. Entry functions always use
NullModel (no LLM calls allowed); configure models on workers.

## Input Overrides

The manifest can provide default input via `entry.args`. CLI input (prompt or
`--input-json`) overrides it when `allow_cli_input` is true.

If `allow_cli_input` is false and a prompt is provided, the CLI exits with an error.

Attachment paths in worker inputs are resolved relative to the manifest directory (the project root)
unless they are absolute paths.

## Approvals

Approvals are configured in the manifest via `runtime.approval_mode`:
- `prompt` (interactive approvals in TUI)
- `approve_all`
- `reject_all`

Approvals apply only to LLM-invoked actions; user-invoked top-level entries are not gated.

Agent tool approvals are controlled separately:
- `runtime.agent_calls_require_approval` (default: false) prompts on every agent tool call.
- `runtime.agent_attachments_require_approval` (default: false) prompts only when an agent tool call includes attachments.
- `runtime.agent_approval_overrides` can override those settings per agent name.

Example:
```json
{
  "runtime": {
    "agent_approval_overrides": {
      "summarizer": {"calls_require_approval": true},
      "analyzer": {"attachments_require_approval": true}
    }
  }
}
```

In headless mode, `prompt` will fail when a tool requires approval (unless you set `return_permission_errors` in the manifest to return errors instead).

## OAuth

OAuth usage is controlled by `runtime.auth_mode`:
- `oauth_off` (default): never use OAuth credentials.
- `oauth_auto`: use OAuth when valid credentials exist, otherwise fall back.
- `oauth_required`: require OAuth for supported providers and fail if not logged in.

Use `llm-do-oauth login --provider anthropic` to store credentials before running with OAuth enabled.

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
- Streaming is enabled only when event callbacks are active and verbosity is `>= 2`.
- With `-v`, runs stay on the non-stream execution path and emit coarse-grained events from final messages.
- Models without `request_stream()` support can run at `-v`; at `-vv` they fail when the model is asked to stream.

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
