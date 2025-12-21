"""OAuth helpers for llm-do."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import logging

from .anthropic import login_anthropic, refresh_anthropic_token
from .storage import (
    OAuthCredentials,
    OAuthProvider,
    OAuthStorageBackend,
    get_oauth_path,
    has_oauth_credentials,
    list_oauth_providers,
    load_oauth_credentials,
    load_oauth_storage,
    remove_oauth_credentials,
    reset_oauth_storage,
    save_oauth_credentials,
    set_oauth_storage,
)

logger = logging.getLogger(__name__)

ANTHROPIC_OAUTH_BETA = "oauth-2025-04-20"
ANTHROPIC_OAUTH_BETA_FEATURES = ("fine-grained-tool-streaming-2025-05-14",)
ANTHROPIC_OAUTH_ACCEPT = "application/json"
ANTHROPIC_OAUTH_DANGEROUS_HEADER = "anthropic-dangerous-direct-browser-access"
ANTHROPIC_OAUTH_SYSTEM_PROMPT = "You are Claude Code, Anthropic's official CLI for Claude."


@dataclass(frozen=True)
class OAuthModelOverrides:
    model: Any
    model_settings: Optional[Dict[str, Any]]
    system_prompt: Optional[str]


def _split_model_identifier(model: str) -> Tuple[Optional[str], str]:
    if ":" not in model:
        return None, model
    provider, name = model.split(":", 1)
    return provider, name


async def refresh_token(provider: OAuthProvider) -> str:
    """Refresh OAuth token for a provider and return the new access token."""
    credentials = load_oauth_credentials(provider)
    if not credentials:
        raise RuntimeError(f"No OAuth credentials found for {provider}")

    if provider == "anthropic":
        new_credentials = await refresh_anthropic_token(credentials.refresh)
    else:
        raise RuntimeError(f"Unknown OAuth provider: {provider}")

    save_oauth_credentials(provider, new_credentials)
    return new_credentials.access


async def get_oauth_api_key(provider: OAuthProvider) -> Optional[str]:
    """Return an API token for a provider, refreshing if expired."""
    credentials = load_oauth_credentials(provider)
    if not credentials:
        return None

    if credentials.is_expired():
        try:
            return await refresh_token(provider)
        except Exception as exc:
            logger.warning("Failed to refresh OAuth token for %s: %s", provider, exc)
            remove_oauth_credentials(provider)
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


async def resolve_oauth_overrides(model: Any) -> Optional[OAuthModelOverrides]:
    """Return OAuth model overrides if the model should use OAuth."""
    if not isinstance(model, str):
        return None

    provider, model_name = _split_model_identifier(model)
    oauth_provider = get_oauth_provider_for_model_provider(provider or "")
    if oauth_provider != "anthropic":
        return None

    token = await get_oauth_api_key("anthropic")
    if not token:
        return None

    oauth_model = _build_anthropic_oauth_model(model_name, token)
    beta_flags = ",".join((ANTHROPIC_OAUTH_BETA, *ANTHROPIC_OAUTH_BETA_FEATURES))
    model_settings = {
        "extra_headers": {
            "accept": ANTHROPIC_OAUTH_ACCEPT,
            "anthropic-beta": beta_flags,
            ANTHROPIC_OAUTH_DANGEROUS_HEADER: "true",
        }
    }
    return OAuthModelOverrides(
        model=oauth_model,
        model_settings=model_settings,
        system_prompt=ANTHROPIC_OAUTH_SYSTEM_PROMPT,
    )


__all__ = [
    "ANTHROPIC_OAUTH_ACCEPT",
    "ANTHROPIC_OAUTH_BETA",
    "ANTHROPIC_OAUTH_BETA_FEATURES",
    "ANTHROPIC_OAUTH_DANGEROUS_HEADER",
    "ANTHROPIC_OAUTH_SYSTEM_PROMPT",
    "OAuthCredentials",
    "OAuthProvider",
    "OAuthStorageBackend",
    "get_oauth_path",
    "has_oauth_credentials",
    "list_oauth_providers",
    "load_oauth_credentials",
    "load_oauth_storage",
    "remove_oauth_credentials",
    "reset_oauth_storage",
    "save_oauth_credentials",
    "set_oauth_storage",
    "login_anthropic",
    "refresh_anthropic_token",
    "refresh_token",
    "get_oauth_api_key",
    "get_oauth_provider_for_model_provider",
    "resolve_oauth_overrides",
]
