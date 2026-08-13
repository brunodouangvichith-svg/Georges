import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../core/indicators/technical_indicators.dart';
import '../../../models/price_bar.dart';

// `left_rim`/`right_rim`/`handle_low` (Cup & Handle) jouent le même rôle
// conceptuel que resistance/support sous un nom différent -- ajoutés pour
// que cette figure soit tracée en ligne elle aussi, pas seulement en
// marqueurs (bug réel trouvé en recevant un email de partage montrant un
// Cup & Handle sans aucune ligne, voir engine/chart_image.py et
// web/src/components/CandlestickChart.jsx, tenus en synchronisation).
const _levelKeys = {'resistance', 'support', 'left_rim', 'right_rim', 'handle_low'};

// Largeur minimale garantie par bougie quand `showIndicators` est actif --
// avec 10 ans de séances quotidiennes (~2500 bougies), les tasser dans la
// largeur du popup les rendrait illisibles (chevauchement complet sous le
// plancher de 2px de `_CandlestickPainter.bodyW`). Le canvas est donc élargi
// au lieu d'être tassé, et rendu défilable/zoomable via `InteractiveViewer`.
const _minCandleWidthWithIndicators = 4.0;

class _Overlay {
  final List<(int, double)> markers;
  final List<double> hlines;

  _Overlay(this.markers, this.hlines);
}

/// Superposition dérivée du `context` réel de `patterns_detected` (voir
/// engine/patterns/*.py côté backend), pas d'une heuristique locale sur les
/// chandeliers — port direct de web/src/components/CandlestickChart.jsx:
/// buildOverlay. Les points {index, price} (ou {points, price} pour une
/// ligne de cou) deviennent des marqueurs, les niveaux resistance/support
/// (bruts ou via un point) deviennent des lignes horizontales.
_Overlay _buildOverlay(Map<String, dynamic>? context, int indexOffset, int candleCount) {
  final markers = <(int, double)>[];
  final hlines = <double>[];
  if (context == null) return _Overlay(markers, hlines);

  for (final entry in context.entries) {
    final isLevelKey = _levelKeys.contains(entry.key);
    final value = entry.value;
    if (value is Map && value.containsKey('price')) {
      final price = (value['price'] as num).toDouble();
      if (value.containsKey('index')) {
        final relIdx = (value['index'] as num).toInt() - indexOffset;
        if (relIdx >= 0 && relIdx < candleCount) markers.add((relIdx, price));
      }
      if (value.containsKey('points')) {
        for (final idx in (value['points'] as List)) {
          final relIdx = (idx as num).toInt() - indexOffset;
          if (relIdx >= 0 && relIdx < candleCount) markers.add((relIdx, price));
        }
      }
      if (value.containsKey('points') || isLevelKey) hlines.add(price);
    } else if (isLevelKey && value is num) {
      hlines.add(value.toDouble());
    }
  }
  return _Overlay(markers, hlines);
}

/// Trace une série `List<double?>` en respectant ses trous (`null`) --
/// plusieurs segments plutôt qu'une interpolation qui masquerait la période
/// de chauffe de l'indicateur (même convention que les `NaN` côté backend :
/// jamais comblés par une valeur inventée).
void _drawSeries(
  Canvas canvas,
  List<double?> series,
  double Function(int) x,
  double Function(double) scaleY,
  Color color, {
  double strokeWidth = 1.5,
}) {
  final paint = Paint()
    ..color = color
    ..strokeWidth = strokeWidth
    ..style = PaintingStyle.stroke;
  Path? path;
  for (var i = 0; i < series.length; i++) {
    final v = series[i];
    if (v == null) {
      if (path != null) {
        canvas.drawPath(path, paint);
        path = null;
      }
      continue;
    }
    final point = Offset(x(i), scaleY(v));
    if (path == null) {
      path = Path()..moveTo(point.dx, point.dy);
    } else {
      path.lineTo(point.dx, point.dy);
    }
  }
  if (path != null) canvas.drawPath(path, paint);
}

class CandlestickChart extends StatefulWidget {
  const CandlestickChart({
    super.key,
    required this.candles,
    this.context,
    this.indexOffset = 0,
    this.takeProfit,
    this.stopLoss,
    this.width = 290,
    this.height = 150,
    this.showIndicators = false,
  });

