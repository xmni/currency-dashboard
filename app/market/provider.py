"""Adapter for the Frankfurter API (free, no API key, central bank rates).

Docs: https://frankfurter.dev
Each provider adapter turns an external API's format into our own `ProviderRate`,
so the rest of the app never depends on one provider's JSON shape.
"""

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

import httpx


class ProviderError(Exception):
    """The external provider failed or returned something we can't use."""


@dataclass(frozen=True)
class ProviderRate:
    base: str
    quote: str
    rate: Decimal
    rate_date: date


class RateProvider(Protocol):
    """What every market data provider must offer. Services depend on this, not on one API."""

    name: str

    def fetch_rates(
        self,
        base: str,
        quotes: list[str],
        start: date | None = None,
        end: date | None = None,
    ) -> list[ProviderRate]: ...


class FrankfurterProvider:
    name = "frankfurter"

    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def fetch_rates(
        self,
        base: str,
        quotes: list[str],
        start: date | None = None,
        end: date | None = None,
    ) -> list[ProviderRate]:
        """Latest rates when no dates are given, otherwise daily rates for the range."""
        params: dict[str, str] = {"base": base, "quotes": ",".join(quotes)}
        if start:
            params["from"] = start.isoformat()
        if end:
            params["to"] = end.isoformat()

        try:
            response = self.client.get("/v2/rates", params=params)
            response.raise_for_status()
            # parse_float=Decimal keeps exact values; float would introduce rounding errors
            data = json.loads(response.text, parse_float=Decimal)
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise ProviderError(f"Frankfurter request failed: {exc}") from exc

        try:
            return [
                ProviderRate(
                    base=item["base"],
                    quote=item["quote"],
                    rate=Decimal(item["rate"]),
                    rate_date=date.fromisoformat(item["date"]),
                )
                for item in data
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError(f"Unexpected Frankfurter response: {exc}") from exc