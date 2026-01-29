from __future__ import annotations

import httpx
from openai import AsyncOpenAI
from pydantic_ai.models import cached_async_http_client
from pydantic_ai.providers import Provider


class OpenAICompatibleProvider(Provider[AsyncOpenAI]):
    """Provider for OpenAI-compatible APIs (e.g., Ollama)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "unused",
        name: str = "openai-compatible",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._name = name

        http_client = http_client or cached_async_http_client(provider=self._name)

        self._client = AsyncOpenAI(
            api_key=api_key,  # required by SDK, ignored by Ollama
            base_url=self._base_url,
            http_client=http_client,
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def client(self) -> AsyncOpenAI:
        return self._client
