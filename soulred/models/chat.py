"""Chat conversations, messages, and Soul-style intimacy progression models."""

import enum
from sqlalchemy import Column, String, Boolean, Integer, Float, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship

from soulred.database import Base
from soulred.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class MessageTypeEnum(str, enum.Enum):
    """Message payload type."""
    TEXT = "text"
    EMOJI = "emoji"
    IMAGE = "image"
    VOICE = "voice"
    SYSTEM = "system"


class IntimacyLevelEnum(str, enum.Enum):
    """Soul intimacy tree progression tiers."""
    SEED = "初识萌芽"
    BUD = "渐入佳境"
    FLOWER = "无话不谈"
    STAR = "挚友星辰"


class ChatConversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Direct messaging conversation session."""
    __tablename__ = "chat_conversations"

    user_a_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_b_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    last_message_content = Column(String(1000), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    is_stranger_session = Column(Boolean, default=True, nullable=False)

    user_a = relationship("User", foreign_keys=[user_a_id])
    user_b = relationship("User", foreign_keys=[user_b_id])
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.created_at")
    intimacy = relationship("IntimacyRecord", back_populates="conversation", uselist=False, cascade="all, delete-orphan")


class ChatMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Single message entity supporting recall and read receipts."""
    __tablename__ = "chat_messages"

    conversation_id = Column(String(36), ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message_type = Column(String(20), default=MessageTypeEnum.TEXT.value, nullable=False)
    content = Column(String(2000), nullable=False)
    media_url = Column(String(500), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    is_recalled = Column(Boolean, default=False, nullable=False)
    recalled_at = Column(DateTime(timezone=True), nullable=True)

    conversation = relationship("ChatConversation", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])


class IntimacyRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks interaction intimacy experience points and badge levels."""
    __tablename__ = "intimacy_records"

    conversation_id = Column(String(36), ForeignKey("chat_conversations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    user_a_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user_b_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    intimacy_score = Column(Float, default=0.0, nullable=False)
    current_level = Column(String(30), default=IntimacyLevelEnum.SEED.value, nullable=False)
    interaction_days = Column(Integer, default=0, nullable=False)
    word_count_today = Column(Integer, default=0, nullable=False)
    last_interacted_date = Column(String(20), nullable=True)
    unlocked_badges = Column(JSON, default=list, nullable=False)

    conversation = relationship("ChatConversation", back_populates="intimacy")
