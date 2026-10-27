"""Pydantic schemas for instant messaging, icebreakers, intimacy progression, and recalls."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class MessageSendSchema(BaseModel):
    """Payload for sending a chat message over HTTP or WebSocket."""
    receiver_id: str = Field(..., description="Recipient user UUID")
    content: str = Field(..., min_length=1, max_length=2000, description="Message text or caption")
    message_type: str = Field("text", description="'text', 'emoji', 'image', or 'voice'")
    media_url: Optional[str] = Field(None, description="Optional media asset URL")


class MessageResponse(BaseModel):
    """Normalized chat message response."""
    id: str
    conversation_id: str
    sender_id: str
    receiver_id: str
    message_type: str = "text"
    content: str
    media_url: Optional[str] = None
    is_read: bool = False
    is_recalled: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationSummaryResponse(BaseModel):
    """Overview item in direct messaging inbox."""
    conversation_id: str
    peer_user_id: str
    peer_nickname: str
    peer_avatar_url: Optional[str] = None
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: int = 0
    is_stranger_session: bool = True
    intimacy_level: str = "初识萌芽"
    intimacy_score: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class IcebreakerResponse(BaseModel):
    """Dynamic conversation starter recommendations."""
    suggestions: List[str]
    common_topics: List[str]
    common_mbti: Optional[str] = None


class IntimacyStatusResponse(BaseModel):
    """Soul intimacy tree level, XP progress, and perks."""
    conversation_id: str
    intimacy_score: float
    current_level: str
    next_level_xp: float
    interaction_days: int
    unlocked_perks: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MessageRecallRequest(BaseModel):
    """Payload to recall a sent message within 2 minutes."""
    message_id: str
