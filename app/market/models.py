from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Asset(Base):
    """A currency or crypto asset, e.g. USD, EUR, BTC."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(10), default="fiat")  # "fiat" or "crypto"


class RateSnapshot(Base):
    """The price of 1 unit of `base` in `quote` on a given day, from one source."""

    __tablename__ = "rate_snapshots"
    # The unique constraint also creates an index on (base, quote, rate_date, source),
    # which Postgres uses for lookups by pair and date. No separate index needed.
    __table_args__ = (
        UniqueConstraint("base", "quote", "rate_date", "source", name="uq_rate_per_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    base: Mapped[str] = mapped_column(ForeignKey("assets.code"))
    quote: Mapped[str] = mapped_column(ForeignKey("assets.code"))
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 10))
    rate_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())