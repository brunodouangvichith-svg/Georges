"""Charge l'univers de départ (CAC 40 + CAC Mid 60) dans `securities`.

Usage :
    python -m ingestion.seed
"""

from sqlalchemy.dialects.postgresql import insert as pg_insert

from ingestion.cac40 import CAC40_SECURITIES
from ingestion.cac_mid60 import CAC_MID60_SECURITIES
from ingestion.db import get_engine
from ingestion.models import Security

# `theme` distingue les deux univers (utile pour filtrer/composer des
# paniers par la suite) — aucun symbole ne doit apparaître dans les deux
# listes, vérifié explicitement plutôt que laissé au dernier upsert gagnant
# silencieusement.
_UNIVERSES = [(CAC40_SECURITIES, "CAC 40"), (CAC_MID60_SECURITIES, "CAC Mid 60")]


def seed_securities() -> int:
    engine = get_engine()
    rows = [
        {"symbol": symbol, "name": name, "country": country, "currency": currency, "sector": sector, "theme": theme}
        for securities, theme in _UNIVERSES
        for symbol, name, country, currency, sector in securities
    ]
    symbols = [row["symbol"] for row in rows]
    duplicates = {s for s in symbols if symbols.count(s) > 1}
    if duplicates:
        raise ValueError(f"Symboles en double entre CAC 40 et CAC Mid 60 : {duplicates}")

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
