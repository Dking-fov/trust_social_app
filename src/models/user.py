"""User, Profile, and EducationCredential models with verification states and privacy fields."""

import enum
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Date,
    Enum as SAEnum,
    ForeignKey,
    JSON,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class GenderEnum(str, enum.Enum):
    """User gender identity."""
    MALE = "Male"
    FEMALE = "Female"


class DatingPreferenceEnum(str, enum.Enum):
    """Dating preference orientation."""
    MALE = "Male"
    FEMALE = "Female"
    BOTH = "Both"


class VerificationStatusEnum(str, enum.Enum):
    """State machine status for real-name educational verification."""
    UNSUBMITTED = "unsubmitted"
    PENDING_REVIEW = "pending_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


class SchoolTierEnum(str, enum.Enum):
    """Normalized institution classification tier."""
    TIER_985 = "985"
    TIER_211 = "211"
    DOUBLE_FIRST_CLASS = "Double First-Class"
    TOP_OVERSEAS = "Top Overseas"
    REGULAR = "Regular"


class DegreeLevelEnum(str, enum.Enum):
    """Normalized educational degree levels."""
    BACHELOR = "Bachelor"
    MASTER = "Master"
    DOCTORATE = "Doctorate"


class User(Base):
    """Core platform user entity."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    birthdate: Mapped[date] = mapped_column(Date, nullable=False)
    resident_city: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    gender: Mapped[GenderEnum] = mapped_column(SAEnum(GenderEnum), nullable=False)
    dating_preference: Mapped[DatingPreferenceEnum] = mapped_column(
        SAEnum(DatingPreferenceEnum), nullable=False
    )
    interest_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Verification state machine
    verification_status: Mapped[VerificationStatusEnum] = mapped_column(
        SAEnum(VerificationStatusEnum),
        default=VerificationStatusEnum.UNSUBMITTED,
        index=True,
        nullable=False,
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Reputation & Points
    reputation_score: Mapped[float] = mapped_column(Float, default=3.5, nullable=False)
    reputation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    points_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Activity & Timestamps
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    education_credential: Mapped[Optional["EducationCredential"]] = relationship(
        "EducationCredential", back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def age(self) -> int:
        """Calculate user age from birthdate."""
        today = date.today()
        return (
            today.year
            - self.birthdate.year
            - ((today.month, today.day) < (self.birthdate.month, self.birthdate.day))
        )


class EducationCredential(Base):
    """User education verification submission and OCR results."""
    __tablename__ = "education_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )

    # Raw credential identifiers (stored private and encrypted)
    document_file_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    credential_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    edu_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # OCR Extracted Fields
    ocr_student_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ocr_institution_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    school_tier: Mapped[Optional[SchoolTierEnum]] = mapped_column(
        SAEnum(SchoolTierEnum), nullable=True
    )
    degree_level: Mapped[Optional[DegreeLevelEnum]] = mapped_column(
        SAEnum(DegreeLevelEnum), nullable=True
    )
    ocr_confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    requires_manual_audit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="education_credential", lazy="selectin")
