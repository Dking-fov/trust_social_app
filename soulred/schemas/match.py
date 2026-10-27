"""Pydantic schemas for personality quiz, Soul radar, daily cards, and crush actions."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class QuizSubmitSchema(BaseModel):
    """Payload for submitting personality & values test answers."""
    answers: Dict[str, Any] = Field(..., description="Map of question IDs to selected answers")
    mbti: Optional[str] = Field(None, description="Optional pre-existing MBTI type")


class QuizResultResponse(BaseModel):
    """Output personality star-chart and multidimensional trait vectors."""
    mbti: Optional[str] = None
    personality_title: str
    traits_vector: List[float]
    dimension_scores: Dict[str, float] = Field(default_factory=dict)
    summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SoulRadarMatchCard(BaseModel):
    """High-match (>80%) soul radar candidate card."""
    user_id: str
    nickname: str
    avatar_url: Optional[str] = None
    mbti: Optional[str] = None
    match_score: float
    common_tags: List[str] = Field(default_factory=list)
    distance_km: Optional[float] = None
    voice_card_url: Optional[str] = None
    personality_title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DailyCardResponse(BaseModel):
    """QingTeng-style daily curated recommendation card."""
    card_id: str
    target_user_id: str
    nickname: str
    avatar_url: Optional[str] = None
    age: Optional[int] = None
    mbti: Optional[str] = None
    job_or_school: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    match_score: float
    match_reasons: List[str] = Field(default_factory=list)
    photo_urls: List[str] = Field(default_factory=list)
    voice_card_url: Optional[str] = None
    date_str: str

    model_config = ConfigDict(from_attributes=True)


class CrushActionRequest(BaseModel):
    """Payload for interacting with daily cards or radar matches."""
    target_user_id: str = Field(..., description="Target user identifier")
    action: str = Field(..., description="Action choice: 'crush' or 'skip'")


class CrushActionResponse(BaseModel):
    """Outcome of crush action including mutual match detection."""
    user_id: str
    target_user_id: str
    status: str
    is_mutual: bool
    conversation_id: Optional[str] = None
    message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
