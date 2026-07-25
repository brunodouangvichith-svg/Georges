"""Charge l'univers de départ (CAC 40) dans `securities`.

Usage :
    python -m ingestion.seed
"""

from sqlalchemy.dialects.postgresql import insert as pg_insert

from ingestion.cac40 import CAC40_SECURITIES
from ingestion.db import get_engine
from ingestion.models import Security


def seed_securities() -> int:
    engine = get_engine()
    rows = [
        {"symbol": symbol, "name": name, "country": country, "currency": currency, "sector": sector, "theme": "CAC 40"}
        for symbol, name, country, currency, sector in CAC40_SECURITIES
    ]

    with engine.begin() as conn:
        stmt = pg_insert(Security).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Security.symbol],
            set_={
                "name": stmt.excluded.name,
                "country": stmt.excluded.country,
                "currency": stmt.excluded.currency,
                "sector": stmt.excluded.sector,
                "theme": stmt.excluded.theme,
            },
        )
        conn.execute(stmt)

    return len(rows)


if __name__ == "__main__":
    count = seed_securities()
    print(f"{count} valeurs chargées dans securities.")
