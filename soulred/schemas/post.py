"""Pydantic schemas for posts, waterfall cards, drafts, and like interactions."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class PostImageSchema(BaseModel):
    """Image attachment metadata including layout aspect ratio."""
    image_url: str
    order_index: int = 0
    aspect_ratio: str = "3:4"
    width: int = 1080
    height: int = 1440
    blurhash: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PostCreate(BaseModel):
    """Payload for publishing a note post."""
    title: str = Field(..., min_length=1, max_length=100, description="Post title headline")
    content: str = Field(..., min_length=1, max_length=2000, description="Post body text")
    mood_tag: Optional[str] = Field(None, description="Emotional tag (e.g. 治愈中, 求聊天)")
    topics: List[str] = Field(default_factory=list, description="Associated social topic tags")
    images: List[PostImageSchema] = Field(default_factory=list, description="Up to 9 uploaded images")
    channel: Optional[str] = Field("recommend", description="Target channel ('recommend', 'nearby', 'following')")
    location: Optional[str] = Field(None, description="Geographic location name")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    circle_id: Optional[str] = None


class PostWaterfallCard(BaseModel):
    """Xiaohongshu dual-column waterfall card response."""
    id: str
    title: str
    content_summary: str
    cover_image_url: str
    aspect_ratio: str = "3:4"
    card_height: Optional[int] = None
    skeleton_color: Optional[str] = "#f2f3f5"
    author_id: str
    author_nickname: str
    author_avatar_url: Optional[str] = None
    likes_count: int = 0
    is_liked: bool = False
    mood_tag: Optional[str] = None
    topics: List[str] = []
    image_count: int = 1
    channel: str = "recommend"
    distance_km: Optional[float] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PostAuthorInfo(BaseModel):
    """Embedded author summary in post details."""
    id: str
    nickname: str
    avatar_url: Optional[str] = None
    mbti: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PostDetailResponse(BaseModel):
    """Full immersive post details response."""
    id: str
    title: str
    content: str
    mood_tag: Optional[str] = None
    topics: List[str] = []
    channel: str
    location: Optional[str] = None
    likes_count: int = 0
    comments_count: int = 0
    view_count: int = 0
    is_liked: bool = False
    author: PostAuthorInfo
    images: List[PostImageSchema] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PostDraftSave(BaseModel):
    """Payload for auto-saving local drafts."""
    title: Optional[str] = None
    content: Optional[str] = None
    mood_tag: Optional[str] = None
    topics: List[str] = []
    image_urls: List[str] = []


class PostLikeToggleResponse(BaseModel):
    """Response returned upon clicking the like heart button."""
    post_id: str
    is_liked: bool
    likes_count: int
