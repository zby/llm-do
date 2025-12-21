"""Anthropic OAuth flows."""
from __future__ import annotations

from typing import Awaitable, Callable
from urllib.parse import urlencode
import base64
import time

import httpx

from .pkce import generate_pkce
from .storage import OAuthCredentials, save_oauth_credentials


def _decode(value: str) -> str:
    return base64.b64decode(value).decode("ascii")


CLIENT_ID = _decode("OWQxYzI1MGEtZTYxYi00NGQ5LTg4ZWQtNTk0NGQxOTYyZjVl")
AUTHORIZE_URL = "https://claude.ai/oauth/authorize"
TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"
REDIRECT_URI = "https://console.anthropic.com/oauth/code/callback"
SCOPES = "org:create_api_key user:profile user:inference"


async def login_anthropic(
    on_auth_url: Callable[[str], None],
    on_prompt_code: Callable[[], Awaitable[str]],
) -> OAuthCredentials:
    """Login with Anthropic OAuth (authorization code + PKCE)."""
    verifier, challenge = generate_pkce()

    params = {
        "code": "true",
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": verifier,
    }

    auth_url = f"{AUTHORIZE_URL}?{urlencode(params)}"
    on_auth_url(auth_url)

    auth_code = await on_prompt_code()
    code, sep, state = auth_code.partition("#")
    if not sep:
        state = ""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            headers={"Content-Type": "application/json"},
            json={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "code": code,
                "state": state,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": verifier,
            },
        )

    if not response.is_success:
        raise RuntimeError(f"Token exchange failed: {response.text}")

    data = response.json()
    expires_at = int(time.time() * 1000) + data["expires_in"] * 1000

    credentials = OAuthCredentials(
        type="oauth",
        refresh=data["refresh_token"],
        access=data["access_token"],
        expires=expires_at,
    )

    save_oauth_credentials("anthropic", credentials)
    return credentials


async def refresh_anthropic_token(refresh_token: str) -> OAuthCredentials:
    """Refresh Anthropic OAuth token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            headers={"Content-Type": "application/json"},
            json={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "refresh_token": refresh_token,
            },
        )

    if not response.is_success:
        raise RuntimeError(f"Anthropic token refresh failed: {response.text}")

    data = response.json()
    expires_at = int(time.time() * 1000) + data["expires_in"] * 1000

    return OAuthCredentials(
        type="oauth",
        refresh=data["refresh_token"],
        access=data["access_token"],
        expires=expires_at,
    )
