"""PKCE utilities for OAuth flows."""
from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Tuple


def generate_pkce() -> Tuple[str, str]:
    """Return (verifier, challenge) as base64url strings."""
    verifier_bytes = secrets.token_bytes(32)
    verifier = base64.urlsafe_b64encode(verifier_bytes).rstrip(b"=").decode("ascii")

    challenge_bytes = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(challenge_bytes).rstrip(b"=").decode("ascii")

    return verifier, challenge
