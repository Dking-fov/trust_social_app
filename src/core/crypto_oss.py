"""Private OSS simulation with AES-256-GCM encryption and 5-minute pre-signed access URLs."""

import os
import time
import base64
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import jwt

from src.config import get_settings

settings = get_settings()


def get_encryption_key() -> bytes:
    """Derive 32-byte key for AES-256."""
    raw_key = settings.STORAGE_ENCRYPTION_KEY.encode("utf-8")
    if len(raw_key) < 32:
        return raw_key.ljust(32, b"0")
    return raw_key[:32]


def encrypt_document(data: bytes, key: Optional[bytes] = None) -> bytes:
    """Encrypt byte data with AES-256-GCM.
    Returns: 12-byte nonce + ciphertext + 16-byte tag.
    """
    if key is None:
        key = get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce + ciphertext


def decrypt_document(encrypted_data: bytes, key: Optional[bytes] = None) -> bytes:
    """Decrypt byte data with AES-256-GCM."""
    if key is None:
        key = get_encryption_key()
    if len(encrypted_data) < 28:
        raise ValueError("Encrypted data too short")
    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def generate_presigned_url(file_key: str, expires_in: int = 300) -> str:
    """Generate a temporary pre-signed URL (default 5-minute maximum expiration)."""
    now = int(time.time())
    payload = {
        "sub": "oss_presigned_download",
        "file_key": file_key,
        "exp": now + min(expires_in, settings.PRESIGNED_URL_EXPIRE_SECONDS),
        "iat": now,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return f"/api/v1/auth/documents/download?token={token}"


class EncryptedStorageService:
    """In-memory private encrypted object storage service simulator."""

    def __init__(self, key: Optional[bytes] = None):
        self.key = key or get_encryption_key()
        # In-memory storage: file_key -> encrypted bytes
        self._store: dict[str, bytes] = {}

    def upload_file(self, file_bytes: bytes, filename: str) -> str:
        """Encrypts and stores file at rest with AES-256-GCM."""
        encrypted = encrypt_document(file_bytes, self.key)
        rand_suffix = os.urandom(8).hex()
        file_key = f"credentials/{rand_suffix}_{filename}"
        self._store[file_key] = encrypted
        return file_key

    def download_file(self, file_key: str) -> bytes:
        """Retrieves and decrypts file content."""
        if file_key not in self._store:
            raise KeyError(f"File key not found: {file_key}")
        encrypted = self._store[file_key]
        return decrypt_document(encrypted, self.key)

    def generate_presigned_url(self, file_key: str, expires_in: int = 300) -> str:
        """Returns signed URL with 5-minute TTL."""
        return generate_presigned_url(file_key, expires_in)

    def verify_presigned_token(self, token: str) -> Optional[str]:
        """Validates token and returns file_key if valid and unexpired."""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            if payload.get("sub") != "oss_presigned_download":
                return None
            return payload.get("file_key")
        except jwt.PyJWTError:
            return None


# Global singleton instance
storage_service = EncryptedStorageService()
