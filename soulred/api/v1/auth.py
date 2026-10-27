"""Authentication and identity verification REST endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from soulred.api.deps import get_db_session, get_current_active_user
from soulred.models.user import User
from soulred.schemas.user import (
    UserCreate,
    UserLogin,
    TokenResponse,
    VerificationSubmitSchema,
    VerificationBadgeResponse,
    UserProfileResponse,
    PrivacySettingSchema,
)
from soulred.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def build_user_profile_response(user: User) -> UserProfileResponse:
    """Helper to assemble full UserProfileResponse from User ORM model."""
    profile = user.profile
    badges = [
        VerificationBadgeResponse.model_validate(b)
        for b in (user.verification_badges or [])
    ]
    privacy = (
        PrivacySettingSchema.model_validate(user.privacy_setting)
        if user.privacy_setting
        else None
    )

    return UserProfileResponse(
        id=profile.id if profile else user.id,
        user_id=user.id,
        username=user.username,
        nickname=profile.nickname if profile else user.username,
        avatar_url=profile.avatar_url if profile else None,
        bio=profile.bio if profile else None,
        gender=profile.gender if profile else "secret",
        age=profile.age if profile else None,
        birth_date=profile.birth_date if profile else None,
        location=profile.location if profile else None,
        voice_card_url=profile.voice_card_url if profile else None,
        mbti=profile.mbti if profile else None,
        interest_tags=profile.interest_tags if profile else [],
        badges=badges,
        privacy=privacy,
    )


@router.post(
    "/register",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user account",
)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db_session),
) -> UserProfileResponse:
    """Register a new user account with default profile and privacy configurations."""
    user = AuthService.register_user(db=db, user_in=user_in)
    return build_user_profile_response(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain JWT access token",
)
def login(
    login_in: UserLogin,
    db: Session = Depends(get_db_session),
) -> TokenResponse:
    """Authenticate user credentials and issue signed JWT bearer token."""
    user = AuthService.authenticate_user(
        db=db,
        username=login_in.username,
        password=login_in.password,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AuthService.create_user_token(user=user)


@router.post(
    "/verification",
    response_model=VerificationBadgeResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit QingTeng authenticity credentials",
)
def submit_verification(
    verification_in: VerificationSubmitSchema,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> VerificationBadgeResponse:
    """Submit real-name, education, or career credentials for official review."""
    badge = AuthService.submit_verification(
        db=db,
        user_id=current_user.id,
        verification_in=verification_in,
    )
    return VerificationBadgeResponse.model_validate(badge)
