"""Sous-agent de collecte "détentions TIC" (Phase 7, extension) — détention
de titres du Trésor américain (Treasuries) par la France, d'après le
système Treasury International Capital (TIC) du département du Trésor
américain.

**Source corrigée après vérification en direct** — la première hypothèse de
ce module (une table HTML `slt-table5.html`) était fausse : cette URL
renvoie un vrai 404. Le fichier réellement servi est un **texte tabulé**
(`slt_table5.txt`, underscore, pas d'HTML/BeautifulSoup nécessaire) :

```
Country\t2026-05\t2026-04\t2026-03\t...
France\t393.1\t393.3\t393.0\t...
```

Piège réel trouvé en testant : **la colonne la plus à gauche est le mois le
plus récent** (ordre chronologique décroissant), pas la plus à droite comme
pour la plupart des séries temporelles habituelles de ce projet (FRED,
Eurostat) — ne pas supposer l'ordre inverse. Montants en **milliards de
dollars** (pas en millions). Serveur `ticdata.treasury.gov` constaté
flaky pendant le développement (mélange de réponses 200 rapides et de
timeouts sur des appels autrement identiques) — traiter tout échec réseau
comme transitoire, jamais fatal (`None` + log, comme les autres
collecteurs)."""

from __future__ import annotations

import csv
import io
import logging

import requests

from agents.orchestrator.types import CollectedItem

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 20
MAX_RETRIES = 2

TIC_URL = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt"
COUNTRY = "France"


def _get_with_retry(url: str) -> requests.Response | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            logger.warning("Tentative %s/%s échouée pour %s : %s", attempt, MAX_RETRIES, url, exc)
    return None


def _parse_amount(text: str) -> float | None:
    cleaned = text.strip().replace(",", "")
    if not cleaned or cleaned in ("N/A", "-", "..."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def fetch_tic_holdings(country: str, label: str, source_name: str, unit: str | None) -> CollectedItem | None:
    """Cherche la ligne du pays donné dans `slt_table5.txt` et renvoie sa
    valeur la plus récente. La ligne d'en-tête (`Country\\t2026-05\\t...`)
    donne les mois dans l'ordre décroissant — la **première** colonne de
    données est donc la plus récente. `None` (jamais d'exception) à la
    moindre étape en échec : page injoignable, en-tête/pays absent, valeur
    non numérique."""
    response = _get_with_retry(TIC_URL)
    if response is None:
        return None

    rows = list(csv.reader(io.StringIO(response.text), delimiter="\t"))
    header = next((row for row in rows if row and row[0].strip().lower() == "country"), None)
    if header is None:
        logger.warning("En-tête introuvable dans la réponse TIC (%s)", TIC_URL)
        return None

    country_row = next((row for row in rows if row and row[0].strip().lower() == country.lower()), None)
    if country_row is None:
        logger.warning("Pays « %s » absent du tableau TIC", country)
        return None

    for column_index in range(1, len(country_row)):
        amount = _parse_amount(country_row[column_index])
        if amount is not None:
            month_label = header[column_index].strip() if column_index < len(header) else ""
            return CollectedItem(
                label=label,
                value=amount,
                unit=unit,
                source_name=source_name,
                source_url=TIC_URL,
                observed_at=month_label,
            )
    logger.warning("Ligne « %s » trouvée mais aucune valeur numérique exploitable", country)
    return None


def collect_donnees_tic(db, engine, scope=None) -> list[tuple[str, list[CollectedItem]]]:
    """Ignore `db`/`engine`/`scope` — pays fixe (France) pour cette
    première version, comme le taux OAT dans `macro.py`. Source unique
    (aucun autre fournisseur public identifié pour cette donnée) → toujours
    `validated` à réputation 0.6 si la collecte réussit."""
    label = f"Détention de Treasuries US par {COUNTRY}"
    item = fetch_tic_holdings(COUNTRY, label=label, source_name="TIC (Trésor US)", unit="Md$")
    if item is None:
        logger.warning("Échec de la collecte TIC pour « %s » — indicateur ignoré ce cycle.", COUNTRY)
        return []
    return [(label, [item])]
