"""Interest circle management, multi-tier nested comment trees, and moderation service.

Implements:
- Circle discovery across thematic categories (art, hiking, dating, treehole)
- Circle membership lifecycle (join, roles, mute status)
- Multi-tier threaded comment submission with text safety verification
- Recursive tree building algorithm with hot-pinned comment prioritization
- Community administration & content moderation actions (mute, delete, ban)
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from soulred.models.circle import (
    InterestCircle,
    CircleMember,
    CircleComment,
    CircleRoleEnum,
    CircleCategoryEnum,
)
from soulred.models.post import Post
from soulred.models.user import User
from soulred.schemas.circle import (
    CircleCreateSchema,
    CircleResponse,
    CommentCreateSchema,
    CommentResponse,
    CommentTreeResponse,
    ModerationActionSchema,
)
from soulred.services.safety_service import ContentSafetyService


class CircleService:
    """Core domain service for interest circles and nested comment trees."""

    @classmethod
    def list_circles(
        cls,
        db: Session,
        category: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[CircleResponse]:
        """List community circles with optional category filter and membership indicator."""
        query = db.query(InterestCircle)
        if category:
            query = query.filter(InterestCircle.category == category)

        circles = query.offset(offset).limit(limit).all()

        joined_circle_ids = set()
        if user_id:
            user_memberships = (
                db.query(CircleMember.circle_id)
                .filter(CircleMember.user_id == user_id)
                .all()
            )
            joined_circle_ids = {m[0] for m in user_memberships}

        responses: List[CircleResponse] = []
        for c in circles:
            responses.append(
                CircleResponse(
                    id=c.id,
                    name=c.name,
                    category=c.category,
                    description=c.description,
                    avatar_url=c.avatar_url,
                    banner_url=c.banner_url,
                    member_count=c.member_count,
                    post_count=c.post_count,
                    is_joined=c.id in joined_circle_ids,
                    created_at=c.created_at,
                )
            )
        return responses

    @classmethod
    def join_circle(
        cls,
        db: Session,
        user_id: str,
        circle_id: str,
    ) -> CircleMember:
        """Join a thematic circle or return existing membership."""
        circle = db.query(InterestCircle).filter(InterestCircle.id == circle_id).first()
        if not circle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Circle not found",
            )

        member = (
            db.query(CircleMember)
            .filter(CircleMember.circle_id == circle_id, CircleMember.user_id == user_id)
            .first()
        )
        if member:
            return member

        new_member = CircleMember(
            circle_id=circle_id,
            user_id=user_id,
            role=CircleRoleEnum.MEMBER.value,
            is_muted=False,
        )
        db.add(new_member)
        circle.member_count += 1
        db.commit()
        db.refresh(new_member)
        return new_member

    @classmethod
    def post_comment(
        cls,
        db: Session,
        user_id: str,
        comment_in: CommentCreateSchema,
    ) -> CircleComment:
        """Post a top-level or nested thread comment after moderation check."""
        # Check muting status in circle if circle_id is provided
        if comment_in.circle_id:
            membership = (
                db.query(CircleMember)
                .filter(
                    CircleMember.circle_id == comment_in.circle_id,
                    CircleMember.user_id == user_id,
                )
                .first()
            )
            if membership and membership.is_muted:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="您已被圈子管理员禁言，无法发表评论",
                )

        # Content Safety verification
        safety_check = ContentSafetyService.check_text_safety(comment_in.content)
        if safety_check["action"] == "REJECTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="评论包含违规或敏感内容，发布失败",
            )

        clean_content = safety_check.get("filtered_text", comment_in.content)

        # Parent comment existence verification
        if comment_in.parent_id:
            parent = db.query(CircleComment).filter(CircleComment.id == comment_in.parent_id).first()
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent comment not found",
                )

        comment = CircleComment(
            post_id=comment_in.post_id,
            circle_id=comment_in.circle_id,
            user_id=user_id,
            parent_id=comment_in.parent_id,
            content=clean_content,
            image_url=comment_in.image_url,
            likes_count=0,
            is_pinned=False,
            is_deleted=False,
        )
        db.add(comment)

        # Increment post comment counter
        if comment_in.post_id:
            post = db.query(Post).filter(Post.id == comment_in.post_id).first()
            if post:
                post.comments_count += 1

        db.commit()
        db.refresh(comment)
        return comment

    @classmethod
    def build_comment_tree(
        cls,
        comments: List[CircleComment],
    ) -> List[CommentTreeResponse]:
        """Transform a flat list of comments into a hierarchical threaded tree structure."""
        if not comments:
            return []

        # Map comment ID to CommentTreeResponse
        nodes: Dict[str, CommentTreeResponse] = {}
        for c in comments:
            if c.is_deleted:
                continue

            user = c.user
            profile = user.profile if user else None
            author_nick = profile.nickname if profile else "SoulRed Explorer"
            author_avatar = profile.avatar_url if profile else None

            node = CommentTreeResponse(
                id=c.id,
                post_id=c.post_id,
                user_id=c.user_id,
                author_nickname=author_nick,
                author_avatar_url=author_avatar,
                parent_id=c.parent_id,
                content=c.content,
                image_url=c.image_url,
                likes_count=c.likes_count,
                is_pinned=c.is_pinned,
                created_at=c.created_at,
                replies=[],
            )
            nodes[c.id] = node

        # Assemble tree
        roots: List[CommentTreeResponse] = []
        for c_id, node in nodes.items():
            if node.parent_id and node.parent_id in nodes:
                nodes[node.parent_id].replies.append(node)
            else:
                roots.append(node)

        # Sort roots: Pinned first, then likes_count desc, then created_at desc
        roots.sort(
            key=lambda r: (1 if r.is_pinned else 0, r.likes_count, r.created_at),
            reverse=True,
        )

        # Sort replies chronologically
        def sort_replies_recursively(parent: CommentTreeResponse):
            parent.replies.sort(key=lambda x: x.created_at)
            for child in parent.replies:
                sort_replies_recursively(child)

        for root in roots:
            sort_replies_recursively(root)

        return roots

    @classmethod
    def moderate_content(
        cls,
        db: Session,
        admin_user_id: str,
        action_in: ModerationActionSchema,
    ) -> Dict[str, Any]:
        """Execute administrative moderation interventions (delete, mute, ban)."""
        target_type = action_in.target_type.lower()
        act = action_in.action.lower()

        if target_type == "post":
            post = db.query(Post).filter(Post.id == action_in.target_id).first()
            if not post:
                raise HTTPException(status_code=404, detail="Target post not found")
            if act in ["delete", "ban"]:
                post.is_deleted = True
            db.commit()
            return {"success": True, "target_id": post.id, "action": act, "message": "Post moderated"}

        elif target_type == "comment":
            comment = db.query(CircleComment).filter(CircleComment.id == action_in.target_id).first()
            if not comment:
                raise HTTPException(status_code=404, detail="Target comment not found")
            if act in ["delete", "ban"]:
                comment.is_deleted = True
            db.commit()
            return {"success": True, "target_id": comment.id, "action": act, "message": "Comment moderated"}

        elif target_type == "user":
            user = db.query(User).filter(User.id == action_in.target_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="Target user not found")
            if act == "ban":
                user.is_active = False
            elif act == "mute":
                # Mute in all circles
                db.query(CircleMember).filter(CircleMember.user_id == user.id).update({"is_muted": True})
            db.commit()
            return {"success": True, "target_id": user.id, "action": act, "message": "User moderated"}

        raise HTTPException(status_code=400, detail=f"Unsupported target type: {target_type}")


# Module-level convenience functions matching architecture symbols
list_circles = CircleService.list_circles
join_circle = CircleService.join_circle
post_comment = CircleService.post_comment
build_comment_tree = CircleService.build_comment_tree
moderate_content = CircleService.moderate_content
