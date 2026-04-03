"""
GrimmGear — Database Models Base
Shared base class and mixins for all models.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class TimestampMixin:
    """Adds created_at and updated_at to any model."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )


class MediaItemMixin(TimestampMixin):
    """Common fields for all media items (movies, episodes, tracks, books)."""
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500))
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    overview: Mapped[Optional[str]] = mapped_column(String(5000), nullable=True)
    poster_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    fanart_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    monitored: Mapped[bool] = mapped_column(default=True)
    path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
