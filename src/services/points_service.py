"""Points economy engine: idempotent transactions, ledger operations, daily check-in, and card refreshes."""

from datetime import date, datetime
from typing import Optional, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.user import User
from src.models.points import PointLedger, DailyActivityLog, PointReasonEnum
from src.models.matching import CandidateDeck
from src.core.exceptions import (
    InsufficientPointsException,
    DailyRefreshLimitException,
)
from src.schemas.points_schemas import (
    PointBalanceResponse,
    PointTransactionDTO,
    DailyCheckInResponse,
    RefreshPackResponse,
)

settings = get_settings()


class PointsService:
    """Encapsulates all points ledger mutations and balance management."""

    @classmethod
    async def award_points(
        cls,
        db: AsyncSession,
        user: User,
        amount: int,
        reason: PointReasonEnum,
        idempotency_key: Optional[str] = None,
        description: Optional[str] = None,
    ) -> PointLedger:
        """Idempotently adds points to user balance and records in immutable ledger."""
        if idempotency_key:
            stmt = select(PointLedger).where(PointLedger.idempotency_key == idempotency_key)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return existing

        user.points_balance += amount
        ledger = PointLedger(
            user_id=user.id,
            amount=amount,
            balance_after=user.points_balance,
            reason=reason,
            idempotency_key=idempotency_key,
            description=description,
            created_at=datetime.utcnow(),
        )
        db.add(ledger)
        await db.commit()
        await db.refresh(user)
        await db.refresh(ledger)
        return ledger

    @classmethod
    async def deduct_points(
        cls,
        db: AsyncSession,
        user: User,
        amount: int,
        reason: PointReasonEnum,
        idempotency_key: Optional[str] = None,
        description: Optional[str] = None,
    ) -> PointLedger:
        """Deducts points if sufficient balance exists, recording in immutable ledger."""
        if user.points_balance < amount:
            raise InsufficientPointsException()

        if idempotency_key:
            stmt = select(PointLedger).where(PointLedger.idempotency_key == idempotency_key)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return existing

        user.points_balance -= amount
        ledger = PointLedger(
            user_id=user.id,
            amount=-amount,
            balance_after=user.points_balance,
            reason=reason,
            idempotency_key=idempotency_key,
            description=description,
            created_at=datetime.utcnow(),
        )
        db.add(ledger)
        await db.commit()
        await db.refresh(user)
        await db.refresh(ledger)
        return ledger

    @classmethod
    async def get_user_balance_and_ledger(
        cls,
        db: AsyncSession,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> PointBalanceResponse:
        """Fetches current balance and paginated audit ledger."""
        user_stmt = select(User).where(User.id == user_id)
        u_res = await db.execute(user_stmt)
        user = u_res.scalar_one_or_none()
        current_balance = user.points_balance if user else 0

        ledger_stmt = (
            select(PointLedger)
            .where(PointLedger.user_id == user_id)
            .order_by(PointLedger.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        l_res = await db.execute(ledger_stmt)
        entries = l_res.scalars().all()

        return PointBalanceResponse(
            balance=current_balance,
            transactions=[
                PointTransactionDTO(
                    id=e.id,
                    amount=e.amount,
                    balance_after=e.balance_after,
                    reason=e.reason,
                    description=e.description,
                    created_at=e.created_at,
                )
                for e in entries
            ],
        )

    @classmethod
    async def daily_checkin(
        cls,
        db: AsyncSession,
        user: User,
    ) -> DailyCheckInResponse:
        """Awards +5 points once per calendar day."""
        today = date.today()
        stmt = select(DailyActivityLog).where(
            and_(DailyActivityLog.user_id == user.id, DailyActivityLog.log_date == today)
        )
        result = await db.execute(stmt)
        log = result.scalar_one_or_none()

        if log and log.has_checked_in:
            return DailyCheckInResponse(
                success=False,
                points_awarded=0,
                current_balance=user.points_balance,
                message="Already checked in today. Come back tomorrow!",
            )

        if not log:
            log = DailyActivityLog(user_id=user.id, log_date=today, has_checked_in=True)
            db.add(log)
        else:
            log.has_checked_in = True

        idempotency = f"daily_checkin_{user.id}_{today.isoformat()}"
        await cls.award_points(
            db=db,
            user=user,
            amount=5,
            reason=PointReasonEnum.DAILY_CHECKIN,
            idempotency_key=idempotency,
            description=f"Daily login reward for {today.isoformat()}",
        )
        await db.commit()

        return DailyCheckInResponse(
            success=True,
            points_awarded=5,
            current_balance=user.points_balance,
            message="Daily login reward claimed successfully (+5 points).",
        )

    @classmethod
    async def purchase_extra_card_pack(
        cls,
        db: AsyncSession,
        user: User,
    ) -> RefreshPackResponse:
        """Exchanges 30 points for 5 extra candidate cards (max 1 refresh per day)."""
        today = date.today()
        stmt = select(DailyActivityLog).where(
            and_(DailyActivityLog.user_id == user.id, DailyActivityLog.log_date == today)
        )
        result = await db.execute(stmt)
        activity_log = result.scalar_one_or_none()

        if activity_log and activity_log.pack_refresh_count >= 1:
            raise DailyRefreshLimitException()

        cost = settings.EXTRA_PACK_COST_POINTS
        cards_to_add = settings.EXTRA_PACK_CARD_COUNT

        if user.points_balance < cost:
            raise InsufficientPointsException(
                message=f"Insufficient points ({user.points_balance} available, {cost} required). Earn points via check-in or dates."
            )

        # Deduct points
        idempotency = f"refresh_pack_{user.id}_{today.isoformat()}"
        await cls.deduct_points(
            db=db,
            user=user,
            amount=cost,
            reason=PointReasonEnum.EXTRA_PACK_REFRESH,
            idempotency_key=idempotency,
            description="Purchased 5 extra candidate recommendation cards",
        )

        # Update activity log
        if not activity_log:
            activity_log = DailyActivityLog(
                user_id=user.id, log_date=today, pack_refresh_count=1
            )
            db.add(activity_log)
        else:
            activity_log.pack_refresh_count += 1

        # Increment remaining cards in today's deck
        deck_stmt = select(CandidateDeck).where(
            and_(CandidateDeck.user_id == user.id, CandidateDeck.deck_date == today)
        )
        deck_res = await db.execute(deck_stmt)
        deck = deck_res.scalar_one_or_none()
        if deck:
            deck.remaining_cards += cards_to_add
            deck.refreshed_count += 1

        await db.commit()

        return RefreshPackResponse(
            success=True,
            cards_added=cards_to_add,
            points_deducted=cost,
            remaining_balance=user.points_balance,
            refreshed_count_today=activity_log.pack_refresh_count,
            message="Successfully purchased 5 additional recommendation cards.",
        )
