"""Offline date workflow entities: invitations, POI locations, check-in records, and double-blind reviews."""

import enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    JSON,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class DateStatusEnum(str, enum.Enum):
    """Lifecycle states of an offline date."""
    PENDING_ACCEPTANCE = "pending_acceptance"
    CONFIRMED_PENDING_ARRIVAL = "confirmed_pending_arrival"
    COMPLETED = "completed"
    CANCELLED_EXCUSED = "cancelled_excused"
    NO_SHOW = "no_show"
    EXPIRED = "expired"


class CheckInMethodEnum(str, enum.Enum):
    """Supported verification methods for date attendance."""
    DYNAMIC_QR = "dynamic_qr"
    GPS_GEOFENCE = "gps_geofence"


class ReviewStatusEnum(str, enum.Enum):
    """Visibility state of mutual behavioral reviews."""
    SUBMITTED_BLIND = "submitted_blind"
    PUBLISHED = "published"
    COLLUSION_FLAGGED = "collusion_flagged"


class DateInvitation(Base):
    """Structured offline date invitation between matched users."""
    __tablename__ = "date_invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    initiator_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Activity & POI Venue
    activity_topic: Mapped[str] = mapped_column(String(100), nullable=False)
    scheduled_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    venue_name: Mapped[str] = mapped_column(String(200), nullable=False)
    venue_address: Mapped[str] = mapped_column(String(300), nullable=False)
    venue_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    venue_longitude: Mapped[float] = mapped_column(Float, nullable=False)

    # State Machine
    status: Mapped[DateStatusEnum] = mapped_column(
        SAEnum(DateStatusEnum),
        default=DateStatusEnum.PENDING_ACCEPTANCE,
        index=True,
        nullable=False,
    )
    initiator_checked_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recipient_checked_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Cancellation & Penalties
    cancelled_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    no_show_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Dynamic QR TOTP Secret
    totp_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    check_ins: Mapped[list["DateCheckIn"]] = relationship(
        "DateCheckIn", back_populates="date_invitation", cascade="all, delete-orphan", lazy="selectin"
    )
    reviews: Mapped[list["DateReview"]] = relationship(
        "DateReview", back_populates="date_invitation", cascade="all, delete-orphan", lazy="selectin"
    )


class DateCheckIn(Base):
    """Arrival verification log for a date participant."""
    __tablename__ = "date_checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date_invitation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("date_invitations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    method: Mapped[CheckInMethodEnum] = mapped_column(
        SAEnum(CheckInMethodEnum), nullable=False
    )
    verified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    date_invitation: Mapped["DateInvitation"] = relationship(
        "DateInvitation", back_populates="check_ins", lazy="selectin"
    )


class DateReview(Base):
    """Double-blind behavioral rating submitted post-date."""
    __tablename__ = "date_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date_invitation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("date_invitations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reviewer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reviewee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    rating: Mapped[float] = mapped_column(Float, nullable=False)
    behavioral_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[ReviewStatusEnum] = mapped_column(
        SAEnum(ReviewStatusEnum),
        default=ReviewStatusEnum.SUBMITTED_BLIND,
        index=True,
        nullable=False,
    )
    is_collusion: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    date_invitation: Mapped["DateInvitation"] = relationship(
        "DateInvitation", back_populates="reviews", lazy="selectin"
    )
