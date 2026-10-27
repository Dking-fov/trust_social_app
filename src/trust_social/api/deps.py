"""FastAPI dependencies for authentication, role-based authorization, and verified status guards."""

from typing import Optional
from fastapi import Depends, Header, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.trust_social.database import get_db
from src.trust_social.exceptions import PermissionDeniedException, UnauthorizedException
from src.trust_social.models import User, UserRole, VerificationStatus
from src.trust_social.security import decode_access_token

security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> User:
    """Retrieve and validate the currently authenticated user from Bearer JWT token."""
    raw_token: Optional[str] = None
    if auth and auth.credentials:
        raw_token = auth.credentials
    elif authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            raw_token = parts[1]
        elif len(parts) == 1:
            raw_token = parts[0]

    if not raw_token:
        raise UnauthorizedException(
            message="Authentication credentials were not provided.",
            error_code="UNAUTHORIZED",
        )

    payload = decode_access_token(raw_token)
    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        raise UnauthorizedException(
            message="Token payload is missing user identification.",
            error_code="INVALID_TOKEN",
        )

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise UnauthorizedException(
            message="Invalid user identifier in token.",
            error_code="INVALID_TOKEN",
        )

    user = db.query(User).filter(User.id == user_id_int, User.is_active.is_(True)).first()
    if not user:
        raise UnauthorizedException(
            message="User associated with this token does not exist or is inactive.",
            error_code="USER_NOT_FOUND",
        )

    if user.is_restricted:
        raise PermissionDeniedException(
            message="This account has been restricted due to policy violations.",
            details={"user_id": user.id},
        )

    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure that the authenticated user possesses administrator privileges."""
    if current_user.role != UserRole.ADMIN:
        raise PermissionDeniedException(
            message="Administrator privileges required for this action.",
            details={"current_role": str(current_user.role)},
        )
    return current_user


def require_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure that the authenticated user has verified educational credentials."""
    if current_user.verification_status != VerificationStatus.VERIFIED:
        raise PermissionDeniedException(
            message="Access restricted: verified educational credential is required.",
            details={"verification_status": str(current_user.verification_status)},
        )
    return current_user
