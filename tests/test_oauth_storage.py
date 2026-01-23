import asyncio
import time

import pytest

from llm_do import oauth
from llm_do.oauth.storage import OAuthCredentials, OAuthStorage


class InMemoryStorage:
    def __init__(self) -> None:
        self._storage: dict[str, dict[str, object]] = {}

    def load(self):
        return dict(self._storage)

    def save(self, storage):
        self._storage = dict(storage)


@pytest.fixture
def memory_storage():
    return OAuthStorage(InMemoryStorage())


def test_save_and_load_credentials(memory_storage):
    creds = OAuthCredentials(
        refresh="refresh_token",
        access="access_token",
        expires=1234567890000,
    )

    memory_storage.save_credentials("anthropic", creds)
    loaded = memory_storage.load_credentials("anthropic")

    assert loaded is not None
    assert loaded.refresh == "refresh_token"
    assert loaded.access == "access_token"
    assert loaded.expires == 1234567890000

    memory_storage.remove_credentials("anthropic")
    assert memory_storage.load_credentials("anthropic") is None


def test_get_oauth_api_key_refreshes(monkeypatch, memory_storage):
    creds = OAuthCredentials(
        refresh="refresh_token",
        access="stale_token",
        expires=0,
    )
    memory_storage.save_credentials("anthropic", creds)

    async def fake_refresh(provider: str, storage=None) -> str:
        target_storage = storage or memory_storage
        new_creds = OAuthCredentials(
            refresh="refresh_token_2",
            access="fresh_token",
            expires=int(time.time() * 1000) + 60_000,
        )
        target_storage.save_credentials(provider, new_creds)
        return new_creds.access

    monkeypatch.setattr(oauth, "refresh_token", fake_refresh)

    token = asyncio.run(oauth.get_oauth_api_key("anthropic", storage=memory_storage))
    assert token == "fresh_token"
