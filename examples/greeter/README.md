# Greeter Example

Minimal example demonstrating the basic llm-do project structure.

## Running

```bash
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"
llm-do examples/greeter "Hello, my name is Alice"
```

## What It Does

A simple agent that responds with a friendly, personalized greeting. This is the "hello world" of llm-do projects.

## Project Structure

```
greeter/
├── main.agent      # Single entry agent
└── project.json    # Manifest
```

## Key Concepts

- **Minimal setup**: Just one agent file and a manifest
- **Entry agent**: Selected in `project.json` via `entry.agent`
- **No tools**: Pure LLM conversation without tool calls
