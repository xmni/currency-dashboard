"""Business rules for the market module. No HTTP and no SQL here."""

from datetime import date

from sqlalchemy.orm import Session

from app.market import repository
from app.market.models import Asset, RateSnapshot
from app.market.provider import RateProvider
from app.market.schemas import AssetCreate, SyncResult


class AssetNotFoundError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(f"Asset {code} not found")
        self.code = code


class AssetAlreadyExistsError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(f"Asset {code} already exists")
        self.code = code


class RateNotFoundError(Exception):
    pass


class InvalidDateRangeError(Exception):
    pass


def _require_assets(db: Session, codes: list[str]) -> None:
    for code in codes:
        if repository.get_asset_by_code(db, code) is None:
            raise AssetNotFoundError(code)


def list_assets(db: Session) -> list[Asset]:
    return repository.list_assets(db)


def create_asset(db: Session, data: AssetCreate) -> Asset:
    if repository.get_asset_by_code(db, data.code) is not None:
        raise AssetAlreadyExistsError(data.code)
    asset = repository.create_asset(db, data.code, data.name, data.kind)
    db.commit()
    return asset


def sync_rates(
    db: Session,
    provider: RateProvider,
    base: str,
    quotes: list[str],
    start: date | None = None,
    end: date | None = None,
) -> SyncResult:
    """Fetch rates from the provider and save them. Safe to run twice (upsert)."""
    if start and end and start > end:
        raise InvalidDateRangeError()
    _require_assets(db, [base, *quotes])

    rates = provider.fetch_rates(base, quotes, start, end)
    # Keep only pairs we track; providers sometimes return extra currencies
    wanted = set(quotes)
    rates = [r for r in rates if r.base == base and r.quote in wanted]

    saved = repository.upsert_rates(db, rates, source=provider.name)
    db.commit()
    return SyncResult(fetched=len(rates), saved=saved)


def get_latest_rate(db: Session, base: str, quote: str) -> RateSnapshot:
    _require_assets(db, [base, quote])
    rate = repository.get_latest_rate(db, base, quote)
    if rate is None:
        raise RateNotFoundError()
    return rate


def get_rate_history(
    db: Session,
    base: str,
    quote: str,
    start: date | None,
    end: date | None,
    limit: int,
    offset: int,
) -> tuple[list[RateSnapshot], int]:
    if start and end and start > end:
        raise InvalidDateRangeError()
    _require_assets(db, [base, quote])
    return repository.get_rate_history(db, base, quote, start, end, limit, offset)