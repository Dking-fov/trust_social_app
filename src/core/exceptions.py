"""Domain-specific exceptions and error code constants matching the PRD specification."""

from enum import Enum
from typing import Any, Optional


class AppErrorCode(str, Enum):
    """Platform error codes matching PRD and specifications."""
    ERR_AUTH_REQUIRED = "ERR_AUTH_REQUIRED"
    ERR_INVALID_TAGS_COUNT = "ERR_INVALID_TAGS_COUNT"
    ERR_UNDERAGE_OR_OVERAGE = "ERR_UNDERAGE_OR_OVERAGE"
    ERR_MATCH_EXPIRED = "ERR_MATCH_EXPIRED"
    ERR_GEO_SPOOFING_DETECTED = "ERR_GEO_SPOOFING_DETECTED"
    ERR_INSUFFICIENT_POINTS = "ERR_INSUFFICIENT_POINTS"
    ERR_DAILY_REFRESH_LIMIT_REACHED = "ERR_DAILY_REFRESH_LIMIT_REACHED"
    ERR_USER_ALREADY_EXISTS = "ERR_USER_ALREADY_EXISTS"
    ERR_INVALID_CREDENTIALS = "ERR_INVALID_CREDENTIALS"
    ERR_NOT_FOUND = "ERR_NOT_FOUND"
    ERR_INVALID_DATE_STATE = "ERR_INVALID_DATE_STATE"
    ERR_REVIEW_LOCKED = "ERR_REVIEW_LOCKED"
    ERR_COLLUSION_COOLDOWN = "ERR_COLLUSION_COOLDOWN"


class AppBaseException(Exception):
    """Base exception for application business logic errors."""

    def __init__(
        self,
        status_code: int,
        error_code: str | AppErrorCode,
        message: str,
        details: Optional[Any] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = str(error_code.value if isinstance(error_code, AppErrorCode) else error_code)
        self.message = message
        self.details = details


class AuthRequiredException(AppBaseException):
    """Raised when an unverified user tries to access gated features."""

    def __init__(self, message: str = "Feature requires verified education credentials."):
        super().__init__(
            status_code=403,
            error_code=AppErrorCode.ERR_AUTH_REQUIRED,
            message=message,
        )


class InvalidTagsCountException(AppBaseException):
    """Raised when interest tags count is less than 3 or greater than 8."""

    def __init__(self, message: str = "Interest tags count must be between 3 and 8 inclusive."):
        super().__init__(
            status_code=422,
            error_code=AppErrorCode.ERR_INVALID_TAGS_COUNT,
            message=message,
        )


class UnderageOrOverageException(AppBaseException):
    """Raised when user age is outside [20, 35]."""

    def __init__(self, message: str = "User age must be between 20 and 35 years old."):
        super().__init__(
            status_code=422,
            error_code=AppErrorCode.ERR_UNDERAGE_OR_OVERAGE,
            message=message,
        )


class MatchExpiredException(AppBaseException):
    """Raised when messaging an inactive/circuit-broken conversation."""

    def __init__(self, message: str = "Conversation has expired and match is dissolved due to 7-day inactivity."):
        super().__init__(
            status_code=410,
            error_code=AppErrorCode.ERR_MATCH_EXPIRED,
            message=message,
        )


class GeoSpoofingException(AppBaseException):
    """Raised when client mock location or GPS spoofing is detected."""

    def __init__(self, message: str = "Mock location or GPS spoofing detected. Check-in rejected."):
        super().__init__(
            status_code=403,
            error_code=AppErrorCode.ERR_GEO_SPOOFING_DETECTED,
            message=message,
        )


class InsufficientPointsException(AppBaseException):
    """Raised when points balance is lower than feature cost."""

    def __init__(self, message: str = "Insufficient points balance for this action."):
        super().__init__(
            status_code=402,
            error_code=AppErrorCode.ERR_INSUFFICIENT_POINTS,
            message=message,
        )


class DailyRefreshLimitException(AppBaseException):
    """Raised when daily recommendation card refresh quota is exceeded."""

    def __init__(self, message: str = "Daily recommendation pack refresh limit reached (1 refresh/day)."):
        super().__init__(
            status_code=400,
            error_code=AppErrorCode.ERR_DAILY_REFRESH_LIMIT_REACHED,
            message=message,
        )
