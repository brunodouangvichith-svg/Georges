"""Entraîne un modèle *candidat* de score de confiance (Phase 2) — ad hoc,
étend la Phase 2 avec un pipeline automatisable plutôt qu'un notebook
manuel. Logique portée depuis `engine/notebooks/train_confidence_model.ipynb`
(qui appelle désormais ce module plutôt que de dupliquer la logique).

Un candidat n'est **jamais** déployé automatiquement : il est sauvegardé sous
`engine/models/candidates/` (gitignoré, jamais lu par
`engine/scoring.py:latest_model_path` qui ne regarde que
`engine/models/*.joblib` directement) avec ses métriques comparées au modèle
actuellement en production. La promotion (copier le candidat retenu dans
`engine/models/`, puis le committer) est un geste humain délibéré — voir
`engine/promote_candidate_model.py`.

Usage :
    python -m engine.train_confidence_model
"""

import json
import os
from datetime import date

import numpy as np
import pandas as pd

from engine.backtest import TRAINING_HORIZON
from engine.features import CATEGORICAL_FEATURE_COLUMNS, FEATURE_COLUMNS, NUMERIC_FEATURE_COLUMNS
from engine.scoring import MODELS_DIR, latest_model_path

TARGET_COLUMN = f"success_{TRAINING_HORIZON}"
DATASET_PATH = os.path.join(os.path.dirname(__file__), "data", "training_set.parquet")
CANDIDATES_DIR = os.path.join(MODELS_DIR, "candidates")


def make_synthetic_dataset(n: int = 800, seed: int = 42) -> pd.DataFrame:
    """Jeu de données synthétique avec un signal latent volontairement
    simple (volume relatif + tendance de marché + position vs SMA50
    influencent la probabilité de succès), pour que l'entraînement ait
    quelque chose de réel à apprendre en l'absence de base peuplée — même
    génération que le notebook, portée ici pour que les deux restent
    identiques par construction plutôt que par copier-coller."""
    rng = np.random.default_rng(seed)
    pattern_types = [
        "Double Bottom", "Double Top", "Bull Flag", "Bear Flag",
        "Ascending Triangle", "Descending Triangle", "Breakout", "Breakdown",
        "Cup & Handle", "Head & Shoulders", "Inverse Head & Shoulders",
        "Falling Wedge", "Rising Wedge",
    ]
    bearish = {"Double Top", "Head & Shoulders", "Descending Triangle", "Rising Wedge", "Bear Flag", "Breakdown"}
    sectors = ["Technologie", "Finance", "Santé", "Industrie", "Énergie", "Consommation"]

    rows = []
    for _ in range(n):
        pattern = rng.choice(pattern_types)
        is_bear = pattern in bearish
        relative_volume = float(rng.lognormal(mean=0.0, sigma=0.4))
        atr = float(rng.uniform(0.01, 0.05))
        market_trend = float(rng.normal(0, 2))
        price_over_sma50 = float(rng.normal(0.98 if is_bear else 1.0, 0.03))
        price_over_sma200 = float(rng.normal(0.95 if is_bear else 1.02, 0.05))
        sma50_over_sma200 = float(rng.normal(0.99 if is_bear else 1.01, 0.03))
        # `rsi_14` ajoutée à `NUMERIC_FEATURE_COLUMNS` après la première
        # écriture de ce générateur synthétique (synthèse Kabbaj) — sans
        # cette colonne, `dataset[FEATURE_COLUMNS]` lève un `KeyError`
        # ("['rsi_14'] not in index"), un vrai bug caught en ré-exécutant le
        # notebook pour la première fois depuis cet ajout. Centrée de part et
        # d'autre de la zone neutre (50) selon le sens de la figure, comme
        # les autres features déjà biaisées ci-dessus.
        rsi_14 = float(np.clip(rng.normal(45.0 if is_bear else 55.0, 15.0), 0.0, 100.0))

        aligned_trend = -market_trend if is_bear else market_trend
        signal = (relative_volume - 1.0) + aligned_trend / 5 + (price_over_sma50 - 1.0) * 5
        prob_success = 1 / (1 + np.exp(-signal))
        success = bool(rng.random() < prob_success)
        ret = float(rng.normal(3 if success else -2, 2) * (-1 if is_bear else 1))

        rows.append({
            "pattern_type": pattern,
            "sector": rng.choice(sectors),
            "relative_volume": relative_volume,
            "atr_pct": atr,
            "market_trend": market_trend,
            "price_over_sma50": price_over_sma50,
            "price_over_sma200": price_over_sma200,
            "sma50_over_sma200": sma50_over_sma200,
            "rsi_14": rsi_14,
            f"return_{TRAINING_HORIZON}": ret,
            TARGET_COLUMN: success,
        })
    return pd.DataFrame(rows)


def load_dataset(dataset_path: str = DATASET_PATH) -> tuple[pd.DataFrame, str]:
    """Charge `training_set.parquet` s'il existe et contient au moins un
    exemple réel, sinon retombe sur le jeu synthétique — même garde-fou
    "fichier vide planterait sur dataset[FEATURE_COLUMNS]" documenté dans le
    notebook d'origine."""
    if os.path.exists(dataset_path):
        dataset = pd.read_parquet(dataset_path)
    else:
        dataset = pd.DataFrame()

    if not dataset.empty:
        return dataset, "base de données (engine/build_training_set.py)"
    return make_synthetic_dataset(), "synthétique (démonstration)"


