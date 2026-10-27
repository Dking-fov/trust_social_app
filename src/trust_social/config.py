"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings using Pydantic Settings management."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application
    PROJECT_NAME: str = "trust_social_app"
    APP_NAME: str = "Trust Social App"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./trust_social.db"

    # Security & JWT Authentication
    JWT_SECRET: str = "super-secret-jwt-key-for-trust-social-app-change-in-production-2026"
    SECRET_KEY: str = "super-secret-jwt-key-for-trust-social-app-change-in-production-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # AES-256-GCM Storage Encryption (32 bytes hex or raw key)
    ENCRYPTION_KEY: str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    STORAGE_ENCRYPTION_KEY: str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    # Daily Curated Matching & Multi-Factor Ranking
    DAILY_DECK_LIMIT: int = 10
    DAILY_RECOMMENDATION_QUOTA: int = 10
    RANKING_BAYESIAN_WEIGHT: float = 0.7
    RANKING_NEW_USER_WEIGHT: float = 0.2
    RANKING_RECENCY_WEIGHT: float = 0.1

    # Bayesian Reputation Parameters: R = (C * m + sum(ratings)) / (C + n)
    BAYESIAN_BASELINE_SCORE_M: float = 3.5
    BAYESIAN_PRIOR_WEIGHT_C: float = 5.0
    NEW_USER_WINDOW_HOURS: int = 72
    RECENCY_WINDOW_HOURS: int = 48

    # Offline Date Dual Verification
    TOTP_STEP_SECONDS: int = 60
    TOTP_WINDOW: int = 1
    GPS_GEOFENCE_RADIUS_METERS: float = 100.0

    # Double-Blind Review & Circuit Breaker Timings
    REVIEW_UNLOCK_DELAY_HOURS: float = 2.0
    REVIEW_AUTO_REVEAL_HOURS: float = 48.0
    REVIEW_COOLDOWN_DAYS: int = 30
    CHAT_CIRCUIT_BREAKER_DAYS: int = 7

    # Points Economy & Incentives
    POINTS_EDU_VERIFICATION: int = 100
    POINTS_DAILY_LOGIN: int = 5
    POINTS_HIGH_SCORE_DATE: int = 30
    POINTS_DECK_REFRESH_COST: int = 20
    POINTS_CRUSH_DISCOVERY_COST: int = 50
    POINTS_REPORT_BOUNTY: int = 50


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()
