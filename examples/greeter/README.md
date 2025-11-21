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
llm-do examples/greeter.yaml "Tell me a joke"
```

The CLI automatically:
- Infers the registry from the worker file path
- Pretty-prints output by default
- Accepts plain text messages

### With different models

```bash
# Override with a different Claude model
llm-do examples/greeter.yaml "What's the weather?" \
  --model anthropic:claude-3-5-sonnet-20241022

# Use OpenAI instead
llm-do examples/greeter.yaml "Hello!" \
  --model openai:gpt-4o

# Use Google Gemini
llm-do examples/greeter.yaml "Hello!" \
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
llm-do examples/greeter.yaml \
  --input '{"message": "Hello!", "context": "formal"}'
```

## Worker Definition

The worker is defined in `../greeter.yaml`:

- **name**: greeter
- **model**: anthropic:claude-sonnet-4-20250514 (configurable via `--model` flag)
- **instructions**: Simple, friendly conversational style
- **no sandboxes**: This worker doesn't need file access
- **no approval rules**: Safe for all operations (no file writes, no delegations)

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
