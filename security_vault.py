"""Credential vault primitives for DUCMANH AI Connection Center.

The caller must load the 32-byte master key from a dedicated Render secret.
This module never reads credentials from request logs or returns plaintext
through API responses. Key rotation is versioned by the caller.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AAD_PREFIX = b"ducmanh-ai:connection-credential:v1:"


class VaultConfigurationError(RuntimeError):
    pass


def _master_key() -> bytes:
    raw = os.getenv("CONNECTIONS_MASTER_KEY", "").strip()
    if not raw:
        raise VaultConfigurationError("CONNECTIONS_MASTER_KEY is not configured")
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except Exception as exc:
        raise VaultConfigurationError("CONNECTIONS_MASTER_KEY must be URL-safe base64") from exc
    if len(key) != 32:
        raise VaultConfigurationError("CONNECTIONS_MASTER_KEY must decode to exactly 32 bytes")
    return key


def encrypt_credential(connection_id: str, plaintext: str) -> dict[str, bytes | str]:
    if not connection_id or not plaintext:
        raise ValueError("connection_id and credential are required")
    nonce = os.urandom(12)
    aad = AAD_PREFIX + connection_id.encode("utf-8")
    ciphertext = AESGCM(_master_key()).encrypt(nonce, plaintext.encode("utf-8"), aad)
    return {"ciphertext": ciphertext, "nonce": nonce, "key_version": "v1"}


def decrypt_credential(connection_id: str, ciphertext: bytes, nonce: bytes) -> str:
    aad = AAD_PREFIX + connection_id.encode("utf-8")
    try:
        return AESGCM(_master_key()).decrypt(nonce, ciphertext, aad).decode("utf-8")
    except Exception as exc:
        raise VaultConfigurationError("Credential decryption failed") from exc


def hash_session_token(token: str) -> bytes:
    """Hash extension bearer tokens before storage; never persist raw tokens."""
    if not token:
        raise ValueError("token is required")
    pepper = os.getenv("SESSION_TOKEN_PEPPER", "").encode("utf-8")
    if len(pepper) < 32:
        raise VaultConfigurationError("SESSION_TOKEN_PEPPER must contain at least 32 characters")
    return hmac.new(pepper, token.encode("utf-8"), hashlib.sha256).digest()
