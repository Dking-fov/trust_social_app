"""Post note publishing, drafts, details, and like interaction REST endpoints."""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from soulred.api.deps import (
    get_db_session,
    get_current_active_user,
    get_optional_current_user,
)
from soulred.models.user import User
from soulred.schemas.post import (
    PostCreate,
    PostDetailResponse,
    PostDraftSave,
    PostLikeToggleResponse,
)
from soulred.services.post_service import PostService

router = APIRouter(prefix="/posts", tags=["Posts"])


@router.post(
    "",
    response_model=PostDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publish Xiaohongshu-style rich-media note post",
)
def create_post(
    post_in: PostCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> PostDetailResponse:
    """Create and publish note post with AI safety verification and image attachments."""
    post = PostService.create_post(
        db=db,
        author_id=current_user.id,
        post_in=post_in,
    )
    return PostService.get_post_detail(
        db=db,
        post_id=post.id,
        current_user_id=current_user.id,
    )


@router.post(
    "/draft",
    summary="Save or update local draft",
)
def save_draft(
    draft_in: PostDraftSave,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    """Auto-save note composition draft to prevent data loss on network disruption."""
    draft = PostService.save_draft(
        db=db,
        user_id=current_user.id,
        draft_in=draft_in,
    )
    return {
        "status": "success",
        "draft_id": draft.id,
        "title": draft.title,
        "content": draft.content,
        "mood_tag": draft.mood_tag,
        "topics": draft.topics or [],
        "image_urls": draft.image_urls or [],
        "updated_at": draft.updated_at,
    }


@router.get(
    "/draft",
    summary="Retrieve active saved draft for current user",
)
def get_my_draft(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    """Retrieve existing draft or return empty draft state."""
    draft = PostService.get_draft(db=db, user_id=current_user.id)
    if not draft:
        return {
            "status": "empty",
            "draft": None,
        }
    return {
        "status": "found",
        "draft": {
            "id": draft.id,
            "title": draft.title,
            "content": draft.content,
            "mood_tag": draft.mood_tag,
            "topics": draft.topics or [],
            "image_urls": draft.image_urls or [],
            "updated_at": draft.updated_at,
        },
    }


@router.get(
    "/{post_id}",
    response_model=PostDetailResponse,
    summary="Get full immersive post details",
)
def get_post(
    post_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db_session),
) -> PostDetailResponse:
    """Retrieve post note by UUID, including author details, images, and like state."""
    viewer_id = current_user.id if current_user else None
    return PostService.get_post_detail(
        db=db,
        post_id=post_id,
        current_user_id=viewer_id,
    )


@router.post(
    "/{post_id}/like",
    response_model=PostLikeToggleResponse,
    summary="Toggle like state on a post note",
)
def toggle_like(
    post_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> PostLikeToggleResponse:
    """Like or unlike a post note atomically."""
    return PostService.toggle_like(
        db=db,
        user_id=current_user.id,
        post_id=post_id,
    )
