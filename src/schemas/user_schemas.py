"""Request and response schemas for user onboarding, auth, and credential verification."""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator

from src.models.user import (
    GenderEnum,
    DatingPreferenceEnum,
    VerificationStatusEnum,
    SchoolTierEnum,
    DegreeLevelEnum,
)
from src.core.exceptions import InvalidTagsCountException, UnderageOrOverageException


class UserRegisterRequest(BaseModel):
    """User profile registration payload."""
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    nickname: str = Field(min_length=1, max_length=100)
    birthdate: date
    resident_city: str = Field(min_length=1, max_length=100)
    gender: GenderEnum
    dating_preference: DatingPreferenceEnum
    interest_tags: List[str]

    @field_validator("interest_tags")
    @classmethod
    def validate_tags(cls, tags: List[str]) -> List[str]:
        if not (3 <= len(tags) <= 8):
            raise InvalidTagsCountException()
        return tags

    @field_validator("birthdate")
    @classmethod
    def validate_age_range(cls, birthdate: date) -> date:
        today = date.today()
        age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
        if age < 20 or age > 35:
            raise UnderageOrOverageException()
        return birthdate


class UserLoginRequest(BaseModel):
    """User authentication credentials."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT bearer token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: int


class OCRParseResultDTO(BaseModel):
    """Parsed educational credential information."""
    student_name: Optional[str] = None
    institution_name: Optional[str] = None
    school_tier: Optional[SchoolTierEnum] = None
    degree_level: Optional[DegreeLevelEnum] = None
    confidence: float = 1.0
    requires_manual_audit: bool = False


class EducationSubmissionRequest(BaseModel):
    """Education credential submission payload."""
    certificate_base64: Optional[str] = Field(default=None, description="Base64 encoded diploma/certificate file")
    filename: Optional[str] = Field(default="certificate.jpg", description="Original file name")
    credential_code: Optional[str] = Field(default=None, description="Official credential verification code")
    edu_email: Optional[EmailStr] = Field(default=None, description="Official .edu university email")
    student_name: Optional[str] = None
    institution_name: Optional[str] = None


class VerificationAuditRequest(BaseModel):
    """Admin compliance audit decision."""
    status: VerificationStatusEnum
    rejection_reason: Optional[str] = None
    school_tier: Optional[SchoolTierEnum] = None
    degree_level: Optional[DegreeLevelEnum] = None


class UserPublicProfileResponse(BaseModel):
    """Desensitized public user profile card (US-004 privacy-safe)."""
    id: int
    nickname: str
    age: int
    resident_city: str
    gender: GenderEnum
    interest_tags: List[str]
    reputation_score: float
    reputation_count: int
    school_tier: Optional[SchoolTierEnum] = None
    degree_level: Optional[DegreeLevelEnum] = None
    is_verified: bool = False

    model_config = {"from_attributes": True}


class UserProfilePrivateResponse(BaseModel):
    """Full authenticated profile for the user themself."""
    id: int
    email: str
    nickname: str
    age: int
    birthdate: date
    resident_city: str
    gender: GenderEnum
    dating_preference: DatingPreferenceEnum
    interest_tags: List[str]
    verification_status: VerificationStatusEnum
    reputation_score: float
    reputation_count: int
    points_balance: int
    is_verified: bool = False
    school_tier: Optional[SchoolTierEnum] = None
    degree_level: Optional[DegreeLevelEnum] = None
    created_at: datetime

    model_config = {"from_attributes": True}
