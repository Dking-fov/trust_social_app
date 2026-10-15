"""Schemas for points balances, transaction histories, daily check-ins, and paid features."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from src.models.points import PointReasonEnum


class PointTransactionDTO(BaseModel):
    """Point ledger transaction item."""
    id: int
    amount: int
    balance_after: int
    reason: PointReasonEnum
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PointBalanceResponse(BaseModel):
    """User points balance overview and recent transactions."""
    balance: int
    transactions: List[PointTransactionDTO] = []


class DailyCheckInResponse(BaseModel):
    """Daily login check-in reward confirmation."""
    success: bool
    points_awarded: int
    current_balance: int
    message: str


class RefreshPackResponse(BaseModel):
    """Extra recommendation card pack acquisition result."""
    success: bool
    cards_added: int
    points_deducted: int
    remaining_balance: int
    refreshed_count_today: int
    message: str
