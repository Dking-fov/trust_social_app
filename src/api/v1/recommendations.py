"""Endpoints for daily 10-candidate quota cards, swipe actions, targeted top-10% discovery, and pack refresh."""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.user import User
from src.schemas.matching_schemas import (
    DailyDeckResponse,
    SwipeRequest,
    SwipeResultResponse,
    TargetedSearchRequest,
    CandidateCardDTO,
    CrushApplicationRequest,
    CrushApplicationResponse,
)
from src.schemas.points_schemas import RefreshPackResponse
from src.core.security import require_verified_user
from src.services.matching_service import MatchingService
from src.services.points_service import PointsService

router = APIRouter(prefix="/recommendations", tags=["Recommendation Engine & Swiping"])


@router.get("/daily-deck", response_model=DailyDeckResponse)
async def get_daily_deck_endpoint(
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves or refreshes daily 10-candidate quota cards for the current user."""
    return await MatchingService.get_or_create_daily_deck(db=db, user=current_user)


@router.post("/swipe", response_model=SwipeResultResponse)
async def swipe_candidate_endpoint(
    req: SwipeRequest,
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Processes swipe action (like or skip), consumes 1 card, and detects mutual double opt-in matches."""
    return await MatchingService.process_swipe(
        db=db,
        user=current_user,
        target_user_id=req.target_user_id,
        action=req.action,
    )


@router.post("/targeted-search", response_model=List[CandidateCardDTO])
async def targeted_search_endpoint(
    req: TargetedSearchRequest,
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Consumes 100 points to unlock city-filtered top 10% reputation candidate directory."""
    return await MatchingService.perform_targeted_search(
        db=db,
        user=current_user,
        req=req,
    )


@router.post("/crush-application", response_model=CrushApplicationResponse)
async def send_crush_endpoint(
    req: CrushApplicationRequest,
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Dispatches direct crush application with 200-char note straight to candidate priority inbox."""
    return await MatchingService.send_crush_application(
        db=db,
        user=current_user,
        req=req,
    )


@router.post("/refresh-pack", response_model=RefreshPackResponse)
async def refresh_pack_endpoint(
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Spends 30 points for 5 extra candidate cards (max 1 refresh per day)."""
    return await PointsService.purchase_extra_card_pack(
        db=db,
        user=current_user,
    )
