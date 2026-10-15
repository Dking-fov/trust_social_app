"""Real-time messaging models, conversation metadata, and 7-day circuit breaker status tracking."""

import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class ConversationStatusEnum(str, enum.Enum):
    """Conversation activity lifecycle statuses."""
    ACTIVE = "active"
    ARCHIVED_INACTIVE = "archived_inactive"


class MessageTypeEnum(str, enum.Enum):
    """Supported 1v1 message payload types."""
    TEXT = "text"
    IMAGE = "image"
    EMOJI = "emoji"
    DATE_INVITE = "date_invite"


class Conversation(Base):
    """1v1 chat session bound to a mutual match."""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("matches.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    user_a_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_b_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[ConversationStatusEnum] = mapped_column(
        SAEnum(ConversationStatusEnum),
        default=ConversationStatusEnum.ACTIVE,
        index=True,
        nullable=False,
    )
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="conversation", cascade="all, delete-orphan", lazy="selectin"
    )


class ChatMessage(Base):
    """Individual 1v1 instant message."""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sender_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    message_type: Mapped[MessageTypeEnum] = mapped_column(
        SAEnum(MessageTypeEnum), default=MessageTypeEnum.TEXT, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages", lazy="selectin")
