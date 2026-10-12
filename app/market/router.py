"""HTTP layer for the market module: parse requests, call the service, map errors."""

from collections.abc import Iterator
from datetime import date
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.market import service
from app.market.models import Asset, RateSnapshot
from app.market.provider import FrankfurterProvider, ProviderError, RateProvider
from app.market.schemas import AssetCreate, AssetOut, RateHistoryOut, RateOut, SyncResult

router = APIRouter(tags=["market"])

DbSession = Annotated[Session, Depends(get_db)]


def get_provider() -> Iterator[RateProvider]:
    """FastAPI dependency: a provider with its own HTTP client, closed after the request."""
    with httpx.Client(
        base_url=settings.frankfurter_base_url,
        timeout=settings.http_timeout_seconds,
    ) as client:
        yield FrankfurterProvider(client)


Provider = Annotated[RateProvider, Depends(get_provider)]
CurrencyCode = Annotated[str, Query(min_length=3, max_length=10, pattern=r"^[A-Z0-9]+$")]


@router.get("/assets", response_model=list[AssetOut])
def list_assets(db: DbSession) -> list[Asset]:
    return service.list_assets(db)


@router.post("/assets", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
def create_asset(data: AssetCreate, db: DbSession) -> Asset:
    try:
        return service.create_asset(db, data)
    except service.AssetAlreadyExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/rates/sync", response_model=SyncResult)
def sync_rates(
    db: DbSession,
    provider: Provider,
    base: CurrencyCode,
    quotes: Annotated[str, Query(description="Comma-separated codes, e.g. EUR,GBP")],
    start: date | None = None,
    end: date | None = None,
) -> SyncResult:
    quote_list = [q.strip().upper() for q in quotes.split(",") if q.strip()]
    if not quote_list:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "quotes must not be empty")
    try:
        return service.sync_rates(db, provider, base, quote_list, start, end)
    except service.AssetNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except service.InvalidDateRangeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "start is after end") from exc
    except ProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Market data provider failed") from exc


@router.get("/rates/latest", response_model=RateOut)
def latest_rate(db: DbSession, base: CurrencyCode, quote: CurrencyCode) -> RateSnapshot:
    try:
        return service.get_latest_rate(db, base, quote)
    except service.AssetNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except service.RateNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No rate stored for this pair") from exc


@router.get("/rates/history", response_model=RateHistoryOut)
def rate_history(
    db: DbSession,
    base: CurrencyCode,
    quote: CurrencyCode,
    start: date | None = None,
    end: date | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RateHistoryOut:
    try:
        items, total = service.get_rate_history(db, base, quote, start, end, limit, offset)
    except service.AssetNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except service.InvalidDateRangeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "start is after end") from exc
    return RateHistoryOut(
        items=[RateOut.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )