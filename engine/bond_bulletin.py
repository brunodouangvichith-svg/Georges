"""Bulletin quotidien déterministe pour Obligataire Watch (ad hoc, pas une
phase du roadmap) — texte en français assemblé directement depuis les
chiffres réels de `engine/compute_bond_yields.py`, sans appel LLM. Conforme
à l'exigence explicite du cahier des charges : "la génération du bulletin
doit pouvoir fonctionner sans IA payante, avec une synthèse déterministe si
nécessaire" — ceci EST cette synthèse déterministe, pas un point de
passage temporaire avant un futur remplacement par Mistral.

Distingue strictement trois catégories, comme demandé : FAITS VÉRIFIÉS
(valeurs réellement observées), INTERPRÉTATION (lecture économique
plausible, jamais présentée comme certaine), CONSÉQUENCES POSSIBLES
(scénarios sur le financement de la dette et les taux immobiliers). Ne
prétend jamais qu'une hausse de l'OAT entraîne mécaniquement une hausse
identique des taux immobiliers — ceux-ci dépendent aussi des taux de swap,
du coût de financement des banques, de leurs marges et de la concurrence."""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from engine.compute_bond_yields import TRACKED_INSTRUMENTS, build_dashboard_summary
from ingestion.models import (
    BOND_INSTRUMENT_BUND_DE_10Y,
    BOND_INSTRUMENT_OAT_FR_10Y,
    BOND_INSTRUMENT_UST_US_10Y,
    BOND_INSTRUMENT_UST_US_2Y,
    BondAlertEvent,
)

INSTRUMENT_LABELS = {
    BOND_INSTRUMENT_OAT_FR_10Y: "OAT France 10 ans",
    BOND_INSTRUMENT_BUND_DE_10Y: "Bund Allemagne 10 ans",
    BOND_INSTRUMENT_UST_US_10Y: "Treasury US 10 ans",
    BOND_INSTRUMENT_UST_US_2Y: "Treasury US 2 ans",
}

# Instruments évoqués dans le cahier des charges sans source gratuite fiable
# identifiée (voir `docs/DATA_SOURCES.md`) — toujours mentionnés
# explicitement comme indisponibles plutôt que simplement omis.
UNAVAILABLE_INSTRUMENTS = ["Swap EUR 10 ans", "OAT France 2 ans", "OAT France 5 ans"]


def _format_card_line(card: dict) -> str:
    label = INSTRUMENT_LABELS.get(card["instrument"], card["instrument"])
    if card["value_pct"] is None:
        return f"- {label} : donnée indisponible (aucune collecte réussie à ce jour)."
    variations = card["variations_bps"]
    variation_parts = []
    for window_label in ("24h", "7j", "30j"):
        value = variations.get(window_label)
        variation_parts.append(f"{window_label} : {value:+.0f} pb" if value is not None else f"{window_label} : n/d")
    return (
        f"- {label} : {card['value_pct']:.2f}% (observé le {card['observed_at']}, "
        f"source {card['source_name']}) — variation {', '.join(variation_parts)}."
    )


def _recent_alerts_section(db: Session) -> str:
    stmt = select(BondAlertEvent).where(BondAlertEvent.status == "triggered").order_by(BondAlertEvent.triggered_at.desc())
    active = db.execute(stmt).scalars().all()
    if not active:
        return "Aucun seuil d'alerte actuellement franchi."
    lines = [f"- {event.message} (depuis le {event.triggered_at.date().isoformat()})" for event in active]
    return "\n".join(lines)


