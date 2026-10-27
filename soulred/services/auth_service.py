"""Authentication, user identity, verification, and privacy filtering service.

Provides:
- User registration with bcrypt hashing & AES-256 encrypted PII
- User credential authentication and token issuance
- QingTeng-style multi-tier authenticity verification submissions
- Privacy filters with coordinate masking and contact incognito checks
"""

import math
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from soulred.models.user import (
    User,
    UserProfile,
    VerificationBadge,
    PrivacySetting,
    VerificationStatusEnum,
    VerificationTypeEnum,
    GenderEnum,
)
from soulred.schemas.user import (
    UserCreate,
    VerificationSubmitSchema,
    TokenResponse,
)
from soulred.utils.crypto import (
    hash_password,
    verify_password,
    encrypt_field,
    decrypt_field,
    create_access_token,
)


def mask_phone_number(phone: Optional[str]) -> Optional[str]:
    """Mask central digits of a mobile phone number (e.g. 138****1234)."""
    if not phone:
        return None
    cleaned = phone.strip()
    if len(cleaned) == 11:
        return f"{cleaned[:3]}****{cleaned[7:]}"
    elif len(cleaned) > 4:
        mid = len(cleaned) // 2
        return f"{cleaned[:mid-2]}****{cleaned[mid+2:]}"
    return "****"


class AuthService:
    """Core domain service for user security, credentials, and verification."""

    @classmethod
    def register_user(cls, db: Session, user_in: UserCreate) -> User:
        """Register a new user account with default profile and privacy settings."""
        # 1. Check duplicate username
        existing_user = db.query(User).filter(User.username == user_in.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Username '{user_in.username}' is already registered",
            )

        # 2. Encrypt phone number with AES-256-GCM if provided
        phone_encrypted = encrypt_field(user_in.phone) if user_in.phone else None

        # 3. Hash password
        hashed_pwd = hash_password(user_in.password)

        # 4. Create User entity
        user = User(
            username=user_in.username,
            phone_encrypted=phone_encrypted,
            email=user_in.email,
            hashed_password=hashed_pwd,
            is_active=True,
        )
        db.add(user)
        db.flush()  # Obtain user.id

        # 5. Create default UserProfile
        profile = UserProfile(
            user_id=user.id,
            nickname=user_in.nickname or user_in.username,
            avatar_url=user_in.avatar_url or "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=400&q=80",
            gender=user_in.gender or GenderEnum.SECRET.value,
            mbti=user_in.mbti,
            interest_tags=[],
        )
        db.add(profile)

        # 6. Create default PrivacySetting
        privacy = PrivacySetting(
            user_id=user.id,
            hide_distance=False,
            hide_from_nearby=False,
            incognito_contacts=False,
            stranger_msg_restricted=True,
        )
        db.add(privacy)

        db.commit()
        db.refresh(user)
        return user

    @classmethod
    def authenticate_user(
        cls,
        db: Session,
        username: str,
        password: str,
    ) -> Optional[User]:
        """Authenticate user by username or decrypted phone number."""
        user = db.query(User).filter(User.username == username).first()

        # If not found by username, inspect matching encrypted phones
        if not user:
            all_users_with_phone = db.query(User).filter(User.phone_encrypted.isnot(None)).all()
            for u in all_users_with_phone:
                try:
                    decrypted = decrypt_field(u.phone_encrypted)
                    if decrypted == username:
                        user = u
                        break
                except Exception:
                    continue

        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated or suspended",
            )

        return user

    @classmethod
    def create_user_token(cls, user: User) -> TokenResponse:
        """Create signed JWT access token for authenticated user."""
        token = create_access_token(
            data={"sub": user.id, "username": user.username}
        )
        profile = user.profile
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user_id=user.id,
            username=user.username,
            nickname=profile.nickname if profile else user.username,
            avatar_url=profile.avatar_url if profile else None,
        )

    @classmethod
    def submit_verification(
        cls,
        db: Session,
        user_id: str,
        verification_in: VerificationSubmitSchema,
    ) -> VerificationBadge:
        """Submit or update identity/education/career authenticity credentials."""
        # Find existing badge for this badge type or create new
        badge = (
            db.query(VerificationBadge)
            .filter(
                VerificationBadge.user_id == user_id,
                VerificationBadge.badge_type == verification_in.badge_type,
            )
            .first()
        )

        if not badge:
            badge = VerificationBadge(
                user_id=user_id,
                badge_type=verification_in.badge_type,
            )
            db.add(badge)

        # Encrypt sensitive PII with AES-256
        if verification_in.real_name:
            badge.real_name_encrypted = encrypt_field(verification_in.real_name)
        if verification_in.id_card:
            badge.id_card_encrypted = encrypt_field(verification_in.id_card)

        if verification_in.school:
            badge.education_school = verification_in.school
        if verification_in.degree:
            badge.education_degree = verification_in.degree
        if verification_in.company:
            badge.company = verification_in.company
        if verification_in.job_title:
            badge.job_title = verification_in.job_title

        # Set status to PENDING for official review
        badge.status = VerificationStatusEnum.PENDING.value
        db.commit()
        db.refresh(badge)
        return badge

    @classmethod
    def apply_privacy_filters(
        cls,
        viewer_user_id: Optional[str],
        target_profile: UserProfile,
        privacy: Optional[PrivacySetting],
        viewer_lat: Optional[float] = None,
        viewer_lon: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Apply granular privacy protection and compute distance if allowed."""
        is_owner = viewer_user_id is not None and viewer_user_id == target_profile.user_id

        # Defaults
        show_distance = True
        show_location = True

        if privacy and not is_owner:
            if privacy.hide_distance:
                show_distance = False
            if privacy.hide_from_nearby:
                show_distance = False
                show_location = False

        distance_km: Optional[float] = None
        if (
            show_distance
            and viewer_lat is not None
            and viewer_lon is not None
            and target_profile.latitude is not None
            and target_profile.longitude is not None
        ):
            distance_km = cls._calculate_haversine(
                viewer_lat, viewer_lon, target_profile.latitude, target_profile.longitude
            )

        return {
            "nickname": target_profile.nickname,
            "avatar_url": target_profile.avatar_url,
            "bio": target_profile.bio,
            "gender": target_profile.gender,
            "age": target_profile.age,
            "location": target_profile.location if show_location else "已隐藏",
            "voice_card_url": target_profile.voice_card_url,
            "mbti": target_profile.mbti,
            "interest_tags": target_profile.interest_tags or [],
            "distance_km": round(distance_km, 2) if distance_km is not None else None,
        }

    @staticmethod
    def _calculate_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Compute spherical distance in kilometers between two geo-coordinates."""
        r = 6371.0  # Earth radius in kilometers
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(d_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return r * c


# Module-level convenience functions matching architecture symbols
register_user = AuthService.register_user
authenticate_user = AuthService.authenticate_user
submit_verification = AuthService.submit_verification
apply_privacy_filters = AuthService.apply_privacy_filters
