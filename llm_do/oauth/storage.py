"""OAuth credential storage with configurable backend."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Literal, Optional, Protocol
import json
import os

OAuthProvider = Literal["anthropic"]


@dataclass
class OAuthCredentials:
    """OAuth credentials for a provider."""

    type: Literal["oauth"] = "oauth"
    refresh: str = ""
    access: str = ""
    expires: int = 0
    enterprise_url: Optional[str] = None
    project_id: Optional[str] = None
    email: Optional[str] = None

    def is_expired(self, buffer_ms: int = 5 * 60 * 1000) -> bool:
        """Return True if the token is expired (with buffer)."""
        import time

        return int(time.time() * 1000) >= (self.expires - buffer_ms)

    def to_dict(self) -> Dict[str, object]:
        data: Dict[str, object] = {
            "type": self.type,
            "refresh": self.refresh,
            "access": self.access,
            "expires": self.expires,
        }
        if self.enterprise_url:
            data["enterpriseUrl"] = self.enterprise_url
        if self.project_id:
            data["projectId"] = self.project_id
        if self.email:
            data["email"] = self.email
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "OAuthCredentials":
        type_value = data.get("type")
        refresh_value = data.get("refresh")
        access_value = data.get("access")
        expires_value = data.get("expires")
        try:
            expires = int(expires_value) if expires_value is not None else 0
        except (TypeError, ValueError):
            expires = 0

        return cls(
            type=type_value if isinstance(type_value, str) else "oauth",
            refresh=refresh_value if isinstance(refresh_value, str) else "",
            access=access_value if isinstance(access_value, str) else "",
            expires=expires,
            enterprise_url=data.get("enterpriseUrl") if isinstance(data.get("enterpriseUrl"), str) else None,
            project_id=data.get("projectId") if isinstance(data.get("projectId"), str) else None,
            email=data.get("email") if isinstance(data.get("email"), str) else None,
        )


class OAuthStorageBackend(Protocol):
    """Storage backend protocol for OAuth credentials."""

    def load(self) -> Dict[str, OAuthCredentials]:
        """Load all OAuth credentials."""

    def save(self, storage: Dict[str, OAuthCredentials]) -> None:
        """Save all OAuth credentials."""


class FileSystemStorage:
    """Default filesystem storage backend."""

    DEFAULT_PATH = Path.home() / ".llm-do" / "oauth.json"

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or self.DEFAULT_PATH

    def load(self) -> Dict[str, OAuthCredentials]:
        if not self.path.exists():
            return {}
        try:
            content = self.path.read_text("utf-8")
            data = json.loads(content)
            if not isinstance(data, dict):
                return {}
            return {
                provider: OAuthCredentials.from_dict(creds)
                for provider, creds in data.items()
                if isinstance(creds, dict)
            }
        except (OSError, json.JSONDecodeError):
            return {}

    def save(self, storage: Dict[str, OAuthCredentials]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        data = {provider: creds.to_dict() for provider, creds in storage.items()}
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass


_storage_backend: OAuthStorageBackend = FileSystemStorage()


def set_oauth_storage(backend: OAuthStorageBackend) -> None:
    """Configure the OAuth storage backend."""
    global _storage_backend
    _storage_backend = backend


def reset_oauth_storage() -> None:
    """Reset to default filesystem storage."""
    global _storage_backend
    _storage_backend = FileSystemStorage()


def get_oauth_path() -> Path:
    """Return the default OAuth storage path."""
    return FileSystemStorage.DEFAULT_PATH


def load_oauth_storage() -> Dict[str, OAuthCredentials]:
    """Load all OAuth credentials."""
    return _storage_backend.load()


def load_oauth_credentials(provider: str) -> Optional[OAuthCredentials]:
    """Load OAuth credentials for a specific provider."""
    return _storage_backend.load().get(provider)


def save_oauth_credentials(provider: str, creds: OAuthCredentials) -> None:
    """Save OAuth credentials for a specific provider."""
    storage = _storage_backend.load()
    storage[provider] = creds
    _storage_backend.save(storage)


def remove_oauth_credentials(provider: str) -> None:
    """Remove OAuth credentials for a specific provider."""
    storage = _storage_backend.load()
    storage.pop(provider, None)
    _storage_backend.save(storage)


def has_oauth_credentials(provider: str) -> bool:
    """Return True if OAuth credentials exist for a provider."""
    return load_oauth_credentials(provider) is not None


def list_oauth_providers() -> list[str]:
    """List all providers with stored OAuth credentials."""
    return list(_storage_backend.load().keys())
