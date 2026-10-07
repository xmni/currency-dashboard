"""Unit tests for the Frankfurter adapter. No network: httpx.MockTransport fakes the API."""

from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.market.provider import FrankfurterProvider, ProviderError


def make_provider(handler: httpx.MockTransport) -> FrankfurterProvider:
    return FrankfurterProvider(httpx.Client(base_url="https://api.test", transport=handler))


def test_parses_rates_as_exact_decimals() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/rates"
        assert request.url.params["base"] == "USD"
        assert request.url.params["quotes"] == "EUR,GBP"
        assert request.url.params["from"] == "2026-09-28"
        return httpx.Response(
            200,
            text='[{"date":"2026-09-28","base":"USD","quote":"EUR","rate":0.87744},'
            '{"date":"2026-09-28","base":"USD","quote":"GBP","rate":0.75361}]',
        )

    provider = make_provider(httpx.MockTransport(handler))
    rates = provider.fetch_rates("USD", ["EUR", "GBP"], start=date(2026, 9, 28))

    assert len(rates) == 2
    assert rates[0].quote == "EUR"
    assert rates[0].rate == Decimal("0.87744")  # exact, no float rounding
    assert rates[0].rate_date == date(2026, 9, 28)


def test_http_error_becomes_provider_error() -> None:
    provider = make_provider(httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(ProviderError):
        provider.fetch_rates("USD", ["EUR"])


def test_unexpected_json_becomes_provider_error() -> None:
    provider = make_provider(
        httpx.MockTransport(lambda r: httpx.Response(200, text='{"error": "nope"}'))
    )
    with pytest.raises(ProviderError):
        provider.fetch_rates("USD", ["EUR"])