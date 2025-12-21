import asyncio
import time

import pytest

from llm_do import oauth
from llm_do.oauth.storage import (
    OAuthCredentials,
    load_oauth_credentials,
    remove_oauth_credentials,
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


def test_save_and_load_credentials(memory_storage):
    creds = OAuthCredentials(
        refresh="refresh_token",
        access="access_token",
        expires=1234567890000,
    )

    save_oauth_credentials("anthropic", creds)
    loaded = load_oauth_credentials("anthropic")

    assert loaded is not None
    assert loaded.refresh == "refresh_token"
    assert loaded.access == "access_token"
    assert loaded.expires == 1234567890000

    remove_oauth_credentials("anthropic")
    assert load_oauth_credentials("anthropic") is None


def test_get_oauth_api_key_refreshes(monkeypatch, memory_storage):
    creds = OAuthCredentials(
        refresh="refresh_token",
        access="stale_token",
        expires=0,
    )
    save_oauth_credentials("anthropic", creds)

    async def fake_refresh(provider: str) -> str:
        new_creds = OAuthCredentials(
            refresh="refresh_token_2",
            access="fresh_token",
            expires=int(time.time() * 1000) + 60_000,
        )
        save_oauth_credentials(provider, new_creds)
        return new_creds.access

    monkeypatch.setattr(oauth, "refresh_token", fake_refresh)

    token = asyncio.run(oauth.get_oauth_api_key("anthropic"))
    assert token == "fresh_token"
