# Greeter Example

A simple example demonstrating basic worker usage with `llm-do`.

## Setup

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Or use a different model provider:

```bash
# For OpenAI
export OPENAI_API_KEY="sk-..."

# For Google Gemini
export GOOGLE_API_KEY="..."
```

## Usage

### Basic greeting (simple interface)

```bash
cd examples
llm-do greeter "Tell me a joke" \
  --model anthropic:claude-sonnet-4-20250514
```

The CLI automatically:
- Discovers workers from the `workers/` subdirectory
- Pretty-prints output by default
- Accepts plain text messages

**Note:** The `--model` flag is required since this worker doesn't specify a model in its definition.

### Using different models

```bash
cd examples

# Override with a different Claude model
llm-do greeter "What's the weather?" \
  --model anthropic:claude-3-5-sonnet-20241022

# Use OpenAI instead
llm-do greeter "Hello!" \
  --model openai:gpt-4o

# Use Google Gemini
llm-do greeter "Hello!" \
  --model google-gla:gemini-1.5-pro
```

**Common Anthropic models:**
- `claude-sonnet-4-20250514` (recommended, latest)
- `claude-opus-4-20250514` (most capable)
- `claude-3-5-sonnet-20241022` (previous generation)
- `claude-3-5-haiku-20241022` (fast, affordable)

### Advanced: JSON input

For structured input, use `--input` instead of a plain message:

```bash
cd examples
llm-do greeter \
  --input '{"message": "Hello!", "context": "formal"}' \
  --model anthropic:claude-sonnet-4-20250514
```

## Worker Definition

The worker is defined in `workers/greeter.yaml`:

- **name**: greeter
- **model**: None (must be specified via `--model` flag)
- **instructions**: Simple, friendly conversational style
- **no sandboxes**: This worker doesn't need file access
- **no approval rules**: Safe for all operations (no file writes, no delegations)

Workers can optionally specify a model in their YAML definition. This example
leaves it unspecified to demonstrate the `--model` flag.

## Output

The CLI returns JSON with the worker result:

```json
{
  "output": "Hello! How can I help you today?"
}
```

Use `--pretty` for formatted output.

## Next Steps

- Try creating a worker with sandboxed file access
- Explore approval rules for controlling tool usage
- See `examples/pitchdeck_eval/` for a more complex multi-worker example
