"""Xiaohongshu-style dual-column waterfall feed generation and ranking engine.

Implements:
- Aspect ratio pre-computation and skeleton placeholder styling
- Dynamic multi-channel feed distribution:
    * 'recommend': Interaction heat + exponential time-decay scoring
    * 'nearby': Spherical Haversine distance-based proximity ranking
    * 'following': Chronological reverse publication stream
- Seamless zero-CLS dual-column card payload assembly
"""

import math
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session

from soulred.models.post import (
    Post,
    PostImage,
    PostLike,
    PostStatusEnum,
    AspectRatioEnum,
)
from soulred.schemas.post import PostWaterfallCard
from soulred.services.auth_service import AuthService


class FeedService:
    """Core domain service for waterfall feed ranking and layout calculation."""

    ASPECT_RATIO_CONFIG = {
        AspectRatioEnum.RATIO_1_1.value: (260, "#fef2f2"),
        AspectRatioEnum.RATIO_3_4.value: (340, "#f3f4f6"),
        AspectRatioEnum.RATIO_4_3.value: (200, "#f0fdf4"),
    }

    @classmethod
    def calculate_card_aspect_ratio(
        cls,
        aspect_ratio: str = "3:4",
        width: int = 1080,
        height: int = 1440,
    ) -> Tuple[int, str]:
        """Compute virtual skeleton height and placeholder tint based on image geometry."""
        if aspect_ratio in cls.ASPECT_RATIO_CONFIG:
            return cls.ASPECT_RATIO_CONFIG[aspect_ratio]

        # Dynamic fallback calculation
        if width > 0 and height > 0:
            ratio = height / width
            calculated_height = int(240 * ratio)
            clamped_height = max(180, min(420, calculated_height))
            return clamped_height, "#eff6ff"

        return 340, "#f3f4f6"

    @classmethod
    def rank_feed_items(
        cls,
        posts: List[Post],
        channel: str = "recommend",
        viewer_lat: Optional[float] = None,
        viewer_lon: Optional[float] = None,
    ) -> List[Post]:
        """Rank post items dynamically based on channel-specific heuristics."""
        now = datetime.now(timezone.utc)

        if channel == "nearby":
            # Rank primarily by distance to viewer
            def get_distance(p: Post) -> float:
                if (
                    viewer_lat is not None
                    and viewer_lon is not None
                    and p.latitude is not None
                    and p.longitude is not None
                ):
                    return AuthService._calculate_haversine(
                        viewer_lat, viewer_lon, p.latitude, p.longitude
                    )
                return 999999.0

            return sorted(posts, key=get_distance)

        elif channel == "following":
            # Chronological reverse order
            return sorted(
                posts,
                key=lambda p: p.created_at or now,
                reverse=True,
            )

        else:
            # Default 'recommend': Heat + Time Decay
            # Heat = likes * 2.0 + comments * 3.0 + views * 0.1
            def calculate_score(p: Post) -> float:
                heat = (
                    (p.likes_count or 0) * 2.0
                    + (p.comments_count or 0) * 3.0
                    + (p.view_count or 0) * 0.1
                )
                created = p.created_at or now
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                hours_elapsed = max(0.0, (now - created).total_seconds() / 3600.0)
                # Exponential/fractional time decay
                decay = 1.0 / (1.0 + hours_elapsed * 0.05)
                return (heat + 1.0) * decay

            return sorted(posts, key=calculate_score, reverse=True)

    @classmethod
    def get_waterfall_feed(
        cls,
        db: Session,
        channel: str = "recommend",
        current_user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        viewer_lat: Optional[float] = None,
        viewer_lon: Optional[float] = None,
    ) -> List[PostWaterfallCard]:
        """Fetch and assemble Xiaohongshu-style dual-column waterfall cards."""
        query = db.query(Post).filter(
            Post.status == PostStatusEnum.PUBLISHED.value,
            Post.is_deleted == False,
        )

        if channel in ["recommend", "nearby", "following"]:
            # Note: channel filtering can be strict or fallback to general published
            channel_posts = query.filter(Post.channel == channel).all()
            # If strictly filtered count is zero, allow general published posts
            posts = channel_posts if channel_posts else query.all()
        else:
            posts = query.all()

        # Rank items
        ranked_posts = cls.rank_feed_items(
            posts,
            channel=channel,
            viewer_lat=viewer_lat,
            viewer_lon=viewer_lon,
        )

        # Slice for pagination
        page_posts = ranked_posts[offset : offset + limit]

        # Determine liked post IDs for current user in one pass
        liked_post_ids = set()
        if current_user_id and page_posts:
            target_ids = [p.id for p in page_posts]
            user_likes = (
                db.query(PostLike.post_id)
                .filter(
                    PostLike.user_id == current_user_id,
                    PostLike.post_id.in_(target_ids),
                )
                .all()
            )
            liked_post_ids = {ul[0] for ul in user_likes}

        # Build cards
        cards: List[PostWaterfallCard] = []
        for p in page_posts:
            # First image as cover
            first_img = p.images[0] if p.images else None
            cover_url = (
                first_img.image_url
                if first_img
                else "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=600&q=80"
            )
            aspect_ratio_str = first_img.aspect_ratio if first_img else AspectRatioEnum.RATIO_3_4.value
            width = first_img.width if first_img else 1080
            height = first_img.height if first_img else 1440

            card_height, skeleton_color = cls.calculate_card_aspect_ratio(
                aspect_ratio=aspect_ratio_str,
                width=width,
                height=height,
            )

            # Author info
            author = p.author
            profile = author.profile if author else None
            author_nickname = profile.nickname if profile else "SoulRed Explorer"
            author_avatar = (
                profile.avatar_url
                if profile
                else "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=400&q=80"
            )

            # Content summary (first 60 characters)
            summary = p.content[:60] + "..." if len(p.content) > 60 else p.content

            # Proximity calculation
            dist_km: Optional[float] = None
            if (
                viewer_lat is not None
                and viewer_lon is not None
                and p.latitude is not None
                and p.longitude is not None
            ):
                dist_km = round(
                    AuthService._calculate_haversine(
                        viewer_lat, viewer_lon, p.latitude, p.longitude
                    ),
                    2,
                )

            card = PostWaterfallCard(
                id=p.id,
                title=p.title,
                content_summary=summary,
                cover_image_url=cover_url,
                aspect_ratio=aspect_ratio_str,
                card_height=card_height,
                skeleton_color=skeleton_color,
                author_id=p.author_id,
                author_nickname=author_nickname,
                author_avatar_url=author_avatar,
                likes_count=p.likes_count,
                is_liked=p.id in liked_post_ids,
                mood_tag=p.mood_tag,
                topics=p.topics or [],
                image_count=len(p.images),
                channel=p.channel,
                distance_km=dist_km,
                created_at=p.created_at,
            )
            cards.append(card)

        return cards


# Module-level convenience functions matching architecture symbols
get_waterfall_feed = FeedService.get_waterfall_feed
calculate_card_aspect_ratio = FeedService.calculate_card_aspect_ratio
rank_feed_items = FeedService.rank_feed_items
