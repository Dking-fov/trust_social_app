"""FastAPI dependency injection utilities for SoulRed.

Provides:
- Database session dependency (get_db_session)
- JWT token validation and current authenticated user retrieval (get_current_user)
- Optional user dependency for public browsing (get_optional_current_user)
- Active user state check (get_current_active_user)
"""

from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

from soulred.database import SessionLocal, get_db
from soulred.models.user import User
from soulred.utils.crypto import decode_access_token

# OAuth2 scheme configured for token endpoint
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


def get_db_session() -> Generator[Session, None, None]:
    """Provide transactional database session per request lifecycle."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db_session),
) -> Optional[User]:
    """Attempt retrieving user from token if present, otherwise return None without raising 401."""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id: Optional[str] = payload.get("sub") or payload.get("user_id")
        if not user_id:
            return None
        return (
            db.query(User)
            .filter(User.id == user_id, User.is_deleted == False)
            .first()
        )
    except (jwt.PyJWTError, Exception):
        return None


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db_session),
) -> User:
    """Validate JWT token from Authorization header and retrieve matching user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    try:
        payload = decode_access_token(token)
        user_id: Optional[str] = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise credentials_exception
    except (jwt.PyJWTError, Exception):
        raise credentials_exception

    user = (
        db.query(User)
        .filter(User.id == user_id, User.is_deleted == False)
        .first()
    )
    if not user:
        raise credentials_exception

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Verify that current user account is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )
    return current_user
