"""Pydantic schemas for authentication, profile persona, verification, and privacy."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class UserCreate(BaseModel):
    """Payload for user registration."""
    username: str = Field(..., min_length=3, max_length=50, description="Unique account username")
    password: str = Field(..., min_length=6, max_length=128, description="Account password")
    phone: Optional[str] = Field(None, description="Mobile number for AES encryption")
    email: Optional[str] = Field(None, description="Optional email address")
    nickname: Optional[str] = Field(None, description="Social display nickname")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")
    gender: Optional[str] = Field("secret", description="Gender identity")
    mbti: Optional[str] = Field(None, description="MBTI personality tag")


class UserLogin(BaseModel):
    """Payload for user login."""
    username: str = Field(..., description="Username or mobile number")
    password: str = Field(..., description="Account password")


class TokenResponse(BaseModel):
    """JWT bearer token and authenticated user context."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None


class UserProfileUpdate(BaseModel):
    """Payload for updating user profile persona."""
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[str] = None
    age: Optional[int] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    voice_card_url: Optional[str] = None
    mbti: Optional[str] = None
    interest_tags: Optional[List[str]] = None


class PrivacySettingSchema(BaseModel):
    """Privacy control flags configuration."""
    hide_distance: bool = False
    hide_from_nearby: bool = False
    incognito_contacts: bool = False
    stranger_msg_restricted: bool = True

    model_config = ConfigDict(from_attributes=True)


class VerificationBadgeResponse(BaseModel):
    """Public credential badge representation."""
    badge_type: str
    status: str
    education_school: Optional[str] = None
    education_degree: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    verified_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponse(BaseModel):
    """Comprehensive user profile response."""
    id: str
    user_id: str
    username: Optional[str] = None
    nickname: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    gender: str = "secret"
    age: Optional[int] = None
    birth_date: Optional[str] = None
    location: Optional[str] = None
    voice_card_url: Optional[str] = None
    mbti: Optional[str] = None
    interest_tags: List[str] = []
    badges: List[VerificationBadgeResponse] = []
    privacy: Optional[PrivacySettingSchema] = None

    model_config = ConfigDict(from_attributes=True)


class VerificationSubmitSchema(BaseModel):
    """Payload for submitting authenticity credentials."""
    badge_type: str = Field("real_name", description="'real_name', 'education', or 'career'")
    real_name: Optional[str] = Field(None, description="Real identity name for AES-256 encryption")
    id_card: Optional[str] = Field(None, description="National ID number for AES-256 encryption")
    school: Optional[str] = Field(None, description="University / College name")
    degree: Optional[str] = Field(None, description="Bachelor / Master / PhD")
    company: Optional[str] = Field(None, description="Employer organization")
    job_title: Optional[str] = Field(None, description="Professional title")
