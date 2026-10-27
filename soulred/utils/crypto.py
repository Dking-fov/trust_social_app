"""Cryptographic and security utilities for SoulRed.

Provides:
- AES-256-GCM encryption and decryption for sensitive PII (real name, ID card, phone)
- Bcrypt password hashing and verification
- PyJWT access token generation and payload decoding
"""

import os
import base64
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Union

import jwt
from passlib.context import CryptContext
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from soulred.config import get_settings

# Passlib bcrypt context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _derive_aes_key(key: Optional[Union[str, bytes]] = None) -> bytes:
    """Derive a fixed 32-byte key for AES-256."""
    if key is None:
        key = get_settings().AES_SECRET_KEY

    if isinstance(key, str):
        try:
            raw = bytes.fromhex(key)
            if len(raw) == 32:
                return raw
        except ValueError:
            pass
        return hashlib.sha256(key.encode("utf-8")).digest()
    elif isinstance(key, bytes):
        if len(key) == 32:
            return key
        return hashlib.sha256(key).digest()
    raise ValueError("Invalid key format for AES-256 encryption")


def encrypt_field(data: Optional[str], key: Optional[Union[str, bytes]] = None) -> Optional[str]:
    """Encrypt a plaintext string using AES-256-GCM.

    Returns a base64-encoded string combining 12-byte nonce and ciphertext + tag.
    Returns None if input is None.
    """
    if data is None:
        return None
    if data == "":
        return ""

    key_bytes = _derive_aes_key(key)
    aesgcm = AESGCM(key_bytes)
    nonce = os.urandom(12)  # 96-bit standard nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, data.encode("utf-8"), None)
    # Combined payload: nonce + ciphertext
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode("utf-8")


def decrypt_field(cipher_text: Optional[str], key: Optional[Union[str, bytes]] = None) -> Optional[str]:
    """Decrypt an AES-256-GCM encrypted base64 string.

    Returns decrypted plaintext string, or None if input is None.
    """
    if cipher_text is None:
        return None
    if cipher_text == "":
        return ""

    key_bytes = _derive_aes_key(key)
    aesgcm = AESGCM(key_bytes)
    raw = base64.b64decode(cipher_text.encode("utf-8"))
    if len(raw) < 12:
        raise ValueError("Ciphertext payload is truncated or invalid")

    nonce = raw[:12]
    ciphertext = raw[12:]
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted_bytes.decode("utf-8")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT access token."""
    settings = get_settings()
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token."""
    settings = get_settings()
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
