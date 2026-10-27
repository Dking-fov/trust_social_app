"""Base ORM model and mixins for SoulRed platform."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean


def get_utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class UUIDPrimaryKeyMixin:
    """Mixin that provides a standard 36-character UUID primary key."""

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
        nullable=False,
    )


class TimestampMixin:
    """Mixin that provides created_at and updated_at UTC timestamps."""

    created_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin that provides soft-deletion flags and timestamp."""

    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def soft_delete(self) -> None:
        """Mark record as soft-deleted."""
        self.is_deleted = True
        self.deleted_at = get_utc_now()
