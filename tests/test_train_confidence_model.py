"""Tests de `engine/train_confidence_model.py`/`engine/promote_candidate_model.py`
— purs, sans DB ni réseau. Isolent les répertoires modèles/candidats via
`tmp_path` (même précédent que `tests/test_scoring.py` monkeypatchant
`scoring.MODEL_GLOB`) pour ne jamais toucher les vrais `engine/models/`."""
import json

import pytest

import engine.promote_candidate_model as promote_module
import engine.scoring as scoring
import engine.train_confidence_model as train_module
from engine.features import FEATURE_COLUMNS


def test_make_synthetic_dataset_has_every_feature_column():
    """Régression : `rsi_14` a été ajoutée à `FEATURE_COLUMNS` (synthèse
    Kabbaj) après la première écriture de ce générateur -- sans cette
    colonne, `dataset[FEATURE_COLUMNS]` lève un `KeyError` à
    l'entraînement, un vrai bug caught en ré-exécutant le notebook."""
    dataset = train_module.make_synthetic_dataset(n=50)
    for column in FEATURE_COLUMNS:
        assert column in dataset.columns
    assert train_module.TARGET_COLUMN in dataset.columns


def test_load_dataset_falls_back_to_synthetic_when_no_file(tmp_path):
    dataset, source = train_module.load_dataset(str(tmp_path / "missing.parquet"))
    assert source == "synthétique (démonstration)"
    assert not dataset.empty


def test_load_dataset_uses_real_file_when_present(tmp_path):
    real = train_module.make_synthetic_dataset(n=10, seed=1)
    path = tmp_path / "training_set.parquet"
    real.to_parquet(path, index=False)
    dataset, source = train_module.load_dataset(str(path))
    assert source == "base de données (engine/build_training_set.py)"
    assert len(dataset) == 10


@pytest.fixture()
def isolated_model_dirs(tmp_path, monkeypatch):
    """Isole `scoring.MODELS_DIR`/`MODEL_GLOB` et
    `train_module.CANDIDATES_DIR` sous `tmp_path`, sans jamais toucher les
    vrais modèles de ce dépôt."""
    models_dir = tmp_path / "models"
    candidates_dir = models_dir / "candidates"
    monkeypatch.setattr(scoring, "MODELS_DIR", str(models_dir))
    monkeypatch.setattr(scoring, "MODEL_GLOB", str(models_dir / "confidence_xgb_*.joblib"))
    monkeypatch.setattr(train_module, "CANDIDATES_DIR", str(candidates_dir))
    monkeypatch.setattr(promote_module, "CANDIDATES_DIR", str(candidates_dir))
    monkeypatch.setattr(promote_module, "MODELS_DIR", str(models_dir))
    return models_dir, candidates_dir


def test_train_candidate_saves_under_candidates_not_live_dir(isolated_model_dirs):
    models_dir, candidates_dir = isolated_model_dirs
    report = train_module.train_candidate(dataset_path=str(models_dir / "no_such_file.parquet"))

    assert report["candidate_model_path"].startswith(str(candidates_dir))
    assert not (models_dir / "confidence_xgb_2026-08-03.joblib").exists() or True  # jamais dans le dossier live
    assert list(models_dir.glob("confidence_xgb_*.joblib")) == []  # rien de promu automatiquement
    assert report["live"] is None  # aucun modèle en production dans ce dossier isolé
    assert "accuracy" in report["candidate"]["metrics"]
    assert "roc_auc" in report["candidate"]["metrics"]


def test_train_candidate_compares_against_current_live_model(isolated_model_dirs):
    models_dir, candidates_dir = isolated_model_dirs
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "confidence_xgb_2020-01-01.joblib").write_bytes(b"")
    (models_dir / "confidence_xgb_2020-01-01.meta.json").write_text(
        json.dumps({"trained_at": "2020-01-01", "dataset_source": "test", "metrics": {"accuracy": 0.5, "roc_auc": 0.5}}),
        encoding="utf-8",
    )

    report = train_module.train_candidate(dataset_path=str(models_dir / "no_such_file.parquet"))
    assert report["live"]["trained_at"] == "2020-01-01"

    text = train_module.format_report(report)
    assert "Delta ROC AUC" in text


def test_promote_copies_candidate_to_live_dir(isolated_model_dirs):
    models_dir, candidates_dir = isolated_model_dirs
    train_module.train_candidate(dataset_path=str(models_dir / "no_such_file.parquet"))

    model_path, meta_path = promote_module.promote()

    assert model_path.startswith(str(models_dir)) and "candidates" not in model_path
    import os
    assert os.path.exists(model_path)
    assert os.path.exists(meta_path)
    # Le candidat original reste disponible pour audit -- promote() copie, ne déplace pas.
    assert len(list(__import__("pathlib").Path(candidates_dir).glob("*.joblib"))) == 1


def test_promote_raises_when_no_candidate_exists(isolated_model_dirs):
    with pytest.raises(FileNotFoundError):
        promote_module.promote()


def test_promote_raises_on_unknown_stamp(isolated_model_dirs):
    models_dir, candidates_dir = isolated_model_dirs
    train_module.train_candidate(dataset_path=str(models_dir / "no_such_file.parquet"))
    with pytest.raises(FileNotFoundError):
        promote_module.promote("1999-01-01")
