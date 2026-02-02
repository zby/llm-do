# Calculator Example

Demonstrates custom Python tools with a simple calculator agent.

## Running

```bash
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"
llm-do examples/calculator "What is factorial of 10?"
```

```bash
llm-do examples/calculator "Calculate fibonacci(15) and add it to 100"
```

## What It Does

A calculator assistant that uses Python tools for mathematical operations instead of computing in its head. This ensures accurate results for complex calculations.

## Available Tools

- `factorial(n)` - Calculate n!
- `fibonacci(n)` - Calculate the nth Fibonacci number
- `add(a, b)` - Add two numbers
- `multiply(a, b)` - Multiply two numbers

## Project Structure

```
calculator/
├── main.agent      # Calculator agent
├── tools.py        # Python tool definitions
└── project.json    # Manifest
```

## Key Concepts

- **Custom toolsets**: Define tools in Python via the `TOOLSETS` registry
- **Tool delegation**: Agent uses tools for calculations rather than guessing
- **Deterministic operations**: Math operations are reliable Python code