  final List<PriceBar> candles;
  final Map<String, dynamic>? context;
  final int indexOffset;
  final double? takeProfit;
  final double? stopLoss;
  final double width;
  final double height;

  /// Superpose les bandes de Bollinger sur le prix et ajoute deux panneaux
  /// (MACD, Stochastique) sous le graphique, calculés côté client depuis
  /// `candles` (voir `core/indicators/technical_indicators.dart`). Off par
  /// défaut pour le petit graphique inline de `DecisionDetailScreen` (250
  /// séances, pas la place pour 3 panneaux) -- activé uniquement pour le
  /// popup plein écran (10 ans), seul endroit assez grand pour rester clair.
  /// Élargit aussi le canvas au nombre réel de bougies au lieu de le tasser
  /// dans `width` (voir `_minCandleWidthWithIndicators`), avec défilement
  /// initial sur les séances les plus récentes.
  final bool showIndicators;

  @override
  State<CandlestickChart> createState() => _CandlestickChartState();
}

class _CandlestickChartState extends State<CandlestickChart> {
  final _transformController = TransformationController();
  bool _scrolledToEnd = false;

  @override
  void dispose() {
    _transformController.dispose();
    super.dispose();
  }

  void _scrollToMostRecent(double contentWidth, double viewportWidth) {
    if (_scrolledToEnd || contentWidth <= viewportWidth) return;
    _scrolledToEnd = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _transformController.value = Matrix4.translationValues(-(contentWidth - viewportWidth), 0.0, 0.0);
    });
  }

  /// Plage de bougies actuellement visible dans le viewport (indices dans
  /// `candles`), déduite de la transformation courante de l'`InteractiveViewer`
  /// -- indispensable pour que l'échelle verticale des prix/MACD se
  /// recalcule sur ce qui est réellement affiché, pas sur les 10 ans entiers.
  /// Sans ça, une séance qui n'est pas proche d'un extrême historique
  /// s'affiche écrasée dans une fraction du panneau (bug réel trouvé en
  /// prévisualisant le graphique avec un historique synthétique de 600
  /// séances avant intégration).
  (int, int) _visibleCandleRange(double contentWidth, double viewportWidth, int candleCount) {
    Matrix4 inverse;
    try {
      inverse = Matrix4.inverted(_transformController.value);
    } catch (_) {
      return (0, candleCount - 1);
    }
    final topLeft = MatrixUtils.transformPoint(inverse, Offset.zero);
    final bottomRight = MatrixUtils.transformPoint(inverse, Offset(viewportWidth, 0));
    final step = contentWidth / candleCount;
    final start = (topLeft.dx / step).floor().clamp(0, candleCount - 1);
    final end = (bottomRight.dx / step).ceil().clamp(0, candleCount - 1);
    return (start, end);
  }

  @override
  Widget build(BuildContext context) {
    if (widget.candles.isEmpty) {
      return SizedBox(
        width: widget.width,
        height: widget.height,
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Text(
              "Pas d'historique de prix disponible pour ce titre.",
              textAlign: TextAlign.center,
              style: TextStyle(color: Theme.of(context).colorScheme.outline, fontSize: 12),
            ),
          ),
        ),
      );
    }

    final overlay = _buildOverlay(widget.context, widget.indexOffset, widget.candles.length);
    final showIndicators = widget.showIndicators;

    final contentWidth = showIndicators
        ? math.max(widget.width, widget.candles.length * _minCandleWidthWithIndicators)
        : widget.width;

    BollingerResult? bollinger;
    MacdResult? macdResult;
    StochasticResult? stochResult;
    if (showIndicators) {
      final closes = widget.candles.map((c) => c.close).toList();
      bollinger = bollingerBands(closes);
      macdResult = macd(closes);
      stochResult = stochasticOscillator(widget.candles);
    }

    // Répartition verticale : prix dominant, MACD/Stochastique en support --
    // même hiérarchie que les plateformes de trading de référence (prix en
    // haut, oscillateurs en bandeaux plus fins dessous).
    const gap = 6.0;
    final pricePanelHeight = showIndicators ? (widget.height - 2 * gap) * 0.56 : widget.height;
    final subPanelHeight = showIndicators ? (widget.height - 2 * gap) * 0.22 : 0.0;
    final totalContentHeight = showIndicators ? widget.height : widget.height;

    if (!showIndicators) {
      return SizedBox(
        width: widget.width,
        height: widget.height,
        child: InteractiveViewer(
          minScale: 1.0,
          maxScale: 4.0,
          child: CustomPaint(
            size: Size(contentWidth, pricePanelHeight),
            painter: _CandlestickPainter(
              candles: widget.candles,
              overlay: overlay,
              bollinger: null,
              visibleRange: null,
              takeProfit: widget.takeProfit,
              stopLoss: widget.stopLoss,
              positiveColor: Colors.green.shade400,
              negativeColor: Colors.red.shade400,
              accentColor: Theme.of(context).colorScheme.primary,
              textDimColor: Theme.of(context).colorScheme.outline,
              bollingerColor: Colors.purple.shade300,
            ),
          ),
        ),
      );
    }

    _scrollToMostRecent(contentWidth, widget.width);
    final positiveColor = Colors.green.shade400;
    final negativeColor = Colors.red.shade400;
    final accentColor = Theme.of(context).colorScheme.primary;
    final textDimColor = Theme.of(context).colorScheme.outline;
    final signalLineColor = Colors.orange.shade400;
    final bollingerColor = Colors.purple.shade300;

    return SizedBox(
      width: widget.width,
      height: totalContentHeight,
      // Pincer-zoomer / glisser sur la courbe -- `InteractiveViewer` gère
      // nativement le pinch/pan sans toucher aux `CustomPainter`. Le contenu
      // (`contentWidth`) dépasse largement `width` : `constrained: false`
      // l'autorise, et `boundaryMargin` par défaut (zéro) empêche tout
      // survol au-delà des données réelles dans les deux sens.
      child: InteractiveViewer(
        transformationController: _transformController,
        constrained: false,
        minScale: 1.0,
        maxScale: 4.0,
        // Se reconstruit à chaque pan/zoom pour recalculer `visibleRange` et
        // ainsi réajuster l'échelle verticale des panneaux sur ce qui est
        // réellement visible (voir `_visibleCandleRange`).
        child: AnimatedBuilder(
          animation: _transformController,
          builder: (context, _) {
            final visibleRange = _visibleCandleRange(contentWidth, widget.width, widget.candles.length);
            return SizedBox(
              width: contentWidth,
              height: totalContentHeight,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CustomPaint(
                    size: Size(contentWidth, pricePanelHeight),
                    painter: _CandlestickPainter(
                      candles: widget.candles,
                      overlay: overlay,
                      bollinger: bollinger,
                      visibleRange: visibleRange,
                      takeProfit: widget.takeProfit,
                      stopLoss: widget.stopLoss,
                      positiveColor: positiveColor,
                      negativeColor: negativeColor,
                      accentColor: accentColor,
                      textDimColor: textDimColor,
                      bollingerColor: bollingerColor,
                    ),
                  ),
                  SizedBox(height: gap),
                  CustomPaint(
                    size: Size(contentWidth, subPanelHeight),
                    painter: _MacdPainter(
                      macdResult: macdResult!,
                      candleCount: widget.candles.length,
                      visibleRange: visibleRange,
                      positiveColor: positiveColor,
                      negativeColor: negativeColor,
                      macdLineColor: accentColor,
                      signalLineColor: signalLineColor,
                      textDimColor: textDimColor,
                    ),
                  ),
                  SizedBox(height: gap),
                  CustomPaint(
                    size: Size(contentWidth, subPanelHeight),
                    painter: _StochasticPainter(
                      stochResult: stochResult!,
                      candleCount: widget.candles.length,
                      percentKColor: accentColor,
                      percentDColor: signalLineColor,
                      textDimColor: textDimColor,
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

class _CandlestickPainter extends CustomPainter {
  _CandlestickPainter({
    required this.candles,
    required this.overlay,
    required this.bollinger,
    required this.visibleRange,
    required this.takeProfit,
    required this.stopLoss,
    required this.positiveColor,
    required this.negativeColor,
    required this.accentColor,
    required this.textDimColor,
    required this.bollingerColor,
  });

  final List<PriceBar> candles;
  final _Overlay overlay;
  final BollingerResult? bollinger;
  /// Indices `(start, end)` inclusifs de la plage actuellement visible dans
  /// le viewport -- `null` pour le petit graphique inline (pas de défilement,
  /// toute la série est "visible"). Utilisé uniquement pour le calcul de
  /// l'échelle verticale (voir `paint`), jamais pour limiter le tracé
  /// lui-même (les bougies hors-écran restent dessinées, `InteractiveViewer`
  /// se charge de ne rendre que la portion visible).
  final (int, int)? visibleRange;
  final double? takeProfit;
  final double? stopLoss;
  final Color positiveColor;
  final Color negativeColor;
  final Color accentColor;
  final Color textDimColor;
  final Color bollingerColor;

  static const _pad = 14.0;
  static const _tagWidth = 45.0;
  static const _tagHeight = 16.0;

  @override
  void paint(Canvas canvas, Size size) {
    final width = size.width;
    final height = size.height;
    final plotW = width - 50;
    final lastClose = candles.last.close;

    // Échelle verticale calculée sur la plage VISIBLE, pas sur les 10 ans
    // entiers -- sinon une séance qui n'est pas proche d'un extrême
    // historique s'affiche écrasée dans une fraction du panneau dès que le
    // graphique est plus large que le viewport (voir `visibleRange`).
    final rangeStart = visibleRange?.$1 ?? 0;
    final rangeEnd = visibleRange?.$2 ?? (candles.length - 1);
    final visibleCandles = candles.sublist(rangeStart, rangeEnd + 1);
    final bollingerVals = bollinger == null
        ? const <double>[]
        : [
            ...bollinger!.upper.sublist(rangeStart, rangeEnd + 1),
            ...bollinger!.lower.sublist(rangeStart, rangeEnd + 1),
          ].whereType<double>();
    final levels = [...overlay.hlines, lastClose, ?takeProfit, ?stopLoss];
    final allVals = <double>[
      ...visibleCandles.expand((c) => [c.high, c.low]),
      ...levels,
      ...bollingerVals,
    ];
    final max = allVals.reduce((a, b) => a > b ? a : b);
    final min = allVals.reduce((a, b) => a < b ? a : b);
    final range = (max - min) == 0 ? 1 : (max - min);
    double scaleY(double v) => _pad + (height - 2 * _pad) * (1 - (v - min) / range);

    final step = plotW / candles.length;
    final bodyW = (step * 0.55).clamp(2.0, double.infinity);
    double x(int i) => i * step + step / 2;

    if (bollinger != null) {
      final bandColor = bollingerColor.withValues(alpha: 0.5);
      _drawSeries(canvas, bollinger!.upper, x, scaleY, bandColor, strokeWidth: 1);
      _drawSeries(canvas, bollinger!.lower, x, scaleY, bandColor, strokeWidth: 1);
      _drawSeries(canvas, bollinger!.mid, x, scaleY, bollingerColor.withValues(alpha: 0.8), strokeWidth: 1);
    }

    if (takeProfit != null) _drawPriceTag(canvas, width, scaleY(takeProfit!), takeProfit!, positiveColor, plotW);
    if (stopLoss != null) _drawPriceTag(canvas, width, scaleY(stopLoss!), stopLoss!, negativeColor, plotW);

    for (var i = 0; i < candles.length; i++) {
      final c = candles[i];
      final up = c.close >= c.open;
      final color = up ? positiveColor : negativeColor;
      final yOpen = scaleY(c.open);
      final yClose = scaleY(c.close);
      final yHigh = scaleY(c.high);
      final yLow = scaleY(c.low);
      final bodyTop = yOpen < yClose ? yOpen : yClose;
      final bodyH = (yClose - yOpen).abs().clamp(1.0, double.infinity);

      canvas.drawLine(Offset(x(i), yHigh), Offset(x(i), yLow), Paint()..color = color..strokeWidth = 1);
      canvas.drawRect(Rect.fromLTWH(x(i) - bodyW / 2, bodyTop, bodyW, bodyH), Paint()..color = color);
    }

    for (final level in overlay.hlines) {
      _drawDashedLine(canvas, Offset(0, scaleY(level)), Offset(plotW, scaleY(level)), accentColor, 1.5, [5, 4]);
    }
    for (final (idx, price) in overlay.markers) {
      canvas.drawCircle(Offset(x(idx), scaleY(price)), 2.5, Paint()..color = accentColor);
    }

    _drawDashedLine(
        canvas, Offset(0, scaleY(lastClose)), Offset(width - 46, scaleY(lastClose)), textDimColor, 1, [2, 3]);
    _drawTag(canvas, width, scaleY(lastClose), lastClose.toStringAsFixed(2), Colors.grey.shade800, textDimColor);

    if (bollinger != null) _drawPanelLabel(canvas, 'Bollinger (20, 2)', bollingerColor);
  }

  void _drawPriceTag(Canvas canvas, double width, double y, double level, Color color, double plotW) {
    _drawDashedLine(canvas, Offset(0, y), Offset(width - 46, y), color, 1.3, [4, 3]);
    _drawTag(canvas, width, y, level.toStringAsFixed(2), color, Colors.white);
  }

  void _drawTag(Canvas canvas, double width, double y, String label, Color fill, Color textColor) {
    final rect = Rect.fromLTWH(width - _tagWidth - 1, y - _tagHeight / 2, _tagWidth, _tagHeight);
    canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(3)), Paint()..color = fill);
    final painter = TextPainter(
      text: TextSpan(
        text: label,
        style: TextStyle(color: textColor, fontSize: 9.5, fontWeight: FontWeight.w600, fontFamily: 'monospace'),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    painter.paint(canvas, Offset(rect.center.dx - painter.width / 2, rect.center.dy - painter.height / 2));
  }

  void _drawDashedLine(Canvas canvas, Offset start, Offset end, Color color, double strokeWidth, List<double> pattern) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = strokeWidth;
    final totalLength = (end - start).distance;
    if (totalLength == 0) return;
    final direction = (end - start) / totalLength;
    var covered = 0.0;
    var dashOn = true;
    var patternIndex = 0;
    while (covered < totalLength) {
      final dashLength = pattern[patternIndex % pattern.length];
      final segmentEnd = (covered + dashLength).clamp(0.0, totalLength);
      if (dashOn) {
        canvas.drawLine(start + direction * covered, start + direction * segmentEnd, paint);
      }
      covered = segmentEnd;
      dashOn = !dashOn;
      patternIndex++;
    }
  }

  @override
  bool shouldRepaint(covariant _CandlestickPainter oldDelegate) =>
      oldDelegate.candles != candles ||
      oldDelegate.overlay != overlay ||
      oldDelegate.bollinger != bollinger ||
      oldDelegate.visibleRange != visibleRange;
}

/// Petite étiquette de coin commune aux 3 panneaux (prix/MACD/Stochastique)
/// -- identifie le panneau une fois le graphique élargi et défilable, où le
/// contexte visuel (titre au-dessus du prix) n'est plus forcément visible
/// simultanément avec les panneaux du bas.
void _drawPanelLabel(Canvas canvas, String label, Color color) {
  final painter = TextPainter(
    text: TextSpan(text: label, style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w600)),
    textDirection: TextDirection.ltr,
  )..layout();
  painter.paint(canvas, const Offset(4, 2));
}

class _MacdPainter extends CustomPainter {
  _MacdPainter({
    required this.macdResult,
    required this.candleCount,
    required this.visibleRange,
    required this.positiveColor,
    required this.negativeColor,
    required this.macdLineColor,
    required this.signalLineColor,
    required this.textDimColor,
  });

  final MacdResult macdResult;
  final int candleCount;
  /// Voir `_CandlestickPainter.visibleRange` -- même rôle : borne le calcul
  /// de l'échelle (`bound`), jamais le tracé lui-même.
  final (int, int)? visibleRange;
  final Color positiveColor;
  final Color negativeColor;
  final Color macdLineColor;
  final Color signalLineColor;
  final Color textDimColor;

  static const _pad = 6.0;

  @override
  void paint(Canvas canvas, Size size) {
    final width = size.width;
    final height = size.height;
    final plotW = width - 50;

    final rangeStart = visibleRange?.$1 ?? 0;
    final rangeEnd = visibleRange?.$2 ?? (candleCount - 1);
    final visibleVals = [
      ...macdResult.macdLine.sublist(rangeStart, rangeEnd + 1),
      ...macdResult.signalLine.sublist(rangeStart, rangeEnd + 1),
      ...macdResult.histogram.sublist(rangeStart, rangeEnd + 1),
    ].whereType<double>();
    // Échelle symétrique autour de zéro, calculée sur la plage VISIBLE
    // (même raison que `_CandlestickPainter` ci-dessus) -- la ligne du zéro
    // (référence documentée dans George_AnalyseTechnique_Kabbaj_Synthese.md
    // §4) reste toujours centrée verticalement, quel que soit le
    // déséquilibre haussier/baissier de la période affichée.
    final bound = visibleVals.isEmpty ? 1.0 : visibleVals.map((v) => v.abs()).reduce((a, b) => a > b ? a : b);
    final range = bound == 0 ? 1.0 : bound * 2;
    double scaleY(double v) => _pad + (height - 2 * _pad) * (1 - (v + bound) / range);

    final step = plotW / candleCount;
    double x(int i) => i * step + step / 2;
    final barW = (step * 0.55).clamp(1.0, double.infinity);

    _drawDashedZeroLine(canvas, scaleY(0), plotW, textDimColor);

    for (var i = 0; i < macdResult.histogram.length; i++) {
      final v = macdResult.histogram[i];
      if (v == null) continue;
      final color = v >= 0 ? positiveColor : negativeColor;
      final yZero = scaleY(0);
      final yVal = scaleY(v);
      final top = yVal < yZero ? yVal : yZero;
      final h = (yZero - yVal).abs().clamp(0.5, double.infinity);
      canvas.drawRect(Rect.fromLTWH(x(i) - barW / 2, top, barW, h), Paint()..color = color.withValues(alpha: 0.7));
    }

    _drawSeries(canvas, macdResult.macdLine, x, scaleY, macdLineColor);
    _drawSeries(canvas, macdResult.signalLine, x, scaleY, signalLineColor);
    _drawPanelLabel(canvas, 'MACD (12, 26, 9)', macdLineColor);
  }

  void _drawDashedZeroLine(Canvas canvas, double y, double plotW, Color color) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1;
    var covered = 0.0;
    while (covered < plotW) {
      final segEnd = math.min(covered + 4, plotW);
      canvas.drawLine(Offset(covered, y), Offset(segEnd, y), paint);
      covered += 7;
    }
  }

  @override
  bool shouldRepaint(covariant _MacdPainter oldDelegate) =>
      oldDelegate.macdResult != macdResult || oldDelegate.visibleRange != visibleRange;
}

class _StochasticPainter extends CustomPainter {
  _StochasticPainter({
    required this.stochResult,
    required this.candleCount,
    required this.percentKColor,
    required this.percentDColor,
    required this.textDimColor,
  });

  final StochasticResult stochResult;
  final int candleCount;
  final Color percentKColor;
  final Color percentDColor;
  final Color textDimColor;

  static const _pad = 6.0;

  @override
  void paint(Canvas canvas, Size size) {
    final width = size.width;
    final height = size.height;
    final plotW = width - 50;

    // Échelle fixe 0-100, comme toute lecture standard du stochastique --
    // pas dérivée des données affichées, pour que les zones de
    // surachat/survente (STOCHASTIC_OVERBOUGHT/OVERSOLD, engine/confidence.py)
    // restent toujours aux mêmes hauteurs relatives.
    double scaleY(double v) => _pad + (height - 2 * _pad) * (1 - v / 100);

    final step = plotW / candleCount;
    double x(int i) => i * step + step / 2;

    for (final level in [stochasticOversold, stochasticOverbought]) {
      _drawDashedLine(canvas, Offset(0, scaleY(level)), Offset(plotW, scaleY(level)), textDimColor, [4, 3]);
    }

    _drawSeries(canvas, stochResult.percentK, x, scaleY, percentKColor);
    _drawSeries(canvas, stochResult.percentD, x, scaleY, percentDColor);
    _drawPanelLabel(canvas, 'Stochastique (14, 3)', percentKColor);
  }

  void _drawDashedLine(Canvas canvas, Offset start, Offset end, Color color, List<double> pattern) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1;
    final totalLength = (end - start).distance;
    if (totalLength == 0) return;
    final direction = (end - start) / totalLength;
    var covered = 0.0;
    var dashOn = true;
    var patternIndex = 0;
    while (covered < totalLength) {
      final dashLength = pattern[patternIndex % pattern.length];
      final segmentEnd = (covered + dashLength).clamp(0.0, totalLength);
      if (dashOn) {
        canvas.drawLine(start + direction * covered, start + direction * segmentEnd, paint);
      }
      covered = segmentEnd;
      dashOn = !dashOn;
      patternIndex++;
    }
  }

  @override
  bool shouldRepaint(covariant _StochasticPainter oldDelegate) => oldDelegate.stochResult != stochResult;
}
