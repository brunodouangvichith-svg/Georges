"""Contexte macro-économique pour `/chat` (ad hoc, pas une phase du
roadmap) — lit `macro_indicator_snapshots` (alimentée par
`agents/collectors/macro.py` [FRED/BCE/Frankfurter], `eurostat.py`
[chômage, inflation HICP zone euro] et `tic.py` via l'orchestrateur de la
Phase 7 MVP), jusqu'ici jamais consultée par `/chat` malgré son
alimentation régulière : une question macro ("quelle est l'inflation en
zone euro ?") tombait donc en repli web générique au lieu d'utiliser des
données déjà collectées et validées. Demandé directement par l'utilisateur
après l'avoir constaté via l'app réelle (George répondait ne pas avoir de
"source dédiée BCE/INSEE/Eurostat" alors que BCE et Eurostat sont déjà
collectées).

Pas de recherche sémantique ici (contrairement à jane_knowledge/
company_knowledge) : le nombre d'indicateurs suivis est petit (moins de
10), donc on renvoie systématiquement le dernier point connu de chacun
plutôt que de filtrer par pertinence — même logique "no relevance
threshold, let the prompt decide" que `connaissances_apprises`."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ingestion.models import MacroIndicatorSnapshot


def get_latest_macro_snapshots(db: Session) -> list[dict]:
    """Dernier point connu de chaque (indicateur, source) — potentiellement
    plusieurs entrées par indicateur quand plusieurs sources le suivent
    (ex. EUR/USD via FRED/BCE/Frankfurter), jamais moyennées/fusionnées :
    le recoupement multi-source (`agents/orchestrator/validation.py`) reste
    visible tel quel plutôt que masqué derrière un seul chiffre. Liste
    vide si `macro_indicator_snapshots` n'a encore jamais été peuplée
    (aucun cycle de collecte lancé) — jamais une exception.

    Utilise une window function (`ROW_NUMBER() OVER (PARTITION BY indicator,
    source_name ORDER BY created_at DESC)`), PAS "les N lignes les plus
    récentes toutes indicateurs confondus, dédupliquées en Python" — trouvé
    en `/code-review` : cette dernière approche fait silencieusement
    disparaître un indicateur à cadence lente (chômage/inflation Eurostat,
    mensuels ; `on_conflict_do_update` dans `agents/orchestrator/run.py` ne
    touche jamais `created_at`, donc sa ligne unique ne "vieillit" jamais)
    une fois que suffisamment de lignes plus récentes d'un indicateur à
    cadence rapide (FRED/BCE/Frankfurter, un nouveau `observed_at` à chaque
    cycle) l'ont fait sortir d'une fenêtre "top N global" — alors même que
    c'est toujours la donnée la plus récente connue pour cet indicateur, pas
    une donnée périmée. La window function isole chaque (indicateur, source)
    indépendamment : aucun ne peut jamais en éclipser un autre."""
    rank = (
        func.row_number()
        .over(
            partition_by=(MacroIndicatorSnapshot.indicator, MacroIndicatorSnapshot.source_name),
            order_by=MacroIndicatorSnapshot.created_at.desc(),
        )
        .label("rank")
    )
    ranked = select(MacroIndicatorSnapshot, rank).subquery()
    stmt = select(ranked).where(ranked.c.rank == 1)
    rows = db.execute(stmt).all()

    return [
        {
            "indicateur": row.indicator,
            "valeur": float(row.value),
            "unite": row.unit,
            "source": row.source_name,
            "observe_le": row.observed_at,
        }
        for row in rows
    ]
