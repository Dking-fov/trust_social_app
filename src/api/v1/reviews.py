"""Endpoints for double-blind post-date review submission and reputation score queries."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.user import User
from src.models.dating import DateInvitation, DateReview, ReviewStatusEnum
from src.schemas.dating_schemas import DateReviewSubmitRequest, DateReviewResponse
from src.core.security import require_verified_user
from src.services.reputation_service import ReputationService

router = APIRouter(prefix="/reviews", tags=["Reputation & Post-Date Reviews"])


@router.post("/{date_id}", response_model=DateReviewResponse)
async def submit_review_endpoint(
    date_id: int,
    req: DateReviewSubmitRequest,
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Submits a double-blind post-date evaluation (1.0-5.0 stars with 0.5 increment, behavioral tags)."""
    stmt = select(DateInvitation).where(DateInvitation.id == date_id)
    invitation = (await db.execute(stmt)).scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Date not found.")

    review = await ReputationService.submit_blind_review(
        db=db,
        date_invitation=invitation,
        reviewer_id=current_user.id,
        rating=req.rating,
        behavioral_tags=req.behavioral_tags,
        comment=req.comment,
    )

    is_revealed = review.status == ReviewStatusEnum.PUBLISHED
    return DateReviewResponse(
        id=review.id,
        date_invitation_id=review.date_invitation_id,
        reviewer_id=review.reviewer_id,
        reviewee_id=review.reviewee_id,
        rating=review.rating if is_revealed or review.reviewer_id == current_user.id else None,
        behavioral_tags=review.behavioral_tags if is_revealed or review.reviewer_id == current_user.id else None,
        comment=review.comment if is_revealed or review.reviewer_id == current_user.id else None,
        status=review.status,
        is_revealed=is_revealed,
        created_at=review.created_at,
        published_at=review.published_at,
    )


@router.get("/{date_id}", response_model=List[DateReviewResponse])
async def get_date_reviews_endpoint(
    date_id: int,
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves post-date reviews for a date (ratings masked until both submit or 48h elapses)."""
    # Trigger reveal check in case 48h timeout has passed
    await ReputationService.try_reveal_reviews(db=db, date_invitation_id=date_id)

    stmt = select(DateReview).where(DateReview.date_invitation_id == date_id)
    reviews = (await db.execute(stmt)).scalars().all()

    results = []
    for r in reviews:
        is_revealed = r.status == ReviewStatusEnum.PUBLISHED
        is_author = r.reviewer_id == current_user.id

        results.append(
            DateReviewResponse(
                id=r.id,
                date_invitation_id=r.date_invitation_id,
                reviewer_id=r.reviewer_id,
                reviewee_id=r.reviewee_id,
                rating=r.rating if (is_revealed or is_author) else None,
                behavioral_tags=r.behavioral_tags if (is_revealed or is_author) else None,
                comment=r.comment if (is_revealed or is_author) else None,
                status=r.status,
                is_revealed=is_revealed,
                created_at=r.created_at,
                published_at=r.published_at,
            )
        )

    return results
