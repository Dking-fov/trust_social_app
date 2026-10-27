"""Interest circles, memberships, and multi-tier nested comments."""

import enum
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship

from soulred.database import Base
from soulred.models.base import UUIDPrimaryKeyMixin, TimestampMixin, get_utc_now


class CircleRoleEnum(str, enum.Enum):
    """Membership role in interest circle."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class CircleCategoryEnum(str, enum.Enum):
    """Preset circle thematic categories."""
    ART = "艺术展览"
    HIKING = "户外徒步"
    DATING = "同城交友"
    TREEHOLE = "深夜树洞"
    MUSIC = "民谣音乐"
    LIFESTYLE = "生活方式"


class InterestCircle(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Thematic community circle entity."""
    __tablename__ = "interest_circles"

    name = Column(String(100), unique=True, index=True, nullable=False)
    category = Column(String(50), default=CircleCategoryEnum.LIFESTYLE.value, nullable=False)
    description = Column(String(1000), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    banner_url = Column(String(500), nullable=True)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    member_count = Column(Integer, default=1, nullable=False)
    post_count = Column(Integer, default=0, nullable=False)
    is_official = Column(Boolean, default=False, nullable=False)

    owner = relationship("User", foreign_keys=[owner_id])
    members = relationship("CircleMember", back_populates="circle", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="circle")


class CircleMember(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User membership relationship in a circle."""
    __tablename__ = "circle_members"
    __table_args__ = (
        UniqueConstraint("circle_id", "user_id", name="uq_circle_member_pair"),
    )

    circle_id = Column(String(36), ForeignKey("interest_circles.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), default=CircleRoleEnum.MEMBER.value, nullable=False)
    is_muted = Column(Boolean, default=False, nullable=False)
    joined_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    circle = relationship("InterestCircle", back_populates="members")
    user = relationship("User")


class CircleComment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Multi-tier tree comment supporting post and circle discussions."""
    __tablename__ = "circle_comments"

    post_id = Column(String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=True, index=True)
    circle_id = Column(String(36), ForeignKey("interest_circles.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(String(36), ForeignKey("circle_comments.id", ondelete="CASCADE"), nullable=True, index=True)
    content = Column(String(2000), nullable=False)
    image_url = Column(String(500), nullable=True)
    likes_count = Column(Integer, default=0, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    user = relationship("User")
    post = relationship("Post", back_populates="comments")
    parent = relationship("CircleComment", remote_side="CircleComment.id", back_populates="replies")
    replies = relationship("CircleComment", back_populates="parent", cascade="all, delete-orphan", order_by="CircleComment.created_at")
