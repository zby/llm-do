# Calculator Worker Example

This example demonstrates how to create workers with **custom tools** in llm-do.

## What This Shows

- **Custom tools**: Python functions in `tools.py` are automatically registered
- **Tool approval rules**: Custom tools follow the same approval flow as built-in tools

## Structure

```
calculator/
├── main.worker    # Worker configuration
├── tools.py       # Custom calculation tools
└── scratch/       # Working directory
```

## Custom Tools

The calculator worker has three custom tools defined in `tools.py`:

1. `calculate_fibonacci(n)` - Calculate Fibonacci numbers
2. `calculate_factorial(n)` - Calculate factorials
3. `calculate_prime_factors(n)` - Find prime factors

These tools are automatically discovered and registered when the worker loads.

## Usage

From the `examples/calculator` directory:

```bash
# Run with approve-all mode (non-interactive)
llm-do "What is the 20th Fibonacci number?" --model anthropic:claude-haiku-4-5 --approve-all

# Complex query using multiple tools
llm-do "Find the prime factors of 1001 and calculate factorial of 7" --model anthropic:claude-haiku-4-5 --approve-all
```

## How Custom Tools Work

1. **Discovery**: llm-do looks for `tools.py` alongside `.worker` files
2. **Registration**: All public functions (not starting with `_`) are registered as [PydanticAI tools](https://ai.pydantic.dev/api/tools/)
3. **Approval**: Tool rules in `main.worker` control whether approval is required
4. **Documentation**: Function docstrings become tool descriptions for the LLM

## Key Features

- **Type hints**: Functions use type annotations for validation
- **Docstrings**: Clear descriptions help the LLM understand when to use each tool
- **Error handling**: Input validation with helpful error messages
- **Private functions**: Functions starting with `_` are not exposed as tools

## Testing

You can test the custom tools are loaded correctly:

```bash
# This should work and show tool usage
llm-do "What is fibonacci(15)?" --model anthropic:claude-haiku-4-5 --approve-all
```

The worker will use the custom `calculate_fibonacci` tool to answer the question.
