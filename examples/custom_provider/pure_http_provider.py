"""Pure HTTP-based provider that calls Ollama's REST API directly.

This demonstrates building a custom model WITHOUT any LLM SDK dependencies -
just using httpx for HTTP requests. Use this pattern when:
- You need to integrate with an API that has no PydanticAI provider
- You want full control over the HTTP layer
- You're building against a custom/internal LLM API
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RequestUsage

from llm_do import register_model_factory


class OllamaHttpModel(Model):
    """Model that calls Ollama's REST API directly via httpx.

    This is a minimal implementation showing the core pattern.
    A production version would add streaming, tool calls, etc.
    """

    def __init__(
        self,
        model_name: str,
        *,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 120.0,
    ) -> None:
        self._model_name = model_name
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def system(self) -> str:
        return "ollama-http"

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Make a chat completion request to Ollama's REST API."""
        # Convert PydanticAI messages to Ollama format
        ollama_messages = self._convert_messages(messages)

        # Build request payload
        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": ollama_messages,
            "stream": False,
        }

        # Add any options from model_settings
        if model_settings:
            options: dict[str, Any] = {}
            if model_settings.temperature is not None:
                options["temperature"] = model_settings.temperature
            if model_settings.max_tokens is not None:
                options["num_predict"] = model_settings.max_tokens
            if model_settings.top_p is not None:
                options["top_p"] = model_settings.top_p
            if options:
                payload["options"] = options

        # Make the HTTP request
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        # Parse response
        content = data.get("message", {}).get("content", "")

        # Extract usage if available
        usage = RequestUsage()
        if "prompt_eval_count" in data:
            usage = RequestUsage(
                request_tokens=data.get("prompt_eval_count", 0),
                response_tokens=data.get("eval_count", 0),
            )

        return ModelResponse(
            parts=[TextPart(content=content)],
            usage=usage,
            model_name=self._model_name,
        )

    def _convert_messages(self, messages: list[ModelMessage]) -> list[dict[str, str]]:
        """Convert PydanticAI messages to Ollama's message format."""
        result: list[dict[str, str]] = []

        for msg in messages:
            if isinstance(msg, ModelRequest):
                for part in msg.parts:
                    if isinstance(part, SystemPromptPart):
                        result.append({"role": "system", "content": part.content})
                    elif isinstance(part, UserPromptPart):
                        # Handle string content (common case)
                        if isinstance(part.content, str):
                            result.append({"role": "user", "content": part.content})
                        else:
                            # For multi-part content, extract text
                            text_parts = [
                                p.content for p in part.content if hasattr(p, "content")
                            ]
                            result.append({"role": "user", "content": " ".join(text_parts)})
            elif isinstance(msg, ModelResponse):
                # Include previous assistant responses for context
                if msg.text:
                    result.append({"role": "assistant", "content": msg.text})

        return result


def build_ollama_http_model(model_name: str) -> OllamaHttpModel:
    """Factory function for the pure HTTP Ollama model."""
    return OllamaHttpModel(model_name)


# Register under a distinct prefix
register_model_factory("ollama-http", build_ollama_http_model)
