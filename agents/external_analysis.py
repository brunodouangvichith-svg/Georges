"""Analyse technique en direct sur une entreprise hors du référentiel suivi
(`securities`, ~120 valeurs CAC 40/Mid 60) — ad hoc, pas une phase du
roadmap. Demandé directement par l'utilisateur : "n'importe quelle
entreprise mentionnée dans le chat" doit pouvoir recevoir une vraie analyse
technique (10 ans, yfinance), pas seulement un résumé d'actualité web.

Trois étapes, chacune pouvant échouer sans faire échouer `/chat` :
1. `extract_company_name` — un nom d'entreprise n'est pas déjà connu comme
   pour `agents/george_veille.py:BIOFUEL_RENEWABLE_GAS_COMPANIES` (liste
   fixe) : il faut l'extraire de la question libre. Tâche confiée au LLM
   (extraction courte et bornée — le point faible documenté ailleurs dans
   ce projet, `agents/chat.py`'s note sur `mistral-small-latest`, concerne
   l'énumération de longues listes structurées, pas ce genre d'extraction).
2. `resolve_ticker` — `yfinance.Search` (déjà une dépendance du projet,
   même source que tout l'univers suivi) plutôt qu'un service tiers
   supplémentaire. Filtre les bons de souscription (BSA/warrants) et
   préfère une cotation Paris quand elle existe, par cohérence avec le
   biais du référentiel déjà suivi — reste une heuristique, pas une
   garantie de tomber sur la bonne cotation à chaque fois.
3. `analyze_ticker` — réutilise `engine.detect.detect_all` tel quel (la
   même fonction pure qui détecte les figures sur l'univers suivi) contre
   un historique yfinance téléchargé à la volée, jamais contre les tables
   internes (`price_history_long` reste réservée à l'univers suivi).
   Volontairement SANS le modèle de confiance appris
   (`engine.scoring.predict_confidence`) : ce modèle est entraîné sur les
   patterns/résultats de l'univers CAC 40/Mid 60, son applicabilité à une
   entreprise quelconque n'est pas vérifiée — seule l'heuristique Phase 1
   (déjà intégrée à `PatternMatch.confidence` par chaque détecteur) est
   utilisée, universellement applicable par construction."""

from __future__ import annotations

import logging

import yfinance as yf

from agents import mistral_client
from engine.detect import detect_all
from engine.patterns import PatternMatch

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = (
    "Tu extrais uniquement le nom d'une entreprise/société mentionnée dans la question "
    "d'un investisseur, rien d'autre. Réponds avec le nom de l'entreprise seul, sans phrase, "
    "sans ponctuation superflue. Si aucune entreprise n'est mentionnée, réponds exactement : AUCUNE."
)

NO_COMPANY_MARKER = "AUCUNE"

_WARRANT_MARKERS = ("BSA", "WARRANT", "BON DE SOUSCRIPTION")


def extract_company_name(question: str) -> str | None:
    """`None` si le LLM ne trouve aucune entreprise dans la question, ou si
    l'appel échoue (`allow_fallback=False` : une extraction ratée doit
    dégrader silencieusement, pas retarder toute la réponse de plusieurs
    dizaines de secondes avec le repli DeepSeek — même principe que
    `agents/jane.py:reformulate_formal`)."""
    try:
        result = mistral_client.complete(
            EXTRACTION_SYSTEM_PROMPT, question, model=mistral_client.MODEL_SMALL, allow_fallback=False
        )
    except mistral_client.MistralUnavailableError:
        return None
    name = result.strip().strip(".\"'")
    if not name or name.upper() == NO_COMPANY_MARKER:
        return None
    return name


def resolve_ticker(company_name: str) -> str | None:
    """`None` si `yfinance` ne trouve rien d'exploitable — jamais une
    exception qui remonterait jusqu'à `/chat`."""
    try:
        candidates = yf.Search(company_name, max_results=8).quotes
    except Exception as err:  # noqa: BLE001 -- échec réseau/API yfinance, jamais bloquant
        logger.info("Résolution de ticker externe en échec pour %r : %s", company_name, err)
        return None

    equities = [
        c
        for c in candidates
        if c.get("quoteType") == "EQUITY"
        # `or ""` plutôt que `.get(key, "")` seul : couvre à la fois la clé
        # absente ET une valeur explicitement `None` (les deux se sont vues
        # en pratique dans de vraies réponses `yf.Search`) -- sans ça,
        # `.upper()` sur `None` lève `AttributeError`, hors du `try/except`
        # ci-dessus, ce qui ferait planter tout `/chat` au lieu de dégrader
        # vers `None` comme le promet la docstring du module.
        and not any(marker in (c.get("shortname") or "").upper() for marker in _WARRANT_MARKERS)
        and not any(marker in (c.get("longname") or "").upper() for marker in _WARRANT_MARKERS)
    ]
    if not equities:
        return None
    # Préfère une cotation Paris quand elle existe (cohérent avec le biais
    # du référentiel CAC 40/Mid 60 déjà suivi) ; sinon garde le premier
    # résultat, déjà trié par pertinence par yfinance lui-même.
    paris_listings = [c for c in equities if c.get("exchange") == "PAR"]
    chosen = (paris_listings or equities)[0]
    return chosen["symbol"]


def analyze_ticker(ticker: str) -> PatternMatch | None:
    """Télécharge 10 ans d'historique et lance la détection de figures
    (`engine.detect.detect_all`, pure, aucun accès DB) — renvoie la figure
    la plus confiante détectée, ou `None` si aucun historique exploitable
    ou aucune figure trouvée."""
    try:
        df = yf.Ticker(ticker).history(period="10y")
    except Exception as err:  # noqa: BLE001 -- échec réseau/API yfinance, jamais bloquant
        logger.info("Téléchargement yfinance en échec pour %r : %s", ticker, err)
        return None
    if df.empty:
        return None
    try:
        # Le renommage/sélection de colonnes est inclus dans ce `try` (pas
        # seulement `detect_all`) : un ticker inhabituel (fonds/ETF que
        # `resolve_ticker` n'a pas totalement exclu, historique partiel...)
        # peut renvoyer un DataFrame sans l'une des 5 colonnes attendues,
        # levant un `KeyError` ici plutôt qu'un `ValueError` dans
        # `detect_all` — les deux doivent dégrader vers `None`, jamais
        # remonter jusqu'à faire planter `/chat`.
        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
        matches = detect_all(df)
    except (KeyError, ValueError) as err:
        logger.warning("Analyse technique externe en échec pour %r : %s", ticker, err)
        return None
    if not matches:
        return None
    return max(matches, key=lambda m: m.confidence)
