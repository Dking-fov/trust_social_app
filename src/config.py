"""Application settings and environment configuration."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "High-Trust Dating App"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./dating_app.db"

    # Security & JWT
    SECRET_KEY: str = "super-secret-key-change-in-production-high-trust-dating-app-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # AES-256 Storage Encryption Key (32-byte hex or url-safe key)
    STORAGE_ENCRYPTION_KEY: str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    PRESIGNED_URL_EXPIRE_SECONDS: int = 300  # 5 minutes

    # Bayesian Reputation Baseline
    BAYESIAN_PRIOR_WEIGHT_M: float = 5.0
    BAYESIAN_BASELINE_SCORE_C: float = 3.5

    # Daily Matching Pool Quota
    DAILY_RECOMMENDATION_QUOTA: int = 10
    EXTRA_PACK_CARD_COUNT: int = 5
    EXTRA_PACK_COST_POINTS: int = 30
    TARGETED_SEARCH_COST_POINTS: int = 100

    # Date check-in rules
    GPS_GEOFENCE_RADIUS_METERS: float = 100.0
    TOTP_STEP_SECONDS: int = 60
    CANCELLATION_FREE_WINDOW_HOURS: float = 4.0
    REVIEW_UNLOCK_DELAY_HOURS: float = 2.0
    REVIEW_AUTO_REVEAL_HOURS: float = 48.0
    COLLUSION_COOLDOWN_DAYS: int = 30


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
