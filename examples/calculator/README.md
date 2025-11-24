# Calculator Worker Example

This example demonstrates how to create workers with **custom tools** in llm-do.

## What This Shows

- **Directory-based worker structure**: Workers can be organized in directories
- **Custom tools**: Python functions in `tools.py` are automatically registered
- **Tool approval rules**: Custom tools follow the same approval flow as built-in tools

## Structure

```
calculator/
├── workers/
│   └── calculator/
│       ├── worker.yaml    # Worker configuration
│       └── tools.py       # Custom calculation tools
└── scratch/               # Working directory for the worker
```

## Custom Tools

The calculator worker has three custom tools defined in `tools.py`:

1. `calculate_fibonacci(n)` - Calculate Fibonacci numbers
2. `calculate_factorial(n)` - Calculate factorials
3. `calculate_prime_factors(n)` - Find prime factors

These tools are automatically discovered and registered when the worker loads.

## Usage

```bash
# Run with approve-all mode (non-interactive)
llm-do calculator "What is the 20th Fibonacci number?" --approve-all

# Run with explicit model
llm-do calculator "Calculate 12 factorial" --model anthropic:claude-haiku-4-5 --approve-all

# Complex query using multiple tools
llm-do calculator "Find the prime factors of 1001 and calculate factorial of 7" --approve-all
```

## How Custom Tools Work

1. **Discovery**: llm-do looks for `workers/calculator/tools.py` alongside `worker.yaml`
2. **Registration**: All public functions (not starting with `_`) are registered as tools
3. **Approval**: Tool rules in `worker.yaml` control whether approval is required
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
llm-do calculator "What is fibonacci(15)?" --approve-all
```

The worker will use the custom `calculate_fibonacci` tool to answer the question.
