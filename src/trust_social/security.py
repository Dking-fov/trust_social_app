"""Cryptographic utilities including password hashing, JWT generation/validation, and AES-256-GCM encryption."""

import base64
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from passlib.context import CryptContext

from src.trust_social.config import get_settings
from src.trust_social.exceptions import InvalidCredentialException, UnauthorizedException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": now})
    secret = settings.JWT_SECRET or settings.SECRET_KEY
    encoded_jwt = jwt.encode(to_encode, secret, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token, raising UnauthorizedException if invalid."""
    secret = settings.JWT_SECRET or settings.SECRET_KEY
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException(
            message="Token has expired. Please log in again.",
            error_code="TOKEN_EXPIRED",
        )
    except jwt.PyJWTError as e:
        raise UnauthorizedException(
            message=f"Invalid authentication token: {str(e)}",
            error_code="INVALID_TOKEN",
        )


def _derive_32byte_key(key: Optional[Union[str, bytes]] = None) -> bytes:
    """Normalize or derive a 32-byte key for AES-256-GCM."""
    raw_key = key if key is not None else (settings.ENCRYPTION_KEY or settings.STORAGE_ENCRYPTION_KEY)
    if isinstance(raw_key, str):
        # Try parsing as hex string first
        if len(raw_key) == 64:
            try:
                return bytes.fromhex(raw_key)
            except ValueError:
                pass
        raw_bytes = raw_key.encode("utf-8")
    else:
        raw_bytes = raw_key

    if len(raw_bytes) == 32:
        return raw_bytes
    # Hash to produce a deterministic 32-byte key
    return hashlib.sha256(raw_bytes).digest()


def encrypt_credential_data(
    data: Union[str, bytes, Dict[str, Any]],
    key: Optional[Union[str, bytes]] = None,
) -> str:
    """Encrypt sensitive educational credential payload using AES-256-GCM with authentication tag.

    Returns a URL-safe base64 string combining 12-byte nonce and ciphertext with 16-byte auth tag.
    """
    derived_key = _derive_32byte_key(key)
    aesgcm = AESGCM(derived_key)

    if isinstance(data, dict):
        plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    elif isinstance(data, str):
        plaintext = data.encode("utf-8")
    elif isinstance(data, bytes):
        plaintext = data
    else:
        plaintext = str(data).encode("utf-8")

    # Generate 12-byte standard GCM nonce
    nonce = os.urandom(12)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)

    # Pack nonce + ciphertext_with_tag and encode as urlsafe base64
    packed = nonce + ciphertext_with_tag
    return base64.urlsafe_b64encode(packed).decode("ascii")


def decrypt_credential_data(
    encrypted_data: str,
    key: Optional[Union[str, bytes]] = None,
) -> str:
    """Decrypt an AES-256-GCM encrypted payload, verifying authenticity tag."""
    derived_key = _derive_32byte_key(key)
    aesgcm = AESGCM(derived_key)

    try:
        # Check if base64 or hex
        try:
            packed = base64.urlsafe_b64decode(encrypted_data.encode("ascii"))
        except Exception:
            # Fallback check if it was stored as hex
            packed = bytes.fromhex(encrypted_data)

        if len(packed) < 28:  # 12 bytes nonce + 16 bytes auth tag minimum
            raise InvalidCredentialException(
                message="Corrupted credential payload: data too short for AES-GCM.",
                details={"length": len(packed)},
            )

        nonce = packed[:12]
        ciphertext_with_tag = packed[12:]
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
        return decrypted_bytes.decode("utf-8")
    except InvalidCredentialException:
        raise
    except Exception as exc:
        raise InvalidCredentialException(
            message=f"Failed to decrypt credential data: {str(exc)}",
            details={"error": str(exc)},
        )
