"""Test de `engine/chart_image.py` — pur, aucune base/réseau, sur une série
synthétique (même construction que `tests/test_patterns.py:make_df`)."""
from engine.chart_image import _build_overlay, render_candlestick_png
from tests.test_patterns import make_df, ramp


def test_render_candlestick_png_returns_a_real_png():
    df = make_df(ramp(100, 130, 60))
    png_bytes = render_candlestick_png(df, "Test — 60 séances")
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")  # signature PNG standard
    assert len(png_bytes) > 1000


def test_render_candlestick_png_with_pattern_context_still_produces_a_real_png():
    """Ne vérifie pas le contenu visuel (pas de rendu pixel-perfect ici),
    seulement que fournir un contexte de figure réel (résistance, points de
    marqueurs) ne fait pas planter le rendu -- mplfinance rejette `hlines`
    ou `addplot` mal formés silencieusement en erreur, pas en avertissement."""
    df = make_df(ramp(100, 130, 60))
    context = {"resistance": 120.0, "bottom_1": {"index": 10, "price": 101.0}}
    png_bytes = render_candlestick_png(df, "Breakout — confiance 70%", context=context)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(png_bytes) > 1000


def test_build_overlay_extracts_markers_and_hlines_from_context():
    context = {
        "bottom_1": {"index": 5, "price": 90.0},
        "bottom_2": {"index": 12, "price": 91.0},
        "resistance": {"index": 8, "price": 110.0},
    }
    markers, hlines = _build_overlay(context)
    assert set(markers) == {(5, 90.0), (12, 91.0), (8, 110.0)}
    assert hlines == [110.0]


def test_build_overlay_handles_scalar_level_and_neckline_points():
    context = {
        "resistance": 42.5,
        "neckline": {"price": 17.28, "points": [3, 9]},
    }
    markers, hlines = _build_overlay(context)
    assert set(markers) == {(3, 17.28), (9, 17.28)}
    assert set(hlines) == {42.5, 17.28}


def test_build_overlay_returns_empty_for_no_context():
    assert _build_overlay(None) == ([], [])
    assert _build_overlay({}) == ([], [])


def test_build_overlay_draws_lines_for_cup_and_handle_rims_and_handle_low():
    """Régression : un email de partage réel a montré un Cup & Handle sans
    aucune ligne tracée -- left_rim/right_rim/handle_low jouent le même rôle
    que resistance/support mais n'étaient pas reconnus comme des niveaux."""
    context = {
        "left_rim": {"index": 56, "price": 15.26},
        "right_rim": {"index": 111, "price": 14.88},
        "cup_bottom": {"index": 99, "price": 13.83},
        "handle_low": 14.4,
    }
    markers, hlines = _build_overlay(context)
    assert set(markers) == {(56, 15.26), (111, 14.88), (99, 13.83)}
    assert set(hlines) == {15.26, 14.88, 14.4}


def test_render_candlestick_png_with_take_profit_and_stop_loss():
    df = make_df(ramp(100, 130, 60))
    png_bytes = render_candlestick_png(df, "Test — niveaux", take_profit=140.0, stop_loss=95.0)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(png_bytes) > 1000
