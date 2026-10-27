"""Personality quiz, QingTeng daily recommendation cards, and crush match models."""

import enum
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship

from soulred.database import Base
from soulred.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class CrushStatusEnum(str, enum.Enum):
    """Crush match interaction status."""
    PENDING = "pending"
    MUTUAL = "mutual"
    SKIPPED = "skipped"


class PersonalityQuizResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Soul-style personality / values star-chart test result."""
    __tablename__ = "personality_quiz_results"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    mbti = Column(String(10), nullable=True)
    personality_title = Column(String(50), nullable=True)
    traits_vector = Column(JSON, default=list, nullable=False)
    dimension_scores = Column(JSON, default=dict, nullable=False)
    answers = Column(JSON, default=dict, nullable=False)

    user = relationship("User", back_populates="quiz_result")


class DailyRecommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """QingTeng-style curated daily cards assigned to users."""
    __tablename__ = "daily_recommendations"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date_str = Column(String(20), nullable=False, index=True)
    match_score = Column(Float, default=0.0, nullable=False)
    reasons = Column(JSON, default=list, nullable=False)
    is_crushed = Column(Boolean, default=False, nullable=False)
    is_skipped = Column(Boolean, default=False, nullable=False)

    user = relationship("User", foreign_keys=[user_id])
    target_user = relationship("User", foreign_keys=[target_user_id])


class CrushMatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Bidirectional crush and matching record."""
    __tablename__ = "crush_matches"
    __table_args__ = (
        UniqueConstraint("user_id", "target_user_id", name="uq_crush_match_pair"),
    )

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), default=CrushStatusEnum.PENDING.value, nullable=False)
    mutual_at = Column(DateTime(timezone=True), nullable=True)
    conversation_id = Column(String(36), nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    target_user = relationship("User", foreign_keys=[target_user_id])
