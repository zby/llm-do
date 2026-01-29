# Entry Logging Example

Demonstrates using an entry function to intercept and log user messages before forwarding to an agent.

## Running

```bash
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"
llm-do examples/entry_logging "Hello, my name is Alice"
```

## What It Does

The entry function receives the user input, logs it to `messages.log` with a timestamp, then forwards the input to the greeter agent.

## Project Structure

```
entry_logging/
├── entry.py        # Entry function that logs messages
├── main.agent      # Greeter agent
└── project.json    # Manifest with entry.function
```

## Key Concepts

- **Entry function**: Uses `entry.function` in manifest instead of `entry.agent`
- **Input handling**: Entry receives `input_data` and `runtime` parameters
- **Agent invocation**: Uses `runtime.call_agent("main", input_data)` to forward to agents
- **Pre-processing**: Entry functions can inspect/modify input before agent execution
