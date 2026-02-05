# Custom Provider Example

This example shows how to register a custom provider and use it via `LLM_DO_MODEL`.

## Files

- `providers.py` registers a model factory for the provider prefix `ollama-local`.
- `providers.py` also registers a `http-json` provider that calls an OpenAI-compatible endpoint with raw HTTP.
- `main.agent` is a minimal agent with no model specified.
- `project.json` loads both the agent and provider registration code.
- `GUIDE.md` is a detailed guide for building custom providers without SDKs.

## Run

Start your OpenAI-compatible server (e.g., Ollama), then run:

```bash
export LLM_DO_MODEL="ollama-local:smollm2:135m-instruct-q2_K"
llm-do examples/custom_provider/project.json "Hello!"
```

The base URL is intentionally hard-coded in `providers.py` for simplicity.

To try the raw HTTP provider, point it at a compatible endpoint:

```bash
export LLM_DO_MODEL="http-json:your-model"
llm-do examples/custom_provider/project.json "Hello!"
```
