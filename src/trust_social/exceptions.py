"""Standardized domain exceptions for the Trust Social platform.

All exceptions follow a consistent format matching the platform's unified error protocol:
{"error_code": str, "message": str, "details": dict}
"""

from typing import Any, Dict, Optional


class AppException(Exception):
    """Base domain exception for application-level errors."""

    def __init__(
        self,
        message: str = "An unexpected application error occurred.",
        error_code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to standardized JSON error dictionary."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class EntityNotFoundException(AppException):
    """Raised when a requested resource or entity cannot be found."""

    def __init__(
        self,
        message: str = "Requested entity was not found.",
        entity_name: Optional[str] = None,
        entity_id: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        err_details = details or {}
        if entity_name:
            err_details["entity_name"] = entity_name
        if entity_id is not None:
            err_details["entity_id"] = entity_id
        super().__init__(
            message=message,
            error_code="ENTITY_NOT_FOUND",
            status_code=404,
            details=err_details,
        )


class UnauthorizedException(AppException):
    """Raised when authentication credentials are missing, invalid, or expired."""

    def __init__(
        self,
        message: str = "Authentication credentials are invalid or missing.",
        error_code: str = "UNAUTHORIZED",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=401,
            details=details,
        )


class PermissionDeniedException(AppException):
    """Raised when the authenticated user does not have permission for an action."""

    def __init__(
        self,
        message: str = "Permission denied for this operation.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
            status_code=403,
            details=details,
        )


class InsufficientPointsException(AppException):
    """Raised when an operation requires more points than the user balance."""

    def __init__(
        self,
        message: str = "Insufficient points balance for this transaction.",
        current_balance: Optional[int] = None,
        required_points: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        err_details = details or {}
        if current_balance is not None:
            err_details["current_balance"] = current_balance
        if required_points is not None:
            err_details["required_points"] = required_points
        super().__init__(
            message=message,
            error_code="INSUFFICIENT_POINTS",
            status_code=400,
            details=err_details,
        )


class InvalidCredentialException(AppException):
    """Raised when submitted credentials fail validation or integrity verification."""

    def __init__(
        self,
        message: str = "Educational credential validation failed.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="INVALID_CREDENTIAL",
            status_code=400,
            details=details,
        )


class DeckExhaustedException(AppException):
    """Raised when user has swiped through all candidates in the daily deck."""

    def __init__(
        self,
        message: str = "Daily candidate deck has been exhausted. Refresh with points or wait until midnight.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="DECK_EXHAUSTED",
            status_code=400,
            details=details,
        )


class DateCheckInException(AppException):
    """Raised when offline date check-in verification fails (TOTP or GPS geofence)."""

    def __init__(
        self,
        message: str = "Offline date check-in failed.",
        reason: Optional[str] = None,
        distance_meters: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        err_details = details or {}
        if reason:
            err_details["reason"] = reason
        if distance_meters is not None:
            err_details["distance_meters"] = distance_meters
        super().__init__(
            message=message,
            error_code="DATE_CHECKIN_FAILED",
            status_code=400,
            details=err_details,
        )


class ReviewCooldownException(AppException):
    """Raised when attempting to submit a review within the 30-day anti-collusion cooldown."""

    def __init__(
        self,
        message: str = "Review rejected: 30-day anti-collusion cooldown active for this pair.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="REVIEW_COOLDOWN_ACTIVE",
            status_code=400,
            details=details,
        )


class DoubleBlindReviewLockedException(AppException):
    """Raised when accessing or submitting reviews before the unlock conditions are met."""

    def __init__(
        self,
        message: str = "Post-date review is currently locked.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="REVIEW_LOCKED",
            status_code=400,
            details=details,
        )


class ChatCircuitBreakerException(AppException):
    """Raised when attempting actions on a dissolved or inactive chat session."""

    def __init__(
        self,
        message: str = "Match session has been dissolved due to 7-day inactivity circuit breaker.",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="CHAT_CIRCUIT_BREAKER_TRIGGERED",
            status_code=400,
            details=details,
        )
