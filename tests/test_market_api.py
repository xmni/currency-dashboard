"""Integration tests: real HTTP requests through FastAPI into a real PostgreSQL."""

from fastapi.testclient import TestClient

from tests.conftest import FakeProvider, rate


def test_create_and_list_assets(client: TestClient) -> None:
    response = client.post("/assets", json={"code": "USD", "name": "US Dollar"})
    assert response.status_code == 201
    assert response.json()["code"] == "USD"

    assets = client.get("/assets").json()
    assert [a["code"] for a in assets] == ["USD"]


def test_duplicate_asset_is_rejected(client: TestClient) -> None:
    client.post("/assets", json={"code": "USD", "name": "US Dollar"})
    response = client.post("/assets", json={"code": "USD", "name": "Again"})
    assert response.status_code == 409


def test_invalid_asset_code_is_rejected(client: TestClient) -> None:
    response = client.post("/assets", json={"code": "us", "name": "lowercase"})
    assert response.status_code == 422


def test_sync_saves_rates_and_is_idempotent(
    client: TestClient, fake_provider: FakeProvider, usd_eur: None
) -> None:
    fake_provider.rates = [rate("2026-09-29", "0.87979"), rate("2026-09-30", "0.88085")]

    first = client.post("/rates/sync", params={"base": "USD", "quotes": "EUR"})
    assert first.json() == {"fetched": 2, "saved": 2}

    # Running again must not create duplicates
    client.post("/rates/sync", params={"base": "USD", "quotes": "EUR"})
    history = client.get("/rates/history", params={"base": "USD", "quote": "EUR"}).json()
    assert history["total"] == 2


def test_sync_updates_a_corrected_rate(
    client: TestClient, fake_provider: FakeProvider, usd_eur: None
) -> None:
    fake_provider.rates = [rate("2026-09-30", "0.88000")]
    client.post("/rates/sync", params={"base": "USD", "quotes": "EUR"})
    fake_provider.rates = [rate("2026-09-30", "0.88085")]
    client.post("/rates/sync", params={"base": "USD", "quotes": "EUR"})

    latest = client.get("/rates/latest", params={"base": "USD", "quote": "EUR"}).json()
    assert latest["rate"] == "0.8808500000"


def test_sync_unknown_asset_returns_404(client: TestClient, usd_eur: None) -> None:
    response = client.post("/rates/sync", params={"base": "USD", "quotes": "XYZ"})
    assert response.status_code == 404


def test_latest_returns_newest_rate(
    client: TestClient, fake_provider: FakeProvider, usd_eur: None
) -> None:
    fake_provider.rates = [rate("2026-09-29", "0.87979"), rate("2026-10-01", "0.88267")]
    client.post("/rates/sync", params={"base": "USD", "quotes": "EUR"})

    response = client.get("/rates/latest", params={"base": "USD", "quote": "EUR"})
    assert response.status_code == 200
    assert response.json()["rate_date"] == "2026-10-01"


def test_latest_without_data_returns_404(client: TestClient, usd_eur: None) -> None:
    response = client.get("/rates/latest", params={"base": "USD", "quote": "EUR"})
    assert response.status_code == 404


def test_history_filters_and_paginates(
    client: TestClient, fake_provider: FakeProvider, usd_eur: None
) -> None:
    fake_provider.rates = [
        rate("2026-09-28", "0.87744"),
        rate("2026-09-29", "0.87979"),
        rate("2026-09-30", "0.88085"),
        rate("2026-10-01", "0.88267"),
    ]
    client.post("/rates/sync", params={"base": "USD", "quotes": "EUR"})

    page = client.get(
        "/rates/history",
        params={"base": "USD", "quote": "EUR", "start": "2026-09-29", "limit": 2},
    ).json()
    assert page["total"] == 3
    assert [i["rate_date"] for i in page["items"]] == ["2026-10-01", "2026-09-30"]

    next_page = client.get(
        "/rates/history",
        params={"base": "USD", "quote": "EUR", "start": "2026-09-29", "limit": 2, "offset": 2},
    ).json()
    assert [i["rate_date"] for i in next_page["items"]] == ["2026-09-29"]


def test_history_rejects_reversed_dates(client: TestClient, usd_eur: None) -> None:
    response = client.get(
        "/rates/history",
        params={"base": "USD", "quote": "EUR", "start": "2026-10-01", "end": "2026-09-01"},
    )
    assert response.status_code == 422