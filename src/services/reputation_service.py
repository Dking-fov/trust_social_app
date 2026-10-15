"""Bayesian Average computation, double-blind post-date review reveal, and 30-day collusion cooldown."""

from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.user import User
from src.models.dating import DateInvitation, DateReview, DateStatusEnum, ReviewStatusEnum
from src.models.points import PointReasonEnum
from src.core.exceptions import AppBaseException, AppErrorCode
from src.services.points_service import PointsService

settings = get_settings()


class ReputationService:
    """Computes Bayesian smoothed reputation scores and manages double-blind review lifecycles."""

    @classmethod
    def calculate_bayesian_score(
        cls,
        ratings: List[float],
        m: Optional[float] = None,
        c: Optional[float] = None,
    ) -> float:
        """Computes Bayesian Average: S = (C * m + sum(ratings)) / (m + len(ratings))."""
        prior_m = m if m is not None else settings.BAYESIAN_PRIOR_WEIGHT_M
        baseline_c = c if c is not None else settings.BAYESIAN_BASELINE_SCORE_C

        if not ratings:
            return round(baseline_c, 2)

        total_rating = sum(ratings)
        v = len(ratings)
        score = (baseline_c * prior_m + total_rating) / (prior_m + v)
        return round(score, 2)

    @classmethod
    async def validate_30_day_pair_cooldown(
        cls,
        db: AsyncSession,
        user_a_id: int,
        user_b_id: int,
        current_date_id: int,
    ) -> bool:
        """Returns True if the pair has a valid published review within the last 30 days (collusion risk)."""
        cooldown_threshold = datetime.utcnow() - timedelta(days=settings.COLLUSION_COOLDOWN_DAYS)

        stmt = select(DateReview).where(
            and_(
                DateReview.date_invitation_id != current_date_id,
                DateReview.status == ReviewStatusEnum.PUBLISHED,
                DateReview.is_collusion.is_(False),
                DateReview.created_at >= cooldown_threshold,
                or_(
                    and_(DateReview.reviewer_id == user_a_id, DateReview.reviewee_id == user_b_id),
                    and_(DateReview.reviewer_id == user_b_id, DateReview.reviewee_id == user_a_id),
                ),
            )
        )
        result = await db.execute(stmt)
        prior_review = result.scalars().first()
        return prior_review is not None

    @classmethod
    async def submit_blind_review(
        cls,
        db: AsyncSession,
        date_invitation: DateInvitation,
        reviewer_id: int,
        rating: float,
        behavioral_tags: List[str],
        comment: Optional[str] = None,
    ) -> DateReview:
        """Submits a double-blind post-date review."""
        if date_invitation.status != DateStatusEnum.COMPLETED:
            raise AppBaseException(
                status_code=400,
                error_code=AppErrorCode.ERR_INVALID_DATE_STATE,
                message="Reviews can only be submitted for completed dates.",
            )

        # Verify 2-hour unlock delay
        if date_invitation.completed_at:
            time_since_completed = datetime.utcnow() - date_invitation.completed_at
            if time_since_completed < timedelta(hours=settings.REVIEW_UNLOCK_DELAY_HOURS):
                raise AppBaseException(
                    status_code=400,
                    error_code=AppErrorCode.ERR_REVIEW_LOCKED,
                    message="Review evaluation unlocks 2 hours after date completion.",
                )

        # Determine reviewee
        if reviewer_id == date_invitation.initiator_id:
            reviewee_id = date_invitation.recipient_id
        elif reviewer_id == date_invitation.recipient_id:
            reviewee_id = date_invitation.initiator_id
        else:
            raise AppBaseException(
                status_code=403,
                error_code=AppErrorCode.ERR_AUTH_REQUIRED,
                message="You are not a participant in this date.",
            )

        # Check existing review by this user for this date
        stmt = select(DateReview).where(
            and_(
                DateReview.date_invitation_id == date_invitation.id,
                DateReview.reviewer_id == reviewer_id,
            )
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing

        # Check 30-day pair collusion cooldown
        is_collusion = await cls.validate_30_day_pair_cooldown(
            db=db,
            user_a_id=reviewer_id,
            user_b_id=reviewee_id,
            current_date_id=date_invitation.id,
        )

        initial_status = (
            ReviewStatusEnum.COLLUSION_FLAGGED
            if is_collusion
            else ReviewStatusEnum.SUBMITTED_BLIND
        )

        review = DateReview(
            date_invitation_id=date_invitation.id,
            reviewer_id=reviewer_id,
            reviewee_id=reviewee_id,
            rating=rating,
            behavioral_tags=behavioral_tags,
            comment=comment,
            status=initial_status,
            is_collusion=is_collusion,
            created_at=datetime.utcnow(),
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)

        # Try to reveal reviews if both participants submitted
        await cls.try_reveal_reviews(db, date_invitation.id)
        await db.refresh(review)
        return review

    @classmethod
    async def try_reveal_reviews(
        cls,
        db: AsyncSession,
        date_invitation_id: int,
        force_timeout_reveal: bool = False,
    ) -> bool:
        """Reveals reviews if both parties have submitted or 48 hours have passed."""
        stmt = select(DateReview).where(DateReview.date_invitation_id == date_invitation_id)
        reviews = (await db.execute(stmt)).scalars().all()

        date_stmt = select(DateInvitation).where(DateInvitation.id == date_invitation_id)
        date_inv = (await db.execute(date_stmt)).scalar_one_or_none()
        if not date_inv:
            return False

        has_both_submitted = len(reviews) == 2
        is_past_48h = False
        if date_inv.completed_at:
            is_past_48h = (datetime.utcnow() - date_inv.completed_at) >= timedelta(
                hours=settings.REVIEW_AUTO_REVEAL_HOURS
            )

        should_reveal = has_both_submitted or is_past_48h or force_timeout_reveal

        if not should_reveal:
            return False

        now = datetime.utcnow()
        for review in reviews:
            if review.status == ReviewStatusEnum.SUBMITTED_BLIND:
                review.status = ReviewStatusEnum.PUBLISHED
                review.published_at = now

        await db.flush()

        for review in reviews:
            if review.status == ReviewStatusEnum.PUBLISHED and not review.is_collusion:
                await cls.recompute_user_reputation(db, review.reviewee_id)

                # Award points if rating >= 4.5
                if review.rating >= 4.5:
                    user_stmt = select(User).where(User.id == review.reviewee_id)
                    user = (await db.execute(user_stmt)).scalar_one_or_none()
                    if user:
                        idempotency = f"date_reward_{review.id}_{user.id}"
                        await PointsService.award_points(
                            db=db,
                            user=user,
                            amount=30,
                            reason=PointReasonEnum.HIGH_RATING_DATE,
                            idempotency_key=idempotency,
                            description=f"High rating ({review.rating}★) reward from date meetup",
                        )

        await db.commit()
        return True

    @classmethod
    async def recompute_user_reputation(cls, db: AsyncSession, user_id: int):
        """Recomputes Bayesian score using all eligible published reviews."""
        stmt = select(DateReview.rating).where(
            and_(
                DateReview.reviewee_id == user_id,
                DateReview.status == ReviewStatusEnum.PUBLISHED,
                DateReview.is_collusion.is_(False),
            )
        )
        ratings = (await db.execute(stmt)).scalars().all()

        new_score = cls.calculate_bayesian_score(list(ratings))
        user_stmt = select(User).where(User.id == user_id)
        user = (await db.execute(user_stmt)).scalar_one_or_none()
        if user:
            user.reputation_score = new_score
            user.reputation_count = len(ratings)
            await db.commit()
