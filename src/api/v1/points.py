"""Endpoints for points balance queries, transaction ledger history, and daily login rewards."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.user import User
from src.schemas.points_schemas import PointBalanceResponse, DailyCheckInResponse
from src.core.security import get_current_user
from src.services.points_service import PointsService

router = APIRouter(prefix="/points", tags=["Points Economy & Rewards"])


@router.get("/balance", response_model=PointBalanceResponse)
async def get_points_balance_endpoint(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves current point balance and paginated audit transaction ledger."""
    return await PointsService.get_user_balance_and_ledger(
        db=db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.post("/checkin", response_model=DailyCheckInResponse)
async def daily_login_checkin_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Claims daily login reward (+5 points, max once per calendar day)."""
    return await PointsService.daily_checkin(
        db=db,
        user=current_user,
    )
