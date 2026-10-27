"""Pydantic request and response schemas ensuring strict serialization, input validation, and privacy desensitization."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.trust_social.models import (
    DateStatus,
    DegreeLevel,
    InstitutionTier,
    PointsReason,
    ReviewStatus,
    UserRole,
    VerificationStatus,
)


# ============================================================================
# Standardized Error Schema
# ============================================================================

class ErrorResponse(BaseModel):
    """Standardized API error response format conforming to domain error protocol."""
    error_code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Authentication Schemas
# ============================================================================

class TokenResponse(BaseModel):
    """JWT authentication token response with user metadata."""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    role: UserRole


class UserCreate(BaseModel):
    """User registration request body."""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(..., min_length=6, max_length=128, description="Plaintext password")
    gender: Optional[str] = Field(None, max_length=20)
    bio: Optional[str] = Field(None, max_length=1000)
    age: Optional[int] = Field(None, ge=18, le=120)
    location: Optional[str] = Field(None, max_length=100)


class UserLogin(BaseModel):
    """User login request body."""
    email: str = Field(..., description="Email address or username")
    password: str = Field(..., description="Plaintext password")


class UserProfileResponse(BaseModel):
    """Full private profile response for the authenticated user."""
    id: int
    username: str
    email: str
    role: UserRole
    verification_status: VerificationStatus
    points_balance: int
    bayesian_reputation: float
    reputation_count: int
    gender: Optional[str] = None
    bio: Optional[str] = None
    age: Optional[int] = None
    location: Optional[str] = None
    is_active: bool
    is_restricted: bool
    institution_tier: Optional[InstitutionTier] = None
    degree_level: Optional[DegreeLevel] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Educational Verification Schemas
# ============================================================================

class EducationVerifyRequest(BaseModel):
    """Educational credential verification submission payload."""
    raw_certificate_data: str = Field(
        ...,
        description="Raw certificate payload or OCR text to be encrypted via AES-256-GCM",
    )
    institution_name: str = Field(..., min_length=2, max_length=255)
    tier: InstitutionTier
    degree: DegreeLevel
    certificate_no: Optional[str] = Field(None, description="Confidential certificate serial")


class EducationVerifyResponse(BaseModel):
    """Response returned upon educational credential submission or review."""
    id: int
    user_id: int
    status: VerificationStatus
    institution_tier: Optional[InstitutionTier] = None
    degree_level: Optional[DegreeLevel] = None
    institution_name_desensitized: Optional[str] = None
    submitted_at: datetime
    audited_at: Optional[datetime] = None
    audit_feedback: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PublicProfileResponse(BaseModel):
    """Public candidate profile strictly hiding all sensitive identity and certificate IDs."""
    id: int
    username: str
    gender: Optional[str] = None
    bio: Optional[str] = None
    age: Optional[int] = None
    location: Optional[str] = None
    verification_status: VerificationStatus
    institution_tier: Optional[InstitutionTier] = None
    degree_level: Optional[DegreeLevel] = None
    bayesian_reputation: float
    reputation_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Candidate Recommendation & Matching Schemas
# ============================================================================

class CandidateCardResponse(BaseModel):
    """Curated candidate card presented in the daily 10-person deck."""
    user_id: int
    username: str
    gender: Optional[str] = None
    bio: Optional[str] = None
    age: Optional[int] = None
    location: Optional[str] = None
    institution_tier: Optional[InstitutionTier] = None
    degree_level: Optional[DegreeLevel] = None
    verification_status: VerificationStatus
    bayesian_reputation: float
    recommendation_score: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class CandidateDeckResponse(BaseModel):
    """Daily candidate deck response with swiping quota status."""
    deck_id: Optional[int] = None
    deck_date: str
    cards: List[CandidateCardResponse]
    is_exhausted: bool = False
    remaining_cards: int = 0
    total_cards: int = 10

    model_config = ConfigDict(from_attributes=True)


class MatchActionRequest(BaseModel):
    """Swipe action submission (LIKE / PASS) on a candidate card."""
    target_user_id: int
    action: str = Field(..., pattern="^(LIKE|PASS)$", description="Must be 'LIKE' or 'PASS'")


class MatchResponse(BaseModel):
    """Result of a swipe action indicating whether mutual match occurred."""
    matched: bool
    session_id: Optional[int] = None
    target_user_id: int
    message: str


# ============================================================================
# Real-Time 1v1 Chat Schemas
# ============================================================================

class ChatMessageCreate(BaseModel):
    """Chat message submission payload."""
    content: str = Field(..., min_length=1, max_length=4000)


class ChatMessageResponse(BaseModel):
    """Chat message delivery payload with SENT / DELIVERED status tracking."""
    id: int
    session_id: int
    sender_id: int
    recipient_id: int
    content: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Offline Date & Dual Verification Schemas
# ============================================================================

class DateInvitationCreate(BaseModel):
    """Offline date invitation request payload."""
    invitee_id: int
    venue_name: str = Field(..., min_length=2, max_length=255)
    venue_latitude: float = Field(..., ge=-90.0, le=90.0)
    venue_longitude: float = Field(..., ge=-180.0, le=180.0)
    scheduled_time: datetime
    activity_type: Optional[str] = Field(None, max_length=100)


class DateInvitationResponse(BaseModel):
    """Offline date invitation response."""
    id: int
    session_id: int
    inviter_id: int
    invitee_id: int
    venue_name: str
    venue_latitude: float
    venue_longitude: float
    scheduled_time: datetime
    activity_type: Optional[str] = None
    status: DateStatus
    created_at: datetime
    check_in_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DateCheckInRequest(BaseModel):
    """Dual verification check-in payload (60s dynamic TOTP token + GPS coordinates)."""
    date_id: int
    totp_token: str = Field(..., min_length=6, max_length=8)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class DateCheckInResponse(BaseModel):
    """Result of offline date dual verification check-in."""
    success: bool
    date_id: int
    status: DateStatus
    distance_meters: float
    message: str


# ============================================================================
# Double-Blind Review Schemas
# ============================================================================

class DateReviewCreate(BaseModel):
    """Double-blind review submission payload."""
    date_id: int
    rating: float = Field(..., ge=1.0, le=5.0, description="Rating between 1.0 and 5.0")
    content: str = Field(..., min_length=5, max_length=2000)
    tags: Optional[List[str]] = Field(default_factory=list)


class DateReviewResponse(BaseModel):
    """Review visibility response, masking content if still in double-blind period."""
    id: int
    date_id: int
    reviewer_id: int
    reviewed_user_id: int
    rating: Optional[float] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    status: ReviewStatus
    is_published: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Points Economy Schemas
# ============================================================================

class PointsBalanceResponse(BaseModel):
    """User points balance response."""
    user_id: int
    points_balance: int


class PointsTransactionResponse(BaseModel):
    """Audit ledger entry for points transactions."""
    id: int
    amount: int
    balance_after: int
    reason: PointsReason
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Risk Control & Reporting Schemas
# ============================================================================

class ReportCreate(BaseModel):
    """User violation report submission payload."""
    reported_user_id: int
    reason: str = Field(..., min_length=3, max_length=255)
    evidence: Optional[str] = None


class ReportResponse(BaseModel):
    """Report ticket response."""
    id: int
    reporter_id: int
    reported_user_id: int
    reason: str
    status: str
    penalty_applied: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
