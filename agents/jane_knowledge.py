"""Base de connaissances méthodologiques de Jane (Phase 7, rôle "veille
méthodologique") — même infrastructure que `agents/reports.py` (embedding
`mistral-embed` + pgvector), mais un concept différent : ici du savoir
général (définitions, méthodologies, mesures de performance...) plutôt que
des figures chartistes candidates (`ingestion.models.PatternCandidate`,
toujours backtestées avant tout usage).

`add_knowledge` déduplique par similarité cosinus avant d'écrire : la veille
continue (`agents/jane_veille.py`) va relire des sources qui se recoupent
dans le temps, sans quoi `jane_knowledge` grossirait indéfiniment de quasi-
doublons plutôt que de vraies additions."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import mistral_client
from ingestion.models import JaneKnowledge

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEED_PATH = REPO_ROOT / "Jane_Synthese_Connaissances.md"

# Distance cosinus pgvector (1 - similarité) en dessous de laquelle un
# nouveau contenu est considéré comme un quasi-doublon d'une entrée déjà
# présente (similarité ≥ 0.95) et donc ignoré plutôt qu'ajouté.
DEDUP_DISTANCE_THRESHOLD = 0.05


def _split_by_headers(lines: list[str], marker: str) -> list[tuple[str | None, list[str]]]:
    """Découpe `lines` à chaque ligne commençant par `marker`, en gardant le
    texte du titre (sans le marqueur) et les lignes qui suivent jusqu'au
    prochain titre du même niveau. Le tout premier groupe a `title=None`
    s'il y a du texte avant le premier titre de ce niveau."""
    sections: list[tuple[str | None, list[str]]] = []
    title: str | None = None
    buf: list[str] = []
    for line in lines:
        if line.startswith(marker):
            sections.append((title, buf))
            title = line[len(marker):].strip()
            buf = []
        else:
            buf.append(line)
    sections.append((title, buf))
    return sections


def chunk_markdown(text: str) -> list[tuple[str, str]]:
    """Découpe un document Markdown en chunks `(titre, contenu)` sur les
    en-têtes `## `, puis `### ` quand une section en contient (cas de la
    section 2 de `Jane_Synthese_Connaissances.md`, trop longue pour rester
    un seul chunk) — pur, aucune DB/réseau, testable sur un texte en dur."""
    lines = text.splitlines()
    chunks: list[tuple[str, str]] = []
    for level2_title, level2_lines in _split_by_headers(lines, "## "):
        if level2_title is None:
            continue  # texte avant le premier "## " (titre H1 du document) — pas un chunk exploitable
        sub_sections = _split_by_headers(level2_lines, "### ")
        if len(sub_sections) == 1:
            body = "\n".join(sub_sections[0][1]).strip()
            if body:
                chunks.append((level2_title, body))
            continue
        for sub_title, sub_lines in sub_sections:
            body = "\n".join(sub_lines).strip()
            if not body:
                continue
            chunks.append((sub_title or level2_title, body))
    return chunks


def add_knowledge(
    db: Session,
    content: str,
    source_name: str,
    source_url: str | None = None,
    dedup_distance_threshold: float = DEDUP_DISTANCE_THRESHOLD,
) -> JaneKnowledge | None:
    """Embedde `content` et l'ajoute à `jane_knowledge`, sauf si une entrée
    déjà présente en est un quasi-doublon (voir `DEDUP_DISTANCE_THRESHOLD`),
    auquel cas renvoie `None` sans rien écrire."""
    [embedding] = mistral_client.embed([content])

    distance = JaneKnowledge.embedding.cosine_distance(embedding).label("distance")
    nearest = db.execute(select(JaneKnowledge.id, distance).order_by(distance).limit(1)).first()
    if nearest is not None and nearest.distance <= dedup_distance_threshold:
        return None

    entry = JaneKnowledge(content=content, source_name=source_name, source_url=source_url, embedding=embedding)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def search_jane_knowledge(
    db: Session, query: str, limit: int = 5, query_embedding: list[float] | None = None
) -> list[JaneKnowledge]:
    """Recherche sémantique dans `jane_knowledge`, même principe que
    `agents/reports.py:search_reports` — utilisé par
    `agents.jane.second_opinion` pour injecter le savoir le plus pertinent
    au contexte de la décision en cours plutôt que le corpus figé du prompt
    système en entier.

    `query_embedding` est optionnel (calculé à partir de `query` si absent) —
    permet à un appelant qui interroge déjà plusieurs bases de connaissances
    pour la MÊME question (voir `agents.chat.answer_question`, qui interroge
    aussi `geopolitical_knowledge`) d'embedder `query` une seule fois plutôt
    qu'un appel Mistral redondant par base interrogée."""
    if query_embedding is None:
        [query_embedding] = mistral_client.embed([query])
    stmt = select(JaneKnowledge).order_by(JaneKnowledge.embedding.cosine_distance(query_embedding)).limit(limit)
    return db.execute(stmt).scalars().all()


def seed_from_markdown(db: Session, path: Path = DEFAULT_SEED_PATH) -> list[JaneKnowledge]:
    """Amorce `jane_knowledge` avec le contenu de `Jane_Synthese_Connaissances.md`
    (une fois) : découpe le document, embedde et écrit chaque chunk, en
    sautant les quasi-doublons (relançable sans dupliquer). Le reste du
    fichier — sections 1/3/4 — deviennent aussi des entrées : c'est le même
    corpus que celui recopié à la main dans `agents/prompts/
    jane_second_opinion_system.txt`, désormais interrogeable dynamiquement."""
    text = path.read_text(encoding="utf-8")
    created = []
    for title, body in chunk_markdown(text):
        entry = add_knowledge(db, content=body, source_name=f"{path.name} — {title}")
        if entry is not None:
            created.append(entry)
    return created


if __name__ == "__main__":
    import logging

    from ingestion.db import get_session_factory

    logging.basicConfig(level=logging.INFO)
    session_factory = get_session_factory()
    with session_factory() as session:
        created_entries = seed_from_markdown(session)
        print(f"{len(created_entries)} entrées ajoutées à jane_knowledge (quasi-doublons ignorés).")
