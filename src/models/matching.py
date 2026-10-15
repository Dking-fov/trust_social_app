"""Models for daily candidate quota decks, individual swipe tracking, and mutual matches."""

import enum
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    Date,
    Enum as SAEnum,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class SwipeTypeEnum(str, enum.Enum):
    """User swipe interaction types."""
    LIKE = "like"
    SKIP = "skip"


class MatchStatusEnum(str, enum.Enum):
    """Mutual match lifecycle statuses."""
    ACTIVE = "active"
    DISSOLVED = "dissolved"


class CandidateDeck(Base):
    """Daily curated 10-candidate quota card deck per user."""
    __tablename__ = "candidate_decks"
    __table_args__ = (
        UniqueConstraint("user_id", "deck_date", name="uq_user_deck_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    deck_date: Mapped[date] = mapped_column(Date, default=date.today, index=True, nullable=False)
    candidate_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    remaining_cards: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    refreshed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class SwipeAction(Base):
    """Immutable record of a single swipe action."""
    __tablename__ = "swipe_actions"
    __table_args__ = (
        UniqueConstraint("user_id", "target_user_id", name="uq_user_target_swipe"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    action: Mapped[SwipeTypeEnum] = mapped_column(SAEnum(SwipeTypeEnum), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Match(Base):
    """Mutual double-opt-in match pairing."""
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("user_a_id", "user_b_id", name="uq_match_user_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_a_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_b_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[MatchStatusEnum] = mapped_column(
        SAEnum(MatchStatusEnum), default=MatchStatusEnum.ACTIVE, index=True, nullable=False
    )
    matched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    dissolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    dissolution_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
