"""Interest circle community, memberships, and multi-tier nested comment REST endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from soulred.api.deps import (
    get_db_session,
    get_current_active_user,
    get_optional_current_user,
)
from soulred.models.circle import InterestCircle, CircleComment
from soulred.models.post import Post
from soulred.models.user import User
from soulred.schemas.circle import (
    CircleCreateSchema,
    CircleResponse,
    CommentCreateSchema,
    CommentResponse,
    CommentTreeResponse,
)
from soulred.schemas.post import PostDetailResponse
from soulred.services.circle_service import CircleService
from soulred.services.post_service import PostService

router = APIRouter(prefix="/circles", tags=["Interest Circles"])


@router.get(
    "",
    response_model=List[CircleResponse],
    summary="List thematic interest circles",
)
def list_circles(
    category: Optional[str] = Query(None, description="Category filter (e.g. '艺术展览', '户外徒步')"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db_session),
) -> List[CircleResponse]:
    """Retrieve interest circle square with membership status indicator."""
    user_id = current_user.id if current_user else None
    return CircleService.list_circles(
        db=db,
        category=category,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=CircleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new interest circle",
)
def create_circle(
    circle_in: CircleCreateSchema,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> CircleResponse:
    """Create a new thematic interest circle with current user as owner."""
    existing = db.query(InterestCircle).filter(InterestCircle.name == circle_in.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Circle '{circle_in.name}' already exists",
        )

    circle = InterestCircle(
        name=circle_in.name,
        category=circle_in.category,
        description=circle_in.description,
        avatar_url=circle_in.avatar_url,
        banner_url=circle_in.banner_url,
        owner_id=current_user.id,
        member_count=1,
        post_count=0,
    )
    db.add(circle)
    db.flush()

    # Add owner membership
    CircleService.join_circle(db=db, user_id=current_user.id, circle_id=circle.id)

    db.commit()
    db.refresh(circle)
    return CircleResponse(
        id=circle.id,
        name=circle.name,
        category=circle.category,
        description=circle.description,
        avatar_url=circle.avatar_url,
        banner_url=circle.banner_url,
        member_count=circle.member_count,
        post_count=circle.post_count,
        is_joined=True,
        created_at=circle.created_at,
    )


@router.post(
    "/{circle_id}/join",
    summary="Join an interest circle",
)
def join_circle(
    circle_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """Join community circle and increment member count."""
    member = CircleService.join_circle(
        db=db,
        user_id=current_user.id,
        circle_id=circle_id,
    )
    return {
        "status": "success",
        "circle_id": member.circle_id,
        "user_id": member.user_id,
        "role": member.role,
        "is_muted": member.is_muted,
        "joined_at": member.joined_at,
    }


@router.get(
    "/{circle_id}/posts",
    response_model=List[PostDetailResponse],
    summary="Get discussion note posts in this circle",
)
def get_circle_posts(
    circle_id: str,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db_session),
) -> List[PostDetailResponse]:
    """Retrieve posts belonging to this circle ordered by pinned status and recency."""
    posts = (
        db.query(Post)
        .filter(Post.circle_id == circle_id, Post.is_deleted == False)
        .order_by(Post.is_hot.desc(), Post.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    viewer_id = current_user.id if current_user else None
    return [
        PostService.get_post_detail(db=db, post_id=p.id, current_user_id=viewer_id)
        for p in posts
    ]


@router.post(
    "/{circle_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a comment in circle or thread",
)
def create_comment_in_circle(
    circle_id: str,
    comment_in: CommentCreateSchema,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> CommentResponse:
    """Publish a top-level or reply comment associated with a circle."""
    comment_in.circle_id = circle_id
    comment = CircleService.post_comment(
        db=db,
        user_id=current_user.id,
        comment_in=comment_in,
    )
    profile = current_user.profile
    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        circle_id=comment.circle_id,
        user_id=comment.user_id,
        author_nickname=profile.nickname if profile else current_user.username,
        author_avatar_url=profile.avatar_url if profile else None,
        parent_id=comment.parent_id,
        content=comment.content,
        image_url=comment.image_url,
        likes_count=comment.likes_count,
        is_pinned=comment.is_pinned,
        created_at=comment.created_at,
    )


@router.post(
    "/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create top-level or reply comment",
)
def create_comment(
    comment_in: CommentCreateSchema,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> CommentResponse:
    """Publish top-level or nested reply comment for post notes or circles."""
    comment = CircleService.post_comment(
        db=db,
        user_id=current_user.id,
        comment_in=comment_in,
    )
    profile = current_user.profile
    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        circle_id=comment.circle_id,
        user_id=comment.user_id,
        author_nickname=profile.nickname if profile else current_user.username,
        author_avatar_url=profile.avatar_url if profile else None,
        parent_id=comment.parent_id,
        content=comment.content,
        image_url=comment.image_url,
        likes_count=comment.likes_count,
        is_pinned=comment.is_pinned,
        created_at=comment.created_at,
    )


@router.get(
    "/{circle_id}/comments/tree",
    response_model=List[CommentTreeResponse],
    summary="Get multi-tier hierarchical nested comment tree for circle",
)
def get_circle_comment_tree(
    circle_id: str,
    db: Session = Depends(get_db_session),
) -> List[CommentTreeResponse]:
    """Assemble nested tree representation of circle discussion comments."""
    comments = (
        db.query(CircleComment)
        .filter(CircleComment.circle_id == circle_id, CircleComment.is_deleted == False)
        .order_by(CircleComment.is_pinned.desc(), CircleComment.created_at.asc())
        .all()
    )
    return CircleService.build_comment_tree(comments=comments)


@router.get(
    "/comments/tree",
    response_model=List[CommentTreeResponse],
    summary="Get multi-tier nested comment tree by post_id or circle_id",
)
def get_comment_tree(
    post_id: Optional[str] = Query(None, description="Post UUID to fetch comments for"),
    circle_id: Optional[str] = Query(None, description="Circle UUID to fetch comments for"),
    db: Session = Depends(get_db_session),
) -> List[CommentTreeResponse]:
    """Retrieve recursive comment tree prioritizing pinned hot comments."""
    query = db.query(CircleComment).filter(CircleComment.is_deleted == False)
    if post_id:
        query = query.filter(CircleComment.post_id == post_id)
    if circle_id:
        query = query.filter(CircleComment.circle_id == circle_id)

    comments = query.order_by(CircleComment.is_pinned.desc(), CircleComment.created_at.asc()).all()
    return CircleService.build_comment_tree(comments=comments)
