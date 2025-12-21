import asyncio
import time

import pytest

from llm_do.oauth import (
    ANTHROPIC_OAUTH_ACCEPT,
    ANTHROPIC_OAUTH_BETA,
    ANTHROPIC_OAUTH_BETA_FEATURES,
    ANTHROPIC_OAUTH_DANGEROUS_HEADER,
    ANTHROPIC_OAUTH_SYSTEM_PROMPT,
    resolve_oauth_overrides,
)
from llm_do.oauth import anthropic as oauth_anthropic
from llm_do.oauth.storage import (
    OAuthCredentials,
    load_oauth_credentials,
    reset_oauth_storage,
    save_oauth_credentials,
    set_oauth_storage,
)


class InMemoryStorage:
    def __init__(self) -> None:
        self._storage = {}

    def load(self):
        return dict(self._storage)

    def save(self, storage):
        self._storage = dict(storage)


@pytest.fixture
def memory_storage():
    storage = InMemoryStorage()
    set_oauth_storage(storage)
    yield storage
    reset_oauth_storage()


class FakeResponse:
    def __init__(self, status_code: int, json_data: dict, text: str = "") -> None:
        self.status_code = status_code
        self._json = json_data
        self.text = text

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict:
        return dict(self._json)


class FakeAsyncClient:
    def __init__(self, response: FakeResponse, capture: dict) -> None:
        self._response = response
        self._capture = capture

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None):
        self._capture["url"] = url
        self._capture["headers"] = headers or {}
        self._capture["json"] = json or {}
        return self._response


def test_login_anthropic_stores_credentials(monkeypatch, memory_storage):
    capture = {}
    response = FakeResponse(
        200,
        {
            "access_token": "access123",
            "refresh_token": "refresh123",
            "expires_in": 3600,
        },
    )

    def client_factory(*args, **kwargs):
        return FakeAsyncClient(response, capture)

    monkeypatch.setattr(oauth_anthropic.httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(oauth_anthropic, "generate_pkce", lambda: ("verifier", "challenge"))

    auth_urls = []

    def on_auth_url(url: str) -> None:
        auth_urls.append(url)

    async def on_prompt_code() -> str:
        return "authcode#authstate"

    creds = asyncio.run(oauth_anthropic.login_anthropic(on_auth_url, on_prompt_code))

    stored = load_oauth_credentials("anthropic")
    assert stored is not None
    assert stored.access == "access123"
    assert stored.refresh == "refresh123"
    assert creds.access == "access123"
    assert capture["json"]["code"] == "authcode"
    assert capture["json"]["state"] == "authstate"
    assert capture["json"]["code_verifier"] == "verifier"
    assert auth_urls and "code_challenge=challenge" in auth_urls[0]
    assert "state=verifier" in auth_urls[0]


def test_refresh_anthropic_token(monkeypatch):
    capture = {}
    response = FakeResponse(
        200,
        {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 1800,
        },
    )

    def client_factory(*args, **kwargs):
        return FakeAsyncClient(response, capture)

    monkeypatch.setattr(oauth_anthropic.httpx, "AsyncClient", client_factory)

    creds = asyncio.run(oauth_anthropic.refresh_anthropic_token("refresh-token"))
    assert creds.access == "new-access"
    assert creds.refresh == "new-refresh"
    assert capture["json"]["refresh_token"] == "refresh-token"


def test_resolve_oauth_overrides(memory_storage):
    save_oauth_credentials(
        "anthropic",
        OAuthCredentials(
            refresh="refresh",
            access="access",
            expires=int(time.time() * 1000) + 10 * 60_000,
        ),
    )

    overrides = asyncio.run(resolve_oauth_overrides("anthropic:claude-sonnet-4"))
    assert overrides is not None
    assert overrides.system_prompt == ANTHROPIC_OAUTH_SYSTEM_PROMPT
    assert overrides.model_settings is not None
    assert overrides.model_settings["extra_headers"]["accept"] == ANTHROPIC_OAUTH_ACCEPT
    beta_header = overrides.model_settings["extra_headers"]["anthropic-beta"]
    beta_flags = {item.strip() for item in beta_header.split(",") if item.strip()}
    assert ANTHROPIC_OAUTH_BETA in beta_flags
    for feature in ANTHROPIC_OAUTH_BETA_FEATURES:
        assert feature in beta_flags
    assert overrides.model_settings["extra_headers"][ANTHROPIC_OAUTH_DANGEROUS_HEADER] == "true"
    assert hasattr(overrides.model, "model_name")
