"""User profile, persona, and privacy settings REST endpoints."""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from soulred.api.deps import (
    get_db_session,
    get_current_active_user,
    get_optional_current_user,
)
from soulred.api.v1.auth import build_user_profile_response
from soulred.models.user import User, UserProfile, PrivacySetting
from soulred.schemas.user import (
    UserProfileResponse,
    UserProfileUpdate,
    PrivacySettingSchema,
)
from soulred.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile and privacy configuration",
)
def get_my_profile(
    current_user: User = Depends(get_current_active_user),
) -> UserProfileResponse:
    """Retrieve full personal profile and settings for the authenticated user."""
    return build_user_profile_response(current_user)


@router.put(
    "/me",
    response_model=UserProfileResponse,
    summary="Update current user persona profile",
)
def update_profile(
    profile_in: UserProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> UserProfileResponse:
    """Update avatar, bio, MBTI, interest tags, or location for the authenticated user."""
    profile = current_user.profile
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)

    update_data = profile_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(profile, field, val)

    db.commit()
    db.refresh(profile)
    db.refresh(current_user)
    return build_user_profile_response(current_user)


@router.put(
    "/privacy",
    response_model=PrivacySettingSchema,
    summary="Update granular privacy flags",
)
def update_privacy_settings(
    privacy_in: PrivacySettingSchema,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> PrivacySettingSchema:
    """Toggle hide distance, hide from nearby, and incognito mode flags."""
    privacy = current_user.privacy_setting
    if not privacy:
        privacy = PrivacySetting(user_id=current_user.id)
        db.add(privacy)

    privacy.hide_distance = privacy_in.hide_distance
    privacy.hide_from_nearby = privacy_in.hide_from_nearby
    privacy.incognito_contacts = privacy_in.incognito_contacts
    privacy.stranger_msg_restricted = privacy_in.stranger_msg_restricted

    db.commit()
    db.refresh(privacy)
    return PrivacySettingSchema.model_validate(privacy)


@router.get(
    "/{user_id}/persona",
    summary="Get target user's public persona with privacy filters applied",
)
def get_user_persona(
    user_id: str,
    viewer_lat: Optional[float] = Query(None, description="Viewer latitude for distance computation"),
    viewer_lon: Optional[float] = Query(None, description="Viewer longitude for distance computation"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    """Retrieve public social profile of another user with distance/location privacy masks."""
    target_user = (
        db.query(User)
        .filter(User.id == user_id, User.is_deleted == False)
        .first()
    )
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    profile = target_user.profile
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not initialized",
        )

    viewer_id = current_user.id if current_user else None
    filtered_data = AuthService.apply_privacy_filters(
        viewer_user_id=viewer_id,
        target_profile=profile,
        privacy=target_user.privacy_setting,
        viewer_lat=viewer_lat,
        viewer_lon=viewer_lon,
    )

    filtered_data["user_id"] = target_user.id
    filtered_data["badges"] = [
        {
            "badge_type": b.badge_type,
            "status": b.status,
            "education_school": b.education_school,
            "company": b.company,
            "job_title": b.job_title,
        }
        for b in (target_user.verification_badges or [])
        if b.status == "approved"
    ]
    return filtered_data
