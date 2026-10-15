"""Points economy transaction ledger with reason codes and idempotent operation tracking."""

import enum
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    Date,
    Enum as SAEnum,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class PointReasonEnum(str, enum.Enum):
    """Reason codes for in-app points ledger adjustments."""
    EDUCATION_VERIFIED = "EDUCATION_VERIFIED"      # +100
    DAILY_CHECKIN = "DAILY_CHECKIN"                # +5
    HIGH_RATING_DATE = "HIGH_RATING_DATE"          # +30 (review >= 4.5)
    CONFIRMED_REPORT = "CONFIRMED_REPORT"          # +50
    TARGETED_SEARCH = "TARGETED_SEARCH"            # -100
    EXTRA_PACK_REFRESH = "EXTRA_PACK_REFRESH"      # -30
    NO_SHOW_PENALTY = "NO_SHOW_PENALTY"            # -50


class PointLedger(Base):
    """Immutable financial ledger for point movements."""
    __tablename__ = "point_ledgers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[PointReasonEnum] = mapped_column(SAEnum(PointReasonEnum), nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(200), unique=True, index=True, nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class DailyActivityLog(Base):
    """Daily user activity log tracking daily check-in and refresh pack consumption."""
    __tablename__ = "daily_activity_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "log_date", name="uq_user_daily_activity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    log_date: Mapped[date] = mapped_column(Date, default=date.today, index=True, nullable=False)
    has_checked_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pack_refresh_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