def generate_daily_bulletin(db: Session) -> str:
    """Assemble le bulletin complet. Pur côté formatage (aucune génération
    de texte non déterministe) — seules les données lues depuis la DB
    varient d'un appel à l'autre."""
    summary = build_dashboard_summary(db)
    cards_by_instrument = {card["instrument"]: card for card in summary["cards"]}
    today = datetime.date.today().isoformat()

    lines: list[str] = []
    lines.append(f"BULLETIN OBLIGATAIRE QUOTIDIEN — {today}")
    lines.append("")
    lines.append("=== FAITS VÉRIFIÉS ===")
    lines.append("")
    for instrument in TRACKED_INSTRUMENTS:
        lines.append(_format_card_line(cards_by_instrument[instrument]))
    lines.append("")
    spread = summary["spread_oat_bund_bps"]
    lines.append(
        f"- Spread OAT-Bund : {spread:+.0f} points de base." if spread is not None else "- Spread OAT-Bund : non calculable (une des deux valeurs manque)."
    )
    curve = summary["us_curve_slope_bps"]
    lines.append(
        f"- Pente courbe US (10 ans - 2 ans) : {curve:+.0f} points de base."
        if curve is not None
        else "- Pente courbe US (10 ans - 2 ans) : non calculable (une des deux valeurs manque)."
    )
    lines.append("")
    lines.append("Données non disponibles via les sources gratuites identifiées pour cette V1 :")
    for name in UNAVAILABLE_INSTRUMENTS:
        lines.append(f"- {name} : non disponible.")
    lines.append("")
    lines.append("Adjudications et annonces macroéconomiques (BCE, Fed, agences de notation) : non suivies dans cette V1.")
    lines.append("")
    lines.append("=== SEUILS D'ALERTE ===")
    lines.append("")
    lines.append(_recent_alerts_section(db))
    lines.append("")
    lines.append("=== INTERPRÉTATION ===")
    lines.append("")
    if spread is not None:
        if spread >= 100:
            lines.append(
                f"Un spread OAT-Bund de {spread:+.0f} points de base reste élevé au regard des niveaux "
                "observés avant 2023 (souvent inférieurs à 50 pb) — signe d'une prime de risque perçue "
                "plus importante sur la dette française relativement à l'Allemagne. Ceci est une lecture "
                "qualitative, pas une alerte de crise automatique."
            )
        else:
            lines.append(f"Le spread OAT-Bund ({spread:+.0f} pb) reste dans une fourchette resserrée.")
    if curve is not None:
        if curve < 0:
            lines.append(
                f"La courbe américaine 10 ans - 2 ans est inversée ({curve:+.0f} pb) — historiquement associée, "
                "mais pas systématiquement, à des périodes de ralentissement économique à venir aux "
                "États-Unis. Une inversion n'implique pas mécaniquement une récession."
            )
        else:
            lines.append(f"La courbe américaine 10 ans - 2 ans est positive ({curve:+.0f} pb), configuration usuelle.")
    lines.append("")
    lines.append("=== CONSÉQUENCES POSSIBLES ===")
    lines.append("")
    lines.append(
        "Un OAT 10 ans élevé renchérit le coût de refinancement de la dette publique française à chaque "
        "nouvelle émission — un scénario possible, pas un effet immédiat sur la dette déjà émise à taux fixe."
    )
    lines.append(
        "Les taux immobiliers ne suivent PAS mécaniquement l'OAT 10 ans de façon identique : ils dépendent "
        "aussi des taux de swap (souvent la référence directe des banques pour leurs crédits à taux fixe), "
        "du coût de financement propre de chaque banque, de leurs marges commerciales et de l'intensité de "
        "la concurrence entre établissements prêteurs. Une hausse de l'OAT est un facteur parmi d'autres, "
        "jamais une cause suffisante à elle seule."
    )
    lines.append("")
    lines.append("=== SOURCES ===")
    lines.append("")
    for instrument in TRACKED_INSTRUMENTS:
        card = cards_by_instrument[instrument]
        label = INSTRUMENT_LABELS.get(instrument, instrument)
        if card["source_name"] is not None:
            lines.append(f"- {label} : {card['source_name']} ({card['source_url']}), observé le {card['observed_at']}.")

    return "\n".join(lines)
