"""Pydantic schemas for interest circles, multi-tier comments, and moderation."""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class CircleCreateSchema(BaseModel):
    """Payload for creating a new interest circle."""
    name: str = Field(..., min_length=2, max_length=100, description="Unique circle name")
    category: str = Field("生活方式", description="Circle category (e.g. 艺术展览, 户外徒步)")
    description: Optional[str] = Field(None, max_length=1000, description="Circle manifesto/description")
    avatar_url: Optional[str] = Field(None, description="Circle icon image URL")
    banner_url: Optional[str] = Field(None, description="Top header background banner")


class CircleResponse(BaseModel):
    """Interest circle profile card response."""
    id: str
    name: str
    category: str
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    member_count: int = 1
    post_count: int = 0
    is_joined: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommentCreateSchema(BaseModel):
    """Payload for publishing a top-level or reply comment."""
    post_id: Optional[str] = Field(None, description="Target post UUID")
    circle_id: Optional[str] = Field(None, description="Optional target circle UUID")
    parent_id: Optional[str] = Field(None, description="Parent comment UUID for nested thread replies")
    content: str = Field(..., min_length=1, max_length=2000, description="Comment body")
    image_url: Optional[str] = Field(None, description="Optional image attachment")


class CommentResponse(BaseModel):
    """Flat comment item representation."""
    id: str
    post_id: Optional[str] = None
    circle_id: Optional[str] = None
    user_id: str
    author_nickname: str
    author_avatar_url: Optional[str] = None
    parent_id: Optional[str] = None
    content: str
    image_url: Optional[str] = None
    likes_count: int = 0
    is_pinned: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommentTreeResponse(BaseModel):
    """Recursive nested comment tree representation."""
    id: str
    post_id: Optional[str] = None
    user_id: str
    author_nickname: str
    author_avatar_url: Optional[str] = None
    parent_id: Optional[str] = None
    content: str
    image_url: Optional[str] = None
    likes_count: int = 0
    is_pinned: bool = False
    created_at: datetime
    replies: List[CommentTreeResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ModerationActionSchema(BaseModel):
    """Payload for administrative and AI content moderation actions."""
    target_type: str = Field(..., description="Entity type: 'post', 'comment', or 'user'")
    target_id: str = Field(..., description="Target UUID")
    action: str = Field(..., description="Intervention action: 'ban', 'delete', 'warn', or 'mute'")
    reason: Optional[str] = Field(None, description="Moderation justification / violated rule")
