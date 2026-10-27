"""Xiaohongshu dual-column waterfall feed dynamic square REST endpoints."""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from soulred.api.deps import get_db_session, get_optional_current_user
from soulred.models.user import User
from soulred.schemas.post import PostWaterfallCard
from soulred.services.feed_service import FeedService

router = APIRouter(prefix="/feed", tags=["Waterfall Feed"])


class FeedResponseWrapper(BaseModel):
    """Enveloped waterfall feed response for frontend and pagination."""
    items: List[PostWaterfallCard]
    channel: str
    page: int
    page_size: int
    total: int


@router.get(
    "",
    summary="Get Xiaohongshu dual-column waterfall feed cards",
)
def get_waterfall_feed(
    channel: str = Query("recommend", description="Channel selector: 'recommend', 'nearby', or 'following'"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size limit"),
    viewer_lat: Optional[float] = Query(None, description="Viewer latitude for nearby feed"),
    viewer_lon: Optional[float] = Query(None, description="Viewer longitude for nearby feed"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    """Retrieve adaptive waterfall feed cards with precalculated aspect ratio heights and skeleton tints."""
    current_user_id = current_user.id if current_user else None
    offset = (page - 1) * page_size

    cards = FeedService.get_waterfall_feed(
        db=db,
        channel=channel,
        current_user_id=current_user_id,
        limit=page_size,
        offset=offset,
        viewer_lat=viewer_lat,
        viewer_lon=viewer_lon,
    )

    return {
        "items": [card.model_dump() for card in cards],
        "channel": channel,
        "page": page,
        "page_size": page_size,
        "total": len(cards),
    }
