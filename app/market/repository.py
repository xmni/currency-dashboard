"""Database access for the market module. Only this file talks SQL."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.market.models import Asset, RateSnapshot
from app.market.provider import ProviderRate


def list_assets(db: Session) -> list[Asset]:
    return list(db.scalars(select(Asset).order_by(Asset.code)))


def get_asset_by_code(db: Session, code: str) -> Asset | None:
    return db.scalar(select(Asset).where(Asset.code == code))


def create_asset(db: Session, code: str, name: str, kind: str) -> Asset:
    asset = Asset(code=code, name=name, kind=kind)
    db.add(asset)
    db.flush()  # sends the INSERT so the asset gets its id; commit happens in the service
    return asset


def upsert_rates(db: Session, rates: list[ProviderRate], source: str) -> int:
    """Insert rates; if a rate for the same pair, day and source exists, update it."""
    if not rates:
        return 0
    rows = [
        {
            "base": r.base,
            "quote": r.quote,
            "rate": r.rate,
            "rate_date": r.rate_date,
            "source": source,
        }
        for r in rates
    ]
    stmt = insert(RateSnapshot).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_rate_per_day",
        set_={"rate": stmt.excluded.rate},
    )
    db.execute(stmt)
    return len(rows)


def get_latest_rate(db: Session, base: str, quote: str) -> RateSnapshot | None:
    stmt = (
        select(RateSnapshot)
        .where(RateSnapshot.base == base, RateSnapshot.quote == quote)
        .order_by(RateSnapshot.rate_date.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def get_rate_history(
    db: Session,
    base: str,
    quote: str,
    start: date | None,
    end: date | None,
    limit: int,
    offset: int,
) -> tuple[list[RateSnapshot], int]:
    """One page of rates, newest first, plus the total count for pagination."""
    conditions = [RateSnapshot.base == base, RateSnapshot.quote == quote]
    if start:
        conditions.append(RateSnapshot.rate_date >= start)
    if end:
        conditions.append(RateSnapshot.rate_date <= end)

    total = db.scalar(select(func.count()).select_from(RateSnapshot).where(*conditions)) or 0
    items = db.scalars(
        select(RateSnapshot)
        .where(*conditions)
        .order_by(RateSnapshot.rate_date.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(items), total