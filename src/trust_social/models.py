"""SQLAlchemy ORM models and enumeration definitions for Trust Social platform."""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.trust_social.database import Base


# ============================================================================
# Enumerations
# ============================================================================

class UserRole(str, Enum):
    """User account permissions and system role."""
    ADMIN = "ADMIN"
    USER = "USER"


class VerificationStatus(str, Enum):
    """Educational credential verification status."""
    UNVERIFIED = "UNVERIFIED"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class InstitutionTier(str, Enum):
    """Categorized institution tier for desensitized public exposure."""
    TIER_985 = "985"
    TIER_211 = "211"
    DOUBLE_FIRST_CLASS = "Double First Class"
    OVERSEAS_TOP_100 = "Overseas Top 100"
    REGULAR = "Regular"


class DegreeLevel(str, Enum):
    """Academic degree hierarchy."""
    BACHELOR = "Bachelor"
    MASTER = "Master"
    DOCTOR = "Doctor"
    OTHER = "Other"


class MatchStatus(str, Enum):
    """Status of mutual match connection."""
    ACTIVE = "ACTIVE"
    DISSOLVED = "DISSOLVED"


class DateStatus(str, Enum):
    """Lifecycle state machine for offline date invitations."""
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ReviewStatus(str, Enum):
    """Double-blind review visibility status."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PUBLISHED = "PUBLISHED"


class PointsReason(str, Enum):
    """Audit reason categories for points ledger transactions."""
    EDU_VERIFICATION = "EDU_VERIFICATION"
    DAILY_CHECKIN = "DAILY_CHECKIN"
    HIGH_SCORE_DATE = "HIGH_SCORE_DATE"
    DECK_REFRESH = "DECK_REFRESH"
    CRUSH_DISCOVERY = "CRUSH_DISCOVERY"
    REPORT_BOUNTY = "REPORT_BOUNTY"
    PENALTY = "PENALTY"
    ADMIN_ADJUSTMENT = "ADMIN_ADJUSTMENT"


# ============================================================================
# ORM Models
# ============================================================================

class User(Base):
    """Core user account entity."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole), default=UserRole.USER, nullable=False
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SQLEnum(VerificationStatus), default=VerificationStatus.UNVERIFIED, nullable=False
    )
    points_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bayesian_reputation: Mapped[float] = mapped_column(Float, default=3.5, nullable=False)
    reputation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reputation_sum: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_restricted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    last_login_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Relationships
    credentials: Mapped[List["EducationCredential"]] = relationship(
        "EducationCredential",
        back_populates="user",
        foreign_keys="EducationCredential.user_id",
        cascade="all, delete-orphan",
    )
    candidate_decks: Mapped[List["CandidateDeck"]] = relationship(
        "CandidateDeck", back_populates="user", cascade="all, delete-orphan"
    )
    points_transactions: Mapped[List["PointsLedger"]] = relationship(
        "PointsLedger", back_populates="user", cascade="all, delete-orphan"
    )


class EducationCredential(Base):
    """Encrypted educational credentials submitted for trust verification."""
    __tablename__ = "education_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # AES-256-GCM ciphertext + tag containing certificate ID, raw student info, diploma images
    encrypted_data: Mapped[str] = mapped_column(Text, nullable=False)

    institution_tier: Mapped[Optional[InstitutionTier]] = mapped_column(
        SQLEnum(InstitutionTier), nullable=True
    )
    degree_level: Mapped[Optional[DegreeLevel]] = mapped_column(
        SQLEnum(DegreeLevel), nullable=True
    )
    institution_name_desensitized: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    status: Mapped[VerificationStatus] = mapped_column(
        SQLEnum(VerificationStatus), default=VerificationStatus.PENDING, nullable=False
    )
    audit_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    audited_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    audited_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User", back_populates="credentials", foreign_keys=[user_id]
    )
    auditor: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[audited_by]
    )


class CandidateDeck(Base):
    """Curated daily 10-candidate pool per user."""
    __tablename__ = "candidate_decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    deck_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False, index=True)
    candidate_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    swiped_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    is_exhausted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="candidate_decks")

    __table_args__ = (
        UniqueConstraint("user_id", "deck_date", name="uq_user_daily_deck"),
    )


class MatchAction(Base):
    """Swipe action record (LIKE / PASS) by user against target candidate."""
    __tablename__ = "match_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "LIKE" or "PASS"
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "target_user_id", name="uq_user_target_action"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    target_user: Mapped["User"] = relationship("User", foreign_keys=[target_user_id])


class MatchSession(Base):
    """Mutual match connection unlocking 1v1 chat and date scheduling."""
    __tablename__ = "match_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user1_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user2_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[MatchStatus] = mapped_column(
        SQLEnum(MatchStatus), default=MatchStatus.ACTIVE, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_dissolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dissolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("user1_id", "user2_id", name="uq_match_session_pair"),
    )

    # Relationships
    user1: Mapped["User"] = relationship("User", foreign_keys=[user1_id])
    user2: Mapped["User"] = relationship("User", foreign_keys=[user2_id])
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan"
    )
    dates: Mapped[List["DateInvitation"]] = relationship(
        "DateInvitation", back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    """Individual chat message within a match session."""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("match_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="SENT", nullable=False
    )  # "SENT", "DELIVERED", "READ"
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    session: Mapped["MatchSession"] = relationship("MatchSession", back_populates="messages")
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])
    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_id])


class DateInvitation(Base):
    """Structured offline date invitation with dual verification parameters."""
    __tablename__ = "date_invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("match_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    inviter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invitee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    venue_name: Mapped[str] = mapped_column(String(255), nullable=False)
    venue_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    venue_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    scheduled_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    activity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    status: Mapped[DateStatus] = mapped_column(
        SQLEnum(DateStatus), default=DateStatus.PROPOSED, nullable=False
    )
    totp_secret: Mapped[str] = mapped_column(String(64), nullable=False)
    check_in_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    check_in_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    check_in_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    session: Mapped["MatchSession"] = relationship("MatchSession", back_populates="dates")
    inviter: Mapped["User"] = relationship("User", foreign_keys=[inviter_id])
    invitee: Mapped["User"] = relationship("User", foreign_keys=[invitee_id])
    reviews: Mapped[List["DateReview"]] = relationship(
        "DateReview", back_populates="date_invitation", cascade="all, delete-orphan"
    )


class DateReview(Base):
    """Double-blind review entity created after physical date completion."""
    __tablename__ = "date_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date_invitation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("date_invitations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewed_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[float] = mapped_column(Float, nullable=False)  # 1.0 to 5.0
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)

    status: Mapped[ReviewStatus] = mapped_column(
        SQLEnum(ReviewStatus), default=ReviewStatus.SUBMITTED, nullable=False
    )
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    unlock_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    auto_reveal_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("date_invitation_id", "reviewer_id", name="uq_date_reviewer_once"),
    )

    # Relationships
    date_invitation: Mapped["DateInvitation"] = relationship(
        "DateInvitation", back_populates="reviews"
    )
    reviewer: Mapped["User"] = relationship("User", foreign_keys=[reviewer_id])
    reviewed_user: Mapped["User"] = relationship("User", foreign_keys=[reviewed_user_id])


class PointsLedger(Base):
    """Audit ledger tracking all points earnings and consumptions."""
    __tablename__ = "points_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # positive or negative
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[PointsReason] = mapped_column(SQLEnum(PointsReason), nullable=False)
    reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="points_transactions")


class ReportTicket(Base):
    """User risk report ticket for governance and safety enforcement."""
    __tablename__ = "report_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reporter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reported_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="OPEN", nullable=False
    )  # "OPEN", "RESOLVED", "REJECTED"
    penalty_applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    reporter: Mapped["User"] = relationship("User", foreign_keys=[reporter_id])
    reported_user: Mapped["User"] = relationship("User", foreign_keys=[reported_user_id])
    resolver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[resolved_by])
