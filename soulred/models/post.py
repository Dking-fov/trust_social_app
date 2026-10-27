"""Post, media image metadata, like interaction, and draft persistence models."""

import enum
from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship

from soulred.database import Base
from soulred.models.base import UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin


class AspectRatioEnum(str, enum.Enum):
    """Aspect ratio presets for Xiaohongshu waterfall cards."""
    RATIO_1_1 = "1:1"
    RATIO_3_4 = "3:4"
    RATIO_4_3 = "4:3"


class PostStatusEnum(str, enum.Enum):
    """Lifecycle status of a post note."""
    DRAFT = "draft"
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"


class MoodTagEnum(str, enum.Enum):
    """Preset emotional and social status badges."""
    HEALING = "治愈中"
    CHATTING = "求聊天"
    DAYDREAMING = "发呆"
    HAPPY = "开心"
    LONELY = "孤单"
    EXCITED = "兴奋"


class Post(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Xiaohongshu-style rich note dynamic post."""
    __tablename__ = "posts"

    author_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(100), nullable=False)
    content = Column(String(2000), nullable=False)
    mood_tag = Column(String(50), nullable=True)
    topics = Column(JSON, default=list, nullable=False)
    channel = Column(String(30), default="recommend", index=True, nullable=False)
    status = Column(String(20), default=PostStatusEnum.PUBLISHED.value, index=True, nullable=False)
    location = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    likes_count = Column(Integer, default=0, nullable=False)
    comments_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)
    is_hot = Column(Boolean, default=False, nullable=False)
    circle_id = Column(String(36), ForeignKey("interest_circles.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    author = relationship("User", back_populates="posts")
    images = relationship("PostImage", back_populates="post", order_by="PostImage.order_index", cascade="all, delete-orphan")
    likes = relationship("PostLike", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("CircleComment", back_populates="post", cascade="all, delete-orphan")
    circle = relationship("InterestCircle", back_populates="posts")


class PostImage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Post image attachment with aspect ratio metadata for waterfall layout."""
    __tablename__ = "post_images"

    post_id = Column(String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    image_url = Column(String(500), nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    aspect_ratio = Column(String(20), default=AspectRatioEnum.RATIO_3_4.value, nullable=False)
    width = Column(Integer, default=1080, nullable=False)
    height = Column(Integer, default=1440, nullable=False)
    blurhash = Column(String(100), nullable=True)

    post = relationship("Post", back_populates="images")


class PostLike(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Note like interaction records."""
    __tablename__ = "post_likes"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_post_like_user"),
    )

    post_id = Column(String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    post = relationship("Post", back_populates="likes")
    user = relationship("User", back_populates="likes")


class PostDraft(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Local draft auto-save model."""
    __tablename__ = "post_drafts"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(100), nullable=True)
    content = Column(String(2000), nullable=True)
    mood_tag = Column(String(50), nullable=True)
    topics = Column(JSON, default=list, nullable=False)
    image_urls = Column(JSON, default=list, nullable=False)

    user = relationship("User", back_populates="drafts")
