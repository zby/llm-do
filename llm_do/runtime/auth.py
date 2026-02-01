"""Auth configuration shared types."""
from __future__ import annotations

from typing import Literal, TypeAlias

AuthMode: TypeAlias = Literal["oauth_off", "oauth_auto", "oauth_required"]
