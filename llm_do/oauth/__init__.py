"""OAuth helpers for llm-do."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from pydantic_ai.settings import ModelSettings

from .anthropic import login_anthropic, refresh_anthropic_token
from .storage import (
    OAuthCredentials,
    OAuthProvider,
    OAuthStorage,
    OAuthStorageBackend,
    get_oauth_path,
)

logger = logging.getLogger(__name__)

ANTHROPIC_OAUTH_BETA = "oauth-2025-04-20"
ANTHROPIC_OAUTH_BETA_FEATURES = ("fine-grained-tool-streaming-2025-05-14",)
ANTHROPIC_OAUTH_ACCEPT = "application/json"
ANTHROPIC_OAUTH_DANGEROUS_HEADER = "anthropic-dangerous-direct-browser-access"


@dataclass(frozen=True)
class OAuthModelOverrides:
    model: Any
    model_settings: ModelSettings | None


def _split_model_identifier(model: str) -> Tuple[Optional[str], str]:
    if ":" not in model:
        return None, model
    provider, name = model.split(":", 1)
    return provider, name


def _ensure_storage(storage: Optional[OAuthStorage]) -> OAuthStorage:
    return storage or OAuthStorage()


async def refresh_token(provider: OAuthProvider, storage: Optional[OAuthStorage] = None) -> str:
    """Refresh OAuth token for a provider and return the new access token."""
    oauth_storage = _ensure_storage(storage)
    credentials = oauth_storage.load_credentials(provider)
    if not credentials:
        raise RuntimeError(f"No OAuth credentials found for {provider}")

    if provider == "anthropic":
        new_credentials = await refresh_anthropic_token(credentials.refresh)
    else:
        raise RuntimeError(f"Unknown OAuth provider: {provider}")

    oauth_storage.save_credentials(provider, new_credentials)
    return new_credentials.access


async def get_oauth_api_key(provider: OAuthProvider, storage: Optional[OAuthStorage] = None) -> Optional[str]:
    """Return an API token for a provider, refreshing if expired."""
    oauth_storage = _ensure_storage(storage)
    credentials = oauth_storage.load_credentials(provider)
    if not credentials:
        return None

    if credentials.is_expired():
        try:
            await refresh_token(provider, storage=oauth_storage)
            # Reload credentials after refresh
            credentials = oauth_storage.load_credentials(provider)
            if not credentials:
                return None
        except Exception as exc:
            logger.warning("Failed to refresh OAuth token for %s: %s", provider, exc)
            oauth_storage.remove_credentials(provider)
            return None

    return credentials.access


def get_oauth_provider_for_model_provider(model_provider: str) -> Optional[OAuthProvider]:
    """Return OAuth provider name for a model provider."""
    if model_provider == "anthropic":
        return "anthropic"
    return None


def _build_anthropic_oauth_model(model_name: str, token: str) -> Any:
    from anthropic import AsyncAnthropic
    from pydantic_ai.models import cached_async_http_client
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    http_client = cached_async_http_client(provider="anthropic")
    client = AsyncAnthropic(auth_token=token, http_client=http_client)
    provider = AnthropicProvider(anthropic_client=client)
    return AnthropicModel(model_name=model_name, provider=provider)


async def resolve_oauth_overrides(
    model: Any,
    storage: Optional[OAuthStorage] = None,
) -> Optional[OAuthModelOverrides]:
    """Return OAuth model overrides if the model should use OAuth."""
    if not isinstance(model, str):
        return None

    provider, model_name = _split_model_identifier(model)
    oauth_provider = get_oauth_provider_for_model_provider(provider or "")
    if oauth_provider != "anthropic":
        return None

    token = await get_oauth_api_key("anthropic", storage=storage)
    if not token:
        return None

    oauth_model = _build_anthropic_oauth_model(model_name, token)
    beta_flags = ",".join((ANTHROPIC_OAUTH_BETA, *ANTHROPIC_OAUTH_BETA_FEATURES))
    model_settings: ModelSettings = {
        "extra_headers": {
            "accept": ANTHROPIC_OAUTH_ACCEPT,
            "anthropic-beta": beta_flags,
            ANTHROPIC_OAUTH_DANGEROUS_HEADER: "true",
        }
    }
    return OAuthModelOverrides(
        model=oauth_model,
        model_settings=model_settings,
    )


__all__ = [
    "ANTHROPIC_OAUTH_ACCEPT",
    "ANTHROPIC_OAUTH_BETA",
    "ANTHROPIC_OAUTH_BETA_FEATURES",
    "ANTHROPIC_OAUTH_DANGEROUS_HEADER",
    "OAuthCredentials",
    "OAuthProvider",
    "OAuthStorage",
    "OAuthStorageBackend",
    "get_oauth_api_key",
    "get_oauth_path",
    "get_oauth_provider_for_model_provider",
    "login_anthropic",
    "refresh_anthropic_token",
    "refresh_token",
    "resolve_oauth_overrides",
]
