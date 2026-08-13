import 'dart:math' as math;

import '../../models/price_bar.dart';

/// Port Dart des indicateurs de `engine/patterns/common.py` (mêmes formules,
/// mêmes fenêtres par défaut) — calculés ici côté client, pas via un appel
/// réseau supplémentaire : le popup plein écran (`_showChartPopup`,
/// `decision_detail_screen.dart`) a déjà l'historique complet de 10 ans en
/// mémoire (`securityFullPricesProvider`), donc tout ce qu'il faut pour
/// tracer MACD/Bollinger/Stochastique est déjà là. Sert uniquement au rendu
/// du graphique mobile — le score de confiance de George reste calculé
/// côté backend (`engine/confidence.py`), jamais recalculé ici.
///
/// Convention `List<double?>` : `null` tant que la fenêtre nécessaire n'est
/// pas encore pleine, même rôle que les `None`/`NaN` du backend Python.

const macdFastSpan = 12;
const macdSlowSpan = 26;
const macdSignalSpan = 9;
const bollingerWindow = 20;
const bollingerNumStd = 2.0;
const stochasticWindow = 14;
const stochasticSignalWindow = 3;
const stochasticOversold = 20.0;
const stochasticOverbought = 80.0;

/// Moyenne mobile exponentielle (lissage `2/(span+1)`) — même récursion que
/// `pandas.Series.ewm(span=span, adjust=False)` : calculée dès le premier
/// point, seulement masquée (`null`) tant que moins de `span` observations
/// ont contribué, pour rester alignée avec `engine/patterns/common.py:ema`.
List<double?> ema(List<double> values, int span) {
  final result = List<double?>.filled(values.length, null);
  if (values.isEmpty) return result;
  final alpha = 2.0 / (span + 1);
  var prev = values[0];
  for (var i = 0; i < values.length; i++) {
    prev = i == 0 ? values[0] : alpha * values[i] + (1 - alpha) * prev;
    if (i >= span - 1) result[i] = prev;
  }
  return result;
}

class MacdResult {
  final List<double?> macdLine;
  final List<double?> signalLine;
  final List<double?> histogram;
  MacdResult(this.macdLine, this.signalLine, this.histogram);
}

/// MACD (Gerald Appel) : ligne = EMA(`fast`) - EMA(`slow`), signal = EMA
/// (`signal`) de la ligne, histogramme = ligne - signal.
MacdResult macd(
  List<double> closes, {
  int fast = macdFastSpan,
  int slow = macdSlowSpan,
  int signal = macdSignalSpan,
}) {
  final emaFast = ema(closes, fast);
  final emaSlow = ema(closes, slow);
  final macdLine = List<double?>.generate(
    closes.length,
    (i) => (emaFast[i] != null && emaSlow[i] != null) ? emaFast[i]! - emaSlow[i]! : null,
  );

  // EMA de la ligne MACD elle-même, mais celle-ci ne démarre qu'à l'indice
  // `slow - 1` (première valeur non nulle) -- on la compacte pour appliquer
  // `ema` sur une série sans trou, puis on redistribue aux bons indices.
  final compact = <double>[];
  final compactIdx = <int>[];
  for (var i = 0; i < macdLine.length; i++) {
    final v = macdLine[i];
    if (v != null) {
      compact.add(v);
      compactIdx.add(i);
    }
  }
  final signalCompact = ema(compact, signal);
  final signalLine = List<double?>.filled(closes.length, null);
  for (var j = 0; j < compactIdx.length; j++) {
    signalLine[compactIdx[j]] = signalCompact[j];
  }

  final histogram = List<double?>.generate(
    closes.length,
    (i) => (macdLine[i] != null && signalLine[i] != null) ? macdLine[i]! - signalLine[i]! : null,
  );
  return MacdResult(macdLine, signalLine, histogram);
}

class BollingerResult {
  final List<double?> mid;
  final List<double?> upper;
  final List<double?> lower;
  BollingerResult(this.mid, this.upper, this.lower);
}

/// Bandes de Bollinger : médiane = SMA(`window`), bandes = médiane ±
/// `numStd` écarts-types (population, cohérent avec `ddof=0` côté backend).
BollingerResult bollingerBands(
  List<double> closes, {
  int window = bollingerWindow,
  double numStd = bollingerNumStd,
}) {
  final n = closes.length;
  final mid = List<double?>.filled(n, null);
  final upper = List<double?>.filled(n, null);
  final lower = List<double?>.filled(n, null);
  for (var i = window - 1; i < n; i++) {
    final w = closes.sublist(i - window + 1, i + 1);
    final mean = w.reduce((a, b) => a + b) / window;
    final variance = w.map((v) => (v - mean) * (v - mean)).reduce((a, b) => a + b) / window;
    final std = math.sqrt(variance);
    mid[i] = mean;
    upper[i] = mean + numStd * std;
    lower[i] = mean - numStd * std;
  }
  return BollingerResult(mid, upper, lower);
}

class StochasticResult {
  final List<double?> percentK;
  final List<double?> percentD;
  StochasticResult(this.percentK, this.percentD);
}

/// Oscillateur stochastique (George Lane) : %K = 100 * (clôture - plus bas
/// sur `window`) / (plus haut - plus bas sur `window`), %D = SMA(`signal`)
/// de %K. `null` si `high == low` sur toute la fenêtre (amplitude nulle).
StochasticResult stochasticOscillator(
  List<PriceBar> candles, {
  int window = stochasticWindow,
  int signal = stochasticSignalWindow,
}) {
  final n = candles.length;
  final percentK = List<double?>.filled(n, null);
  for (var i = window - 1; i < n; i++) {
    final w = candles.sublist(i - window + 1, i + 1);
    final lowestLow = w.map((c) => c.low).reduce(math.min);
    final highestHigh = w.map((c) => c.high).reduce(math.max);
    final denom = highestHigh - lowestLow;
    percentK[i] = denom == 0 ? null : 100 * (candles[i].close - lowestLow) / denom;
  }
  final percentD = List<double?>.filled(n, null);
  for (var i = signal - 1; i < n; i++) {
    final w = percentK.sublist(i - signal + 1, i + 1);
    if (w.any((v) => v == null)) continue;
    percentD[i] = w.map((v) => v!).reduce((a, b) => a + b) / signal;
  }
  return StochasticResult(percentK, percentD);
}
