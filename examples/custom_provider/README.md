# Custom Provider Example

This example shows how to register custom providers and use them via `LLM_DO_MODEL`.

## Files

- `providers.py` - Uses `OpenAICompatibleProvider` for OpenAI-compatible APIs (e.g., Ollama)
- `pure_http_provider.py` - Pure HTTP implementation using only httpx (no LLM SDK)
- `main.agent` - A minimal agent with no model specified
- `project.json` - Loads both provider files and the agent

## Option 1: OpenAI-Compatible Provider

Uses PydanticAI's `OpenAICompatibleProvider` with the OpenAI SDK. Best for APIs that follow the OpenAI chat completions format.

```bash
export LLM_DO_MODEL="ollama-local:smollm2:135m-instruct-q2_K"
llm-do examples/custom_provider/project.json "Hello!"
```

## Option 2: Pure HTTP Provider (No SDK)

Uses only httpx to call Ollama's native REST API directly. Use this pattern when:
- Integrating with an API that has no PydanticAI provider
- You want full control over the HTTP layer
- Building against a custom/internal LLM API

```bash
export LLM_DO_MODEL="ollama-http:smollm2:135m-instruct-q2_K"
llm-do examples/custom_provider/project.json "Hello!"
```

## Choosing an Approach

| Approach | Best For | Dependencies |
|----------|----------|--------------|
| `OpenAICompatibleProvider` | OpenAI-compatible APIs | openai SDK |
| Pure HTTP | Any REST API | httpx only |

The pure HTTP approach is more verbose but gives you complete control and works with any HTTP-based LLM API, not just OpenAI-compatible ones.
