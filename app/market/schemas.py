from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AssetCreate(BaseModel):
    code: str = Field(min_length=3, max_length=10, pattern=r"^[A-Z0-9]+$")
    name: str = Field(min_length=1, max_length=100)
    kind: str = Field(default="fiat", pattern=r"^(fiat|crypto)$")


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    kind: str


class RateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    base: str
    quote: str
    rate: Decimal
    rate_date: date
    source: str


class RateHistoryOut(BaseModel):
    items: list[RateOut]
    total: int
    limit: int
    offset: int


class SyncResult(BaseModel):
    fetched: int
    saved: int