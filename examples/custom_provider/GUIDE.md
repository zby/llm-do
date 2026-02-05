# Custom Provider Guide (No SDK)

Connect `llm-do` to any HTTP endpoint without relying on LLM SDKs.

This guide walks through the `http-json` example—a minimal implementation that speaks to OpenAI-compatible APIs using raw HTTP requests.

---

## Overview

The `providers.py` example registers two providers:

| Provider | Approach | Implementation |
|----------|----------|----------------|
| `ollama-local` | SDK-backed | Uses `OpenAIChatModel` from PydanticAI |
| `http-json` | SDK-free | Custom `SimpleHTTPChatModel` with `httpx` |

The SDK-free approach requires you to implement:

1. A **provider** class (configuration + HTTP client)
2. A **model** class (request/response translation)
3. **Message mapping** (PydanticAI ↔ your API format)
4. **Registration** via `register_model_factory()`

---

## The Provider Class

The provider holds connection details and the HTTP client:

```python
class SimpleHTTPProvider:
    base_url: str      # e.g., "http://127.0.0.1:8000/v1"
    api_key: str       # Optional bearer token
    name: str          # Provider identifier (e.g., "http-json")
    client: httpx.AsyncClient
```

Swap `httpx` for `aiohttp`, `requests`, or `urllib`—the model logic stays the same.

---

## The Model Class

Subclass `pydantic_ai.models.Model` and implement these:

| Attribute/Method | Purpose |
|------------------|---------|
| `model_name` | The model identifier sent to the API |
| `system` | Provider ID (use `"openai"` for OpenAI-compatible APIs) |
| `request()` | Sends the HTTP request and parses the response |

---

## Message Mapping

PydanticAI provides `ModelMessage` objects. Convert them to your API's format:

**Supported in this example:**

| PydanticAI Type | Maps To |
|-----------------|---------|
| `ModelRequest` + `UserPromptPart` | `{"role": "user", "content": "..."}` |
| `ModelRequest` + `SystemPromptPart` | `{"role": "system", "content": "..."}` |
| `ModelResponse` + `TextPart` | `{"role": "assistant", "content": "..."}` |

The example also calls `Model._get_instructions()` to inject system instructions.

---

## Request Format

The example posts to `/chat/completions`:

```json
{
  "model": "your-model",
  "messages": [...],
  "temperature": 0.7,
  "max_tokens": 400
}
```

**Supported settings:** `temperature`, `max_tokens`, `top_p`, `presence_penalty`, `frequency_penalty`

### Custom Parameters

The example passes through any additional keys from `model_settings` to the API payload, allowing provider-specific parameters:

```python
# In your agent or run call
result = await agent.run(
    prompt,
    model_settings={
        "temperature": 0.7,
        "stop": ["\n\n"],           # Standard OpenAI parameter
        "seed": 42,                  # Reproducibility
        "num_ctx": 4096,             # Ollama-specific context size
    },
)
```

Internal keys (`timeout`, `parallel_tool_calls`, `extra_headers`) are filtered out and not sent to the API.

---

## Response Parsing

Expects an OpenAI-style response:

```json
{
  "choices": [
    {"message": {"content": "Hello!"}}
  ]
}
```

Extract `choices[0].message.content` and return a `ModelResponse` with a `TextPart`.

---

## Tool Calling Support

The example supports OpenAI-compatible function calling. Tools are mapped as follows:

### Tool Definition Mapping

| PydanticAI Field | OpenAI Format |
|------------------|---------------|
| `ToolDefinition.name` | `function.name` |
| `ToolDefinition.description` | `function.description` |
| `ToolDefinition.parameters_json_schema` | `function.parameters` |

### Request Message Mapping

| PydanticAI Type | OpenAI Format |
|-----------------|---------------|
| `ToolReturnPart` | `{"role": "tool", "tool_call_id": "...", "content": "..."}` |
| `RetryPromptPart` (with tool_name) | `{"role": "tool", "tool_call_id": "...", "content": "..."}` |
| `ModelResponse` with `ToolCallPart` | Assistant message with `tool_calls` array |

### Response Parsing

Tool calls in the response are parsed into `ToolCallPart` objects:

```python
for tc in msg.get("tool_calls", []):
    if tc.get("type") == "function":
        parts.append(ToolCallPart(
            tool_name=tc["function"]["name"],
            args=tc["function"]["arguments"],
            tool_call_id=tc["id"],
        ))
```

### Example Tool Response

```json
{
  "choices": [{
    "message": {
      "content": null,
      "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "get_weather",
          "arguments": "{\"location\": \"Paris\"}"
        }
      }]
    }
  }]
}
```

---

## Registration

Connect your provider prefix to a factory function:

```python
register_model_factory("http-json", build_http_json_model)
```

Then use it:

```bash
export LLM_DO_MODEL="http-json:your-model"
llm-do examples/custom_provider/project.json "Hello!"
```

---

## Limitations

This minimal example intentionally omits:

| Feature | Status |
|---------|--------|
| Tool calling | Supported |
| Structured output | Not supported |
| Streaming | Not implemented |

---

## Extending the Example

| Feature | How to Add |
|---------|------------|
| **Streaming** | Implement `request_stream()` returning `StreamedResponse` |
| **Token usage** | Parse `usage` fields into `RequestUsage` |
| **Error handling** | Translate API errors into `UserError` with clear messages |

---

## Checklist

Before shipping your custom provider:

1. Provider stores base URL, API key, name, and HTTP client
2. Model subclass implements `request()`
3. Message mapping handles system/user/assistant history
4. Response parsing returns `ModelResponse` + `TextPart`
5. Factory registered with `register_model_factory()`
6. README documents usage and example commands
