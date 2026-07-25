import json

import joblib
import numpy as np
import pytest

import engine.scoring as scoring
from engine.patterns.common import PatternMatch
from tests.test_patterns import make_df, ramp


class FakeModel:
    """Modèle factice — seul `predict_proba` compte pour `predict_confidence`."""

    def __init__(self, proba: float):
        self.proba = proba

    def predict_proba(self, X):
        return np.array([[1 - self.proba, self.proba]] * len(X))


class BrokenModel:
    """Modèle factice dont l'inférence échoue toujours — pour vérifier le repli."""

    def predict_proba(self, X):
        raise RuntimeError("boom")


@pytest.fixture(autouse=True)
def _reset_cache():
    scoring.reset_model_cache()
    yield
    scoring.reset_model_cache()


def _match(confidence=42.0, pattern_type="Bull Flag"):
    return PatternMatch(pattern_type=pattern_type, detected_at=None, confidence=confidence, context={})


def test_predict_confidence_falls_back_to_heuristic_when_no_model(monkeypatch, tmp_path):
    monkeypatch.setattr(scoring, "MODEL_GLOB", str(tmp_path / "confidence_xgb_*.joblib"))
    df = make_df(ramp(100, 150, 210))
    result = scoring.predict_confidence(_match(confidence=42.0), df, sector="Technologie")
    assert result == 42.0


def test_predict_confidence_falls_back_when_history_too_short(monkeypatch, tmp_path):
    model_path = tmp_path / "confidence_xgb_2099-01-01.joblib"
    joblib.dump(FakeModel(0.9), model_path)
    with open(tmp_path / "confidence_xgb_2099-01-01.meta.json", "w", encoding="utf-8") as f:
        json.dump({"feature_columns": ["pattern_type", "sector"]}, f)
    monkeypatch.setattr(scoring, "MODEL_GLOB", str(tmp_path / "confidence_xgb_*.joblib"))

    df = make_df(ramp(100, 110, 50))  # < 200 séances : pas de SMA200 -> features indisponibles
    result = scoring.predict_confidence(_match(confidence=17.0), df, sector="Technologie")
    assert result == 17.0


def test_predict_confidence_uses_model_when_available(monkeypatch, tmp_path):
    model_path = tmp_path / "confidence_xgb_2099-01-01.joblib"
    joblib.dump(FakeModel(0.83), model_path)
    with open(tmp_path / "confidence_xgb_2099-01-01.meta.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "feature_columns": [
                    "pattern_type",
                    "sector",
                    "relative_volume",
                    "atr_pct",
                    "market_trend",
                    "price_over_sma50",
                    "price_over_sma200",
                    "sma50_over_sma200",
                ]
            },
            f,
        )
    monkeypatch.setattr(scoring, "MODEL_GLOB", str(tmp_path / "confidence_xgb_*.joblib"))

    df = make_df(ramp(100, 150, 210))
    result = scoring.predict_confidence(_match(confidence=42.0), df, sector="Technologie")
    assert result == 83.0


def test_predict_confidence_falls_back_on_prediction_error(monkeypatch, tmp_path):
    model_path = tmp_path / "confidence_xgb_2099-01-01.joblib"
    joblib.dump(BrokenModel(), model_path)
    with open(tmp_path / "confidence_xgb_2099-01-01.meta.json", "w", encoding="utf-8") as f:
        json.dump({"feature_columns": ["pattern_type", "sector"]}, f)
    monkeypatch.setattr(scoring, "MODEL_GLOB", str(tmp_path / "confidence_xgb_*.joblib"))

    df = make_df(ramp(100, 150, 210))
    result = scoring.predict_confidence(_match(confidence=55.0), df, sector="Technologie")
    assert result == 55.0


def test_load_latest_model_picks_the_most_recent_by_filename(monkeypatch, tmp_path):
    for stamp, proba in [("2020-01-01", 0.1), ("2099-12-31", 0.9), ("2023-06-15", 0.5)]:
        joblib.dump(FakeModel(proba), tmp_path / f"confidence_xgb_{stamp}.joblib")
        with open(tmp_path / f"confidence_xgb_{stamp}.meta.json", "w", encoding="utf-8") as f:
            json.dump({"feature_columns": ["pattern_type", "sector"]}, f)
    monkeypatch.setattr(scoring, "MODEL_GLOB", str(tmp_path / "confidence_xgb_*.joblib"))

    model, _ = scoring.load_latest_model()
    assert model.proba == 0.9
