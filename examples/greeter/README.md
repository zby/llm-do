# Greeter Example

A minimal conversational worker demonstrating basic `llm-do` usage. No tools, no file access—just a friendly chat worker.

## Setup

```bash
# Set your API key (choose one)
export ANTHROPIC_API_KEY="sk-ant-..."
# or
export OPENAI_API_KEY="sk-..."

# Set a default model
export MODEL=anthropic:claude-3-5-haiku-20241022  # or openai:gpt-4o-mini
```

## Usage

```bash
cd examples/greeter

# Run main.worker (default)
llm-do "Tell me a joke" --model $MODEL

# Or run a specific worker
llm-do --worker greeter "Tell me a joke" --model $MODEL
```

The CLI automatically:
- Runs `main.worker` by default (or use `--worker` for others)
- Accepts plain text messages
- Returns the worker's response

## Worker Definition

See `greeter.worker`:

```yaml
name: greeter
description: A friendly assistant that greets users and responds to messages
instructions: |
  You are a friendly and helpful assistant.

  When the user provides a message:
  1. Greet them warmly
  2. Respond thoughtfully to their message
  3. Be concise but friendly

  Keep your responses brief and conversational.
```

**Key points:**
- No `model` specified → must use `--model` flag
- No filesystem toolset → no file access
- No approval rules → safe for all operations (no tools available)
- Inline instructions → no separate prompt file needed

## Next Steps

- See `examples/pitchdeck_eval/` for a multi-worker example with file access and delegation
- Try creating your own worker with file access and tools
