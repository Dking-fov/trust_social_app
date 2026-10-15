"""Schemas for date invitation proposals, POI venue selection, check-in proofs (QR/GPS), and reviews."""

from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

from src.models.dating import DateStatusEnum, CheckInMethodEnum, ReviewStatusEnum


class DateInviteCreateRequest(BaseModel):
    """Payload to initiate a structured offline date."""
    conversation_id: int
    activity_topic: str = Field(min_length=1, max_length=100)
    scheduled_datetime: datetime
    venue_name: str = Field(min_length=1, max_length=200)
    venue_address: str = Field(min_length=1, max_length=300)
    venue_latitude: float = Field(ge=-90.0, le=90.0)
    venue_longitude: float = Field(ge=-180.0, le=180.0)

    @field_validator("scheduled_datetime")
    @classmethod
    def validate_meeting_time(cls, dt: datetime) -> datetime:
        now = datetime.utcnow()
        min_time = now + timedelta(hours=1, minutes=50)  # leeway around 2h
        max_time = now + timedelta(days=14, hours=1)
        if dt < min_time:
            raise ValueError("Meeting datetime must be scheduled at least 2 hours in advance.")
        if dt > max_time:
            raise ValueError("Meeting datetime cannot be scheduled beyond 14 days in advance.")
        return dt


class DateInviteResponse(BaseModel):
    """Structured date proposal entity details."""
    id: int
    conversation_id: int
    initiator_id: int
    recipient_id: int
    activity_topic: str
    scheduled_datetime: datetime
    venue_name: str
    venue_address: str
    venue_latitude: float
    venue_longitude: float
    status: DateStatusEnum
    initiator_checked_in: bool
    recipient_checked_in: bool
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DateRespondRequest(BaseModel):
    """Response to pending date proposal."""
    action: str = Field(description="'accept' or 'decline'")


class DateCancelRequest(BaseModel):
    """Date cancellation request."""
    reason: Optional[str] = Field(default=None, max_length=255)


class DateCheckInQRGenerateResponse(BaseModel):
    """Dynamic TOTP QR code for in-person check-in."""
    date_id: int
    qr_token: str
    valid_seconds: int = 60
    expires_at: datetime


class DateCheckInQRScanRequest(BaseModel):
    """QR code check-in verification request."""
    qr_token: str


class DateCheckInGPSRequest(BaseModel):
    """GPS geofence check-in verification request."""
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    is_mock: bool = Field(default=False, description="Mock location telemetry flag")


class DateReviewSubmitRequest(BaseModel):
    """Double-blind review submission."""
    rating: float = Field(ge=1.0, le=5.0)
    behavioral_tags: List[str] = Field(min_length=1)
    comment: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("rating")
    @classmethod
    def validate_half_star_increment(cls, v: float) -> float:
        if round(v * 2) != v * 2:
            raise ValueError("Rating must be in 0.5 increments between 1.0 and 5.0.")
        return v


class DateReviewResponse(BaseModel):
    """Review feedback response (supports blind hiding)."""
    id: int
    date_invitation_id: int
    reviewer_id: int
    reviewee_id: int
    rating: Optional[float] = None
    behavioral_tags: Optional[List[str]] = None
    comment: Optional[str] = None
    status: ReviewStatusEnum
    is_revealed: bool = False
    created_at: datetime
    published_at: Optional[datetime] = None
