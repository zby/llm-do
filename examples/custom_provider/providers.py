import json

import httpx
from pydantic_ai.exceptions import UserError
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import (
    Model,
    ModelMessage,
    ModelRequestParameters,
    ModelSettings,
)
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.tools import ToolDefinition

from llm_do import register_model_factory
from llm_do.providers import OpenAICompatibleProvider


class LocalOllamaProvider(OpenAICompatibleProvider):
    def __init__(self) -> None:
        super().__init__(
            base_url="http://127.0.0.1:11434/v1",
            name="ollama-local",
        )


def build_ollama_model(model_name: str) -> OpenAIChatModel:
    return OpenAIChatModel(model_name, provider=LocalOllamaProvider())


register_model_factory("ollama-local", build_ollama_model)


class SimpleHTTPProvider:
    """Minimal provider that uses plain HTTP requests (no SDKs)."""

    def __init__(self, *, base_url: str, api_key: str | None = None, name: str = "http-json") -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._name = name
        self._client = httpx.AsyncClient(timeout=30.0)

    @property
    def name(self) -> str:
        return self._name

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def api_key(self) -> str | None:
        return self._api_key

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client


class SimpleHTTPChatModel(Model):
    """Simple OpenAI-compatible chat model implemented with raw HTTP calls."""

    def __init__(self, model_name: str, *, provider: SimpleHTTPProvider) -> None:
        super().__init__()
        self._model_name = model_name
        self._provider = provider

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def system(self) -> str:
        return "openai"

    @property
    def base_url(self) -> str | None:
        return self._provider.base_url

    def _map_tool_definition(self, tool: ToolDefinition) -> dict:
        """Convert a PydanticAI ToolDefinition to OpenAI function tool format."""
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.parameters_json_schema,
            },
        }

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        model_settings, model_request_parameters = self.prepare_request(model_settings, model_request_parameters)

        if not model_request_parameters.allow_text_output or model_request_parameters.output_mode != "text":
            raise UserError("SimpleHTTPChatModel only supports plain text output.")

        payload_messages: list[dict] = []
        instructions = self._get_instructions(messages, model_request_parameters)
        if instructions:
            payload_messages.append({"role": "system", "content": instructions})

        for message in messages:
            if isinstance(message, ModelRequest):
                for part in message.parts:
                    if isinstance(part, SystemPromptPart):
                        payload_messages.append({"role": "system", "content": part.content})
                    elif isinstance(part, UserPromptPart):
                        if not isinstance(part.content, str):
                            raise UserError("SimpleHTTPChatModel only supports string user prompts.")
                        payload_messages.append({"role": "user", "content": part.content})
                    elif isinstance(part, ToolReturnPart):
                        payload_messages.append({
                            "role": "tool",
                            "tool_call_id": part.tool_call_id or "",
                            "content": part.model_response_str(),
                        })
                    elif isinstance(part, RetryPromptPart) and part.tool_name:
                        payload_messages.append({
                            "role": "tool",
                            "tool_call_id": part.tool_call_id or "",
                            "content": part.model_response_str(),
                        })
            elif isinstance(message, ModelResponse):
                tool_calls = [
                    {
                        "id": p.tool_call_id,
                        "type": "function",
                        "function": {
                            "name": p.tool_name,
                            "arguments": p.args if isinstance(p.args, str) else json.dumps(p.args),
                        },
                    }
                    for p in message.parts
                    if isinstance(p, ToolCallPart)
                ]
                if tool_calls:
                    text_content = message.text or None
                    payload_messages.append({
                        "role": "assistant",
                        "content": text_content,
                        "tool_calls": tool_calls,
                    })
                elif message.text:
                    payload_messages.append({"role": "assistant", "content": message.text})

        payload: dict[str, object] = {
            "model": self.model_name,
            "messages": payload_messages,
        }

        all_tools = model_request_parameters.function_tools + model_request_parameters.output_tools
        if all_tools:
            payload["tools"] = [self._map_tool_definition(t) for t in all_tools]

        # Standard OpenAI parameters
        standard_keys = ("temperature", "max_tokens", "top_p", "presence_penalty", "frequency_penalty")
        for key in standard_keys:
            if model_settings and key in model_settings:
                payload[key] = model_settings[key]

        # Pass through custom parameters (e.g., stop, seed, or provider-specific like num_ctx)
        if model_settings:
            internal_keys = {"timeout", "parallel_tool_calls", "extra_headers", *standard_keys}
            for key, value in model_settings.items():
                if key not in internal_keys and value is not None:
                    payload[key] = value

        headers = {"Content-Type": "application/json"}
        if self._provider.api_key:
            headers["Authorization"] = f"Bearer {self._provider.api_key}"

        response = await self._provider.client.post(
            f"{self._provider.base_url}/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        msg = data.get("choices", [{}])[0].get("message", {})
        parts: list[TextPart | ToolCallPart] = []

        if content := msg.get("content"):
            parts.append(TextPart(content=content))

        for tc in msg.get("tool_calls", []):
            if tc.get("type") == "function":
                parts.append(
                    ToolCallPart(
                        tool_name=tc["function"]["name"],
                        args=tc["function"]["arguments"],
                        tool_call_id=tc["id"],
                    )
                )

        if not parts:
            parts.append(TextPart(content=""))

        return ModelResponse(
            parts=parts,
            model_name=self.model_name,
            provider_name=self._provider.name,
            provider_details={"raw_response": data},
        )


def build_http_json_model(model_name: str) -> SimpleHTTPChatModel:
    return SimpleHTTPChatModel(
        model_name,
        provider=SimpleHTTPProvider(
            base_url="http://127.0.0.1:8000/v1",
            api_key=None,
        ),
    )


register_model_factory("http-json", build_http_json_model)
