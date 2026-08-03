"""Test de `engine/chart_image.py` — pur, aucune base/réseau, sur une série
synthétique (même construction que `tests/test_patterns.py:make_df`)."""
from engine.chart_image import render_candlestick_png
from tests.test_patterns import make_df, ramp


def test_render_candlestick_png_returns_a_real_png():
    df = make_df(ramp(100, 130, 60))
    png_bytes = render_candlestick_png(df, "Test — 60 séances")
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")  # signature PNG standard
    assert len(png_bytes) > 1000
