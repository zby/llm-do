# Custom Provider Example

This example shows how to register a custom provider and use it via `LLM_DO_MODEL`.

## Files

- `providers.py` registers a model factory for the provider prefix `ollama-local`.
- `main.agent` is a minimal agent with no model specified.
- `project.json` loads both the agent and provider registration code.

## Run

Start your OpenAI-compatible server (e.g., Ollama), then run:

```bash
export LLM_DO_MODEL="ollama-local:smollm2:135m-instruct-q2_K"
llm-do examples/custom_provider/project.json "Hello!"
```

The base URL is intentionally hard-coded in `providers.py` for simplicity.
