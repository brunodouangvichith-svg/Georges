"""Promeut un modèle *candidat* (`engine/train_confidence_model.py`) en
modèle de production — geste humain délibéré, jamais automatique (voir
CLAUDE.md, section "Auto-learn"). Copie (ne déplace pas — le candidat reste
disponible pour audit) le `.joblib`/`.meta.json` choisi de
`engine/models/candidates/` vers `engine/models/`, où
`engine/scoring.py:latest_model_path` le ramassera au prochain
`engine.run_detection`. Ne fait ni `git add`, ni commit, ni push : c'est à
l'appelant de vérifier le résultat puis de committer/pousser explicitement,
même discipline que le reste de ce projet pour toute action difficile à
annuler.

Usage :
    python -m engine.promote_candidate_model              # promeut le plus récent candidat
    python -m engine.promote_candidate_model 2026-08-15    # promeut un candidat daté précis
"""

import glob
import os
import shutil
import sys

from engine.scoring import MODELS_DIR
from engine.train_confidence_model import CANDIDATES_DIR


def _latest_candidate_stamp() -> str | None:
    paths = sorted(glob.glob(os.path.join(CANDIDATES_DIR, "confidence_xgb_*.joblib")))
    if not paths:
        return None
    filename = os.path.basename(paths[-1])
    return filename.removeprefix("confidence_xgb_").removesuffix(".joblib")


def promote(stamp: str | None = None) -> tuple[str, str]:
    """Copie le candidat `stamp` (ou le plus récent si omis) vers
    `engine/models/`. Lève `FileNotFoundError` si le candidat n'existe pas
    — jamais de promotion silencieuse d'un fichier manquant."""
    if stamp is None:
        stamp = _latest_candidate_stamp()
        if stamp is None:
            raise FileNotFoundError(f"Aucun candidat trouvé sous {CANDIDATES_DIR}.")

    candidate_model = os.path.join(CANDIDATES_DIR, f"confidence_xgb_{stamp}.joblib")
    candidate_meta = os.path.join(CANDIDATES_DIR, f"confidence_xgb_{stamp}.meta.json")
    if not os.path.exists(candidate_model) or not os.path.exists(candidate_meta):
        raise FileNotFoundError(f"Candidat {stamp} introuvable sous {CANDIDATES_DIR}.")

    os.makedirs(MODELS_DIR, exist_ok=True)
    live_model = os.path.join(MODELS_DIR, f"confidence_xgb_{stamp}.joblib")
    live_meta = os.path.join(MODELS_DIR, f"confidence_xgb_{stamp}.meta.json")
    shutil.copy2(candidate_model, live_model)
    shutil.copy2(candidate_meta, live_meta)
    return live_model, live_meta


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    model_path, meta_path = promote(arg)
    print(f"Promu : {model_path}")
    print(f"        {meta_path}")
    print("Reste à faire (geste humain, pas automatisé ici) : "
          "git add ces deux fichiers, commit, push -- c'est ce qui rend le "
          "modèle disponible au prochain workflow GitHub Actions programmé.")
