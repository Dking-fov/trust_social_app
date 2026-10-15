"""Schemas for 1v1 instant messaging, WebSocket payloads, and conversation status."""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field

from src.models.chat import MessageTypeEnum, ConversationStatusEnum
from src.schemas.user_schemas import UserPublicProfileResponse


class ChatMessageCreateRequest(BaseModel):
    """Payload to send a new chat message."""
    message_type: MessageTypeEnum = Field(default=MessageTypeEnum.TEXT)
    content: str = Field(min_length=1, max_length=2000)


class ChatMessageResponse(BaseModel):
    """Chat message delivery representation."""
    id: int
    conversation_id: int
    sender_id: int
    message_type: MessageTypeEnum
    content: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    """Conversation summary with partner profile and unread statistics."""
    id: int
    match_id: int
    partner: UserPublicProfileResponse
    status: ConversationStatusEnum
    message_count: int
    last_message: Optional[ChatMessageResponse] = None
    unread_count: int = 0
    created_at: datetime
    updated_at: datetime


class WebSocketEventPayload(BaseModel):
    """Real-time event frame dispatched over WebSocket connections."""
    event: str  # e.g. "new_message", "match_success", "date_update"
    data: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
