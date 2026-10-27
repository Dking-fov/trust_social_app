"""Post note creation, draft auto-save, like toggles, and detail assembly service.

Implements Xiaohongshu-style rich note publishing with:
- AI content safety filtering (real-time sensitive word blocking)
- Multimodal image attachments (1:1, 3:4, 4:3) with blurhash support
- Local draft auto-save and retrieval
- Atomically counted like interaction states
- Immersive post detail view assembly
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from soulred.models.post import (
    Post,
    PostImage,
    PostLike,
    PostDraft,
    PostStatusEnum,
    AspectRatioEnum,
)
from soulred.models.circle import InterestCircle
from soulred.models.user import User
from soulred.schemas.post import (
    PostCreate,
    PostDraftSave,
    PostLikeToggleResponse,
    PostDetailResponse,
    PostAuthorInfo,
    PostImageSchema,
)
from soulred.services.safety_service import ContentSafetyService


class PostService:
    """Core domain service for user notes, drafts, and like interactions."""

    @classmethod
    def create_post(
        cls,
        db: Session,
        author_id: str,
        post_in: PostCreate,
    ) -> Post:
        """Publish a new post note with AI safety verification and image attachments."""
        # 1. AI Content Safety Review
        image_urls = [img.image_url for img in post_in.images]
        review_result = ContentSafetyService.review_post_content(
            title=post_in.title,
            content=post_in.content,
            image_urls=image_urls,
        )

        if review_result["action"] == "REJECTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Post rejected by content safety filter: {review_result.get('reason')}",
            )

        post_status = (
            PostStatusEnum.PENDING.value
            if review_result["action"] == "PENDING_REVIEW"
            else PostStatusEnum.PUBLISHED.value
        )

        final_content = review_result.get("filtered_content", post_in.content)

        # 2. Persist Post entity
        post = Post(
            author_id=author_id,
            title=post_in.title,
            content=final_content,
            mood_tag=post_in.mood_tag,
            topics=post_in.topics or [],
            channel=post_in.channel or "recommend",
            status=post_status,
            location=post_in.location,
            latitude=post_in.latitude,
            longitude=post_in.longitude,
            circle_id=post_in.circle_id,
            likes_count=0,
            comments_count=0,
            view_count=0,
        )
        db.add(post)
        db.flush()

        # 3. Attach post images (up to 9 items)
        for idx, img_schema in enumerate(post_in.images[:9]):
            post_image = PostImage(
                post_id=post.id,
                image_url=img_schema.image_url,
                order_index=img_schema.order_index if img_schema.order_index is not None else idx,
                aspect_ratio=img_schema.aspect_ratio or AspectRatioEnum.RATIO_3_4.value,
                width=img_schema.width or 1080,
                height=img_schema.height or 1440,
                blurhash=img_schema.blurhash or "LEHV6nWB2yk8pyo0adR*.7kCMdnj",
            )
            db.add(post_image)

        # 4. If linked to an interest circle, increment circle post count
        if post_in.circle_id:
            circle = db.query(InterestCircle).filter(InterestCircle.id == post_in.circle_id).first()
            if circle:
                circle.post_count += 1

        db.commit()
        db.refresh(post)
        return post

    @classmethod
    def save_draft(
        cls,
        db: Session,
        user_id: str,
        draft_in: PostDraftSave,
    ) -> PostDraft:
        """Upsert user's local auto-save draft."""
        draft = db.query(PostDraft).filter(PostDraft.user_id == user_id).first()
        if not draft:
            draft = PostDraft(
                user_id=user_id,
                title=draft_in.title,
                content=draft_in.content,
                mood_tag=draft_in.mood_tag,
                topics=draft_in.topics or [],
                image_urls=draft_in.image_urls or [],
            )
            db.add(draft)
        else:
            draft.title = draft_in.title
            draft.content = draft_in.content
            draft.mood_tag = draft_in.mood_tag
            draft.topics = draft_in.topics or []
            draft.image_urls = draft_in.image_urls or []

        db.commit()
        db.refresh(draft)
        return draft

    @classmethod
    def get_draft(
        cls,
        db: Session,
        user_id: str,
    ) -> Optional[PostDraft]:
        """Retrieve user's active saved draft."""
        return db.query(PostDraft).filter(PostDraft.user_id == user_id).first()

    @classmethod
    def toggle_like(
        cls,
        db: Session,
        user_id: str,
        post_id: str,
    ) -> PostLikeToggleResponse:
        """Toggle like state on a post note atomically."""
        post = db.query(Post).filter(Post.id == post_id, Post.is_deleted == False).first()
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found",
            )

        existing_like = (
            db.query(PostLike)
            .filter(PostLike.post_id == post_id, PostLike.user_id == user_id)
            .first()
        )

        if existing_like:
            db.delete(existing_like)
            post.likes_count = max(0, post.likes_count - 1)
            is_liked = False
        else:
            new_like = PostLike(post_id=post_id, user_id=user_id)
            db.add(new_like)
            post.likes_count += 1
            is_liked = True

        db.commit()
        db.refresh(post)
        return PostLikeToggleResponse(
            post_id=post.id,
            is_liked=is_liked,
            likes_count=post.likes_count,
        )

    @classmethod
    def get_post_detail(
        cls,
        db: Session,
        post_id: str,
        current_user_id: Optional[str] = None,
    ) -> PostDetailResponse:
        """Assemble full post detail with author persona, image list, and view counter."""
        post = db.query(Post).filter(Post.id == post_id, Post.is_deleted == False).first()
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found",
            )

        # Increment view count
        post.view_count += 1
        db.commit()

        # Check like status
        is_liked = False
        if current_user_id:
            like_exists = (
                db.query(PostLike)
                .filter(PostLike.post_id == post_id, PostLike.user_id == current_user_id)
                .first()
            )
            is_liked = like_exists is not None

        # Author summary
        author = post.author
        profile = author.profile if author else None
        author_info = PostAuthorInfo(
            id=author.id if author else "unknown",
            nickname=profile.nickname if profile else "SoulRed Explorer",
            avatar_url=profile.avatar_url if profile else None,
            mbti=profile.mbti if profile else None,
        )

        # Images list
        images_schema = [
            PostImageSchema.model_validate(img)
            for img in sorted(post.images, key=lambda x: x.order_index)
        ]

        return PostDetailResponse(
            id=post.id,
            title=post.title,
            content=post.content,
            mood_tag=post.mood_tag,
            topics=post.topics or [],
            channel=post.channel,
            location=post.location,
            likes_count=post.likes_count,
            comments_count=post.comments_count,
            view_count=post.view_count,
            is_liked=is_liked,
            author=author_info,
            images=images_schema,
            created_at=post.created_at,
        )


# Module-level convenience functions matching architecture symbols
create_post = PostService.create_post
save_draft = PostService.save_draft
get_draft = PostService.get_draft
toggle_like = PostService.toggle_like
get_post_detail = PostService.get_post_detail
