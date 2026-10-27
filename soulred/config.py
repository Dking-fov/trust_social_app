"""Global configuration management for SoulRed Social Platform.

Loads configuration from environment variables or .env file with Pydantic Settings.
"""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application global settings."""

    # Project metadata
    APP_NAME: str = "SoulRed Social Platform"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = ["*"]

    # Database Configuration
    DATABASE_URL: str = "sqlite:///./soulred.db"
    SQLITE_CHECK_SAME_THREAD: bool = False
    DB_ECHO: bool = False

    # Security & JWT Configuration
    SECRET_KEY: str = "soulred-super-secret-jwt-key-2026-very-secure-random-token"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # AES-256-GCM Encryption Key (Must be 32 bytes or 64-hex string)
    # Default 32-byte key represented as 64 hex characters
    AES_SECRET_KEY: str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    # Business Rules & Quotas
    STRANGER_DAILY_MSG_LIMIT: int = 1
    MATCHING_COSINE_THRESHOLD: float = 0.80

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Retrieve cached global settings instance."""
    return Settings()
