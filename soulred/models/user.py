"""User identity, persona profile, verification badges, and privacy models."""

import enum
from sqlalchemy import Column, String, Boolean, Integer, Float, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship

from soulred.database import Base
from soulred.models.base import UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin


class GenderEnum(str, enum.Enum):
    """User gender identity options."""
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    SECRET = "secret"


class VerificationStatusEnum(str, enum.Enum):
    """Real-name / Education / Career credential verification status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class VerificationTypeEnum(str, enum.Enum):
    """Credential verification badge types."""
    REAL_NAME = "real_name"
    EDUCATION = "education"
    CAREER = "career"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Core user account entity."""
    __tablename__ = "users"

    username = Column(String(50), unique=True, index=True, nullable=False)
    phone_encrypted = Column(String(255), nullable=True, index=True)
    email = Column(String(100), nullable=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    privacy_setting = relationship("PrivacySetting", back_populates="user", uselist=False, cascade="all, delete-orphan")
    verification_badges = relationship("VerificationBadge", back_populates="user", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    drafts = relationship("PostDraft", back_populates="user", cascade="all, delete-orphan")
    likes = relationship("PostLike", back_populates="user", cascade="all, delete-orphan")
    quiz_result = relationship("PersonalityQuizResult", back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Public social profile, 3D avatar, voice card, and persona tags."""
    __tablename__ = "user_profiles"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    nickname = Column(String(50), nullable=False, default="SoulRed Explorer")
    avatar_url = Column(String(500), nullable=True)
    bio = Column(String(500), nullable=True)
    gender = Column(String(20), default=GenderEnum.SECRET.value, nullable=False)
    birth_date = Column(String(20), nullable=True)
    age = Column(Integer, nullable=True)
    location = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    voice_card_url = Column(String(500), nullable=True)
    mbti = Column(String(10), nullable=True)
    interest_tags = Column(JSON, default=list, nullable=False)

    # Relationship back to User
    user = relationship("User", back_populates="profile")


class VerificationBadge(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """QingTeng-style authenticity verification badge record."""
    __tablename__ = "verification_badges"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    badge_type = Column(String(30), default=VerificationTypeEnum.REAL_NAME.value, nullable=False)
    real_name_encrypted = Column(String(255), nullable=True)
    id_card_encrypted = Column(String(255), nullable=True)
    education_school = Column(String(100), nullable=True)
    education_degree = Column(String(50), nullable=True)
    company = Column(String(100), nullable=True)
    job_title = Column(String(100), nullable=True)
    status = Column(String(20), default=VerificationStatusEnum.PENDING.value, nullable=False)
    review_notes = Column(String(255), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="verification_badges")


class PrivacySetting(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Granular privacy and anti-harassment configurations."""
    __tablename__ = "privacy_settings"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    hide_distance = Column(Boolean, default=False, nullable=False)
    hide_from_nearby = Column(Boolean, default=False, nullable=False)
    incognito_contacts = Column(Boolean, default=False, nullable=False)
    stranger_msg_restricted = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="privacy_setting")
