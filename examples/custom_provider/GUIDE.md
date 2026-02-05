# Custom Provider Guide (No SDK)

This guide explains what the `http-json` example provider implements and what you need to build when wiring a custom provider that **does not rely on any LLM SDKs**. The goal is to show how to connect `llm-do` + PydanticAI to a plain HTTP endpoint (OpenAI-compatible or similar) using only common HTTP libraries.

## What This Example Implements

The example in `providers.py` adds **two** providers:

1. **`ollama-local`** (SDK-backed) using `OpenAIChatModel`.
2. **`http-json`** (SDK-free) using a custom `SimpleHTTPChatModel` that issues raw HTTP requests with `httpx`.

The SDK-free version demonstrates the minimum surface area you must implement:

- A provider class that stores base URL/auth info.
- A model class that subclasses `pydantic_ai.models.Model` and implements `request()`.
- Mapping between `PydanticAI` message objects and your HTTP provider’s request schema.
- Parsing the provider response back into a `ModelResponse` with text parts.

## Provider Responsibilities

**Provider = configuration + HTTP client.**

The `SimpleHTTPProvider` encapsulates:

- `base_url`: Where HTTP requests are sent (e.g., `http://127.0.0.1:8000/v1`).
- `api_key`: Optional bearer token for auth headers.
- `name`: A stable identifier used in responses (e.g., `http-json`).
- `httpx.AsyncClient`: A reusable async HTTP client.

If you swap in another HTTP client (`urllib`, `requests`, `aiohttp`), the model logic stays the same—only the transport changes.

## Model Responsibilities

A custom model must subclass `pydantic_ai.models.Model` and implement:

- `model_name`: The provider-side model name (e.g., `your-model`).
- `system`: A standardized provider id (the example uses `openai` because the API is OpenAI-compatible).
- `request()`: The real HTTP call with request/response translation.

### Message Mapping

PydanticAI hands you a list of `ModelMessage` objects. In the example, we only support:

- `ModelRequest` with `UserPromptPart` (user input)
- `ModelRequest` with `SystemPromptPart` (system input)
- `ModelResponse` with `TextPart` (assistant history)

If your provider accepts OpenAI-style messages, you need to map these into:

```json
{
  "role": "user" | "system" | "assistant",
  "content": "..."
}
```

The example does the following:

- Uses `Model._get_instructions()` to inject system instructions.
- Converts each `UserPromptPart` into a `user` message.
- Converts each `SystemPromptPart` into a `system` message.
- Converts each prior `ModelResponse` into an `assistant` message (text only).

### Output + Tool Constraints

The SDK-free example intentionally keeps scope minimal:

- **Only text output is supported.** If tool calls or structured output are requested, it raises a `UserError`.
- **No streaming.** Streaming is possible but not shown in this minimal example.
- **No tool calling.** If you want tools, you must translate `function_tools` + tool schemas into your provider’s format.

## Request Construction

The `http-json` example posts to `/chat/completions` with a payload like:

```json
{
  "model": "your-model",
  "messages": [...],
  "temperature": 0.7,
  "max_tokens": 400
}
```

Only a small set of optional settings are passed through:

- `temperature`
- `max_tokens`
- `top_p`
- `presence_penalty`
- `frequency_penalty`

If your endpoint supports different fields, you can map them in the same spot.

## Response Parsing

The model expects an OpenAI-style response structure:

```json
{
  "choices": [
    {"message": {"content": "..."}}
  ]
}
```

It extracts the first `choices[0].message.content` and returns a `ModelResponse` with a single `TextPart`.

If your provider returns a different schema, transform it here and set `parts` accordingly.

## Configuration in `providers.py`

The `register_model_factory` call connects a provider prefix (e.g., `http-json`) to a factory function that builds the model:

```python
register_model_factory("http-json", build_http_json_model)
```

Usage becomes:

```bash
export LLM_DO_MODEL="http-json:your-model"
llm-do examples/custom_provider/project.json "Hello!"
```

If you need environment-driven configuration, update the provider factory to read from env vars before instantiating the provider.

## Extending This Example

When you need more features, consider adding:

- **Tool support:** Map `function_tools` to your provider’s tool schema and parse tool calls back into `ToolCallPart`.
- **Streaming:** Implement `request_stream()` and return `StreamedResponse` objects.
- **Token usage:** Populate `RequestUsage` by parsing `usage` fields from your API responses.
- **Error mapping:** Translate provider-specific error payloads into `UserError` with actionable messages.

## Checklist: Minimal SDK-Free Provider

- [ ] Provider object that stores base URL, API key, name, and HTTP client.
- [ ] Model subclass implementing `request()`.
- [ ] Model message mapping for system/user/assistant history.
- [ ] Response parsing into `ModelResponse` + `TextPart`.
- [ ] `register_model_factory()` with a custom provider prefix.
- [ ] README instructions + example run commands.
