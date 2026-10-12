"""Add common currencies to the database. Safe to run many times.

Run with:  uv run python -m app.market.seed
"""

from sqlalchemy.dialects.postgresql import insert

from app.core.db import SessionLocal
from app.market.models import Asset

ASSETS = [
    ("USD", "US Dollar"),
    ("EUR", "Euro"),
    ("GBP", "British Pound"),
    ("JPY", "Japanese Yen"),
    ("CHF", "Swiss Franc"),
    ("CAD", "Canadian Dollar"),
    ("AUD", "Australian Dollar"),
    ("CNY", "Chinese Yuan"),
    ("TRY", "Turkish Lira"),
]


def main() -> None:
    rows = [{"code": code, "name": name, "kind": "fiat"} for code, name in ASSETS]
    with SessionLocal() as db:
        db.execute(insert(Asset).values(rows).on_conflict_do_nothing(index_elements=["code"]))
        db.commit()
    print(f"Seeded {len(rows)} assets")


if __name__ == "__main__":
    main()