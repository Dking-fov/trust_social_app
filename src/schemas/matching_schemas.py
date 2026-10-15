"""Schemas for candidate feed cards, swipe actions, mutual match alerts, and pack refresh."""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from src.models.matching import SwipeTypeEnum, MatchStatusEnum
from src.schemas.user_schemas import UserPublicProfileResponse


class CandidateCardDTO(UserPublicProfileResponse):
    """Candidate card displayed in recommendation feed."""
    ranking_score: Optional[float] = None


class DailyDeckResponse(BaseModel):
    """Daily recommendation card deck payload."""
    deck_date: date
    remaining_cards: int
    refreshed_count: int
    seconds_until_reset: int
    candidates: List[CandidateCardDTO]


class SwipeRequest(BaseModel):
    """Candidate swipe action request."""
    target_user_id: int
    action: SwipeTypeEnum


class SwipeResultResponse(BaseModel):
    """Outcome of swipe operation."""
    success: bool
    is_match: bool
    remaining_cards: int
    match_id: Optional[int] = None
    conversation_id: Optional[int] = None
    message: str = "Swipe recorded successfully."


class MatchDetailResponse(BaseModel):
    """Detailed mutual match record with partner profile."""
    match_id: int
    partner: UserPublicProfileResponse
    conversation_id: int
    status: MatchStatusEnum
    matched_at: datetime


class TargetedSearchRequest(BaseModel):
    """Search request filtered by city and top reputation percentile."""
    city: Optional[str] = None
    top_percentile: float = Field(default=0.10, ge=0.01, le=1.0)


class CrushApplicationRequest(BaseModel):
    """Direct application sent to a high-reputation candidate."""
    target_user_id: int
    intro_note: str = Field(min_length=1, max_length=200)


class CrushApplicationResponse(BaseModel):
    """Direct application dispatch confirmation."""
    success: bool
    target_user_id: int
    message: str = "Crush application delivered to recipient priority inbox."