def train_candidate(dataset_path: str = DATASET_PATH) -> dict:
    """Entraîne un pipeline scikit-learn + XGBClassifier sur le jeu de
    données disponible, sauvegarde le candidat sous `CANDIDATES_DIR`, et
    renvoie un rapport (métriques du candidat + du modèle actuellement en
    production, pour que la décision de promotion se base sur une vraie
    comparaison plutôt que sur le seul chiffre du candidat)."""
    # Imports scikit-learn/xgboost différés : ce module est importé par
    # `engine/notebooks/train_confidence_model.ipynb`, dont l'extra
    # `notebook` (pip install -e ".[dev,notebook]") est optionnel — les
    # fonctions pures ci-dessus (`make_synthetic_dataset`, `load_dataset`)
    # ne doivent pas exiger ces dépendances juste pour être important dans
    # des tests qui ne les exercent pas.
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import accuracy_score, roc_auc_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder
    from xgboost import XGBClassifier

    import joblib

    dataset, source = load_dataset(dataset_path)

    X = dataset[FEATURE_COLUMNS]
    y = dataset[TARGET_COLUMN].astype(bool)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    preprocessor = ColumnTransformer([
        ("numeric", SimpleImputer(strategy="median"), NUMERIC_FEATURE_COLUMNS),
        ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURE_COLUMNS),
    ])
    pipeline = Pipeline([
        ("preprocess", preprocessor),
        ("model", XGBClassifier(n_estimators=150, max_depth=3, learning_rate=0.1, eval_metric="logloss", random_state=42)),
    ])
    pipeline.fit(X_train, y_train)

    proba_test = pipeline.predict_proba(X_test)[:, 1]
    pred_test = proba_test >= 0.5
    accuracy = accuracy_score(y_test, pred_test)
    auc = roc_auc_score(y_test, proba_test)

    os.makedirs(CANDIDATES_DIR, exist_ok=True)
    stamp = date.today().isoformat()
    model_path = os.path.join(CANDIDATES_DIR, f"confidence_xgb_{stamp}.joblib")
    meta_path = os.path.join(CANDIDATES_DIR, f"confidence_xgb_{stamp}.meta.json")
    candidate_meta = {
        "trained_at": stamp,
        "training_horizon_sessions": TRAINING_HORIZON,
        "feature_columns": FEATURE_COLUMNS,
        "numeric_feature_columns": NUMERIC_FEATURE_COLUMNS,
        "categorical_feature_columns": CATEGORICAL_FEATURE_COLUMNS,
        "dataset_source": source,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "metrics": {"accuracy": accuracy, "roc_auc": auc},
    }

    joblib.dump(pipeline, model_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(candidate_meta, f, ensure_ascii=False, indent=2)

    live_meta = _current_live_meta()

    return {
        "candidate_model_path": model_path,
        "candidate_meta_path": meta_path,
        "candidate": candidate_meta,
        "live": live_meta,
    }


def _current_live_meta() -> dict | None:
    """Métadonnées du modèle actuellement en production (celui que
    `engine/scoring.py` chargerait réellement), `None` si aucun n'existe
    encore. Sert uniquement à comparer -- ne charge jamais ce modèle
    lui-même ici (pas besoin, seules les métriques comptent pour la
    comparaison)."""
    path = latest_model_path()
    if path is None:
        return None
    meta_path = path.removesuffix(".joblib") + ".meta.json"
    if not os.path.exists(meta_path):
        return None
    with open(meta_path, encoding="utf-8") as f:
        return json.load(f)


def format_report(report: dict) -> str:
    candidate = report["candidate"]
    live = report["live"]
    lines = [
        f"Candidat entraîné : {candidate['trained_at']} (source : {candidate['dataset_source']}, "
        f"{candidate['n_train']} train / {candidate['n_test']} test)",
        f"  accuracy={candidate['metrics']['accuracy']:.3f}  roc_auc={candidate['metrics']['roc_auc']:.3f}",
    ]
    if live is None:
        lines.append("Aucun modèle en production actuellement — ce serait le premier modèle réel.")
    else:
        lines.append(
            f"Modèle en production : {live['trained_at']} (source : {live['dataset_source']}, "
            f"{live.get('n_train', '?')} train / {live.get('n_test', '?')} test)"
        )
        lines.append(f"  accuracy={live['metrics']['accuracy']:.3f}  roc_auc={live['metrics']['roc_auc']:.3f}")
        delta_auc = candidate["metrics"]["roc_auc"] - live["metrics"]["roc_auc"]
        lines.append(f"Delta ROC AUC (candidat - production) : {delta_auc:+.3f}")
    lines.append(
        f"Candidat sauvegardé sous {report['candidate_model_path']} -- promotion manuelle requise "
        "(python -m engine.promote_candidate_model), jamais automatique."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    result = train_candidate()
    print(format_report(result))
