import 'package:flutter/material.dart';

import '../../../models/price_bar.dart';

const _levelKeys = {'resistance', 'support'};

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

class CandlestickChart extends StatelessWidget {
  const CandlestickChart({
    super.key,
    required this.candles,
    this.context,
    this.indexOffset = 0,
    this.takeProfit,
    this.stopLoss,
    this.width = 290,
    this.height = 150,
  });

  final List<PriceBar> candles;
  final Map<String, dynamic>? context;
  final int indexOffset;
  final double? takeProfit;
  final double? stopLoss;
  final double width;
  final double height;

  @override
  Widget build(BuildContext context) {
    if (candles.isEmpty) {
      return SizedBox(
        width: width,
        height: height,
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

    final overlay = _buildOverlay(this.context, indexOffset, candles.length);
    return SizedBox(
      width: width,
      height: height,
      // Pincer-zoomer sur la courbe des prix — `InteractiveViewer` gère
      // nativement le pinch/pan sans toucher au `CustomPainter`, contenu
      // borné à sa taille d'origine (pas de `boundaryMargin`) pour qu'un
      // zoom arrière ne fasse jamais apparaître de vide autour du graphique.
      child: InteractiveViewer(
        minScale: 1.0,
        maxScale: 4.0,
        child: CustomPaint(
          size: Size(width, height),
          painter: _CandlestickPainter(
            candles: candles,
            overlay: overlay,
            takeProfit: takeProfit,
            stopLoss: stopLoss,
            positiveColor: Colors.green.shade400,
            negativeColor: Colors.red.shade400,
            accentColor: Theme.of(context).colorScheme.primary,
            textDimColor: Theme.of(context).colorScheme.outline,
          ),
        ),
      ),
    );
  }
}

class _CandlestickPainter extends CustomPainter {
  _CandlestickPainter({
    required this.candles,
    required this.overlay,
    required this.takeProfit,
    required this.stopLoss,
    required this.positiveColor,
    required this.negativeColor,
    required this.accentColor,
    required this.textDimColor,
  });

  final List<PriceBar> candles;
  final _Overlay overlay;
  final double? takeProfit;
  final double? stopLoss;
  final Color positiveColor;
  final Color negativeColor;
  final Color accentColor;
  final Color textDimColor;

  static const _pad = 14.0;
  static const _tagWidth = 45.0;
  static const _tagHeight = 16.0;

  @override
  void paint(Canvas canvas, Size size) {
    final width = size.width;
    final height = size.height;
    final plotW = width - 50;
    final lastClose = candles.last.close;

    final levels = [...overlay.hlines, lastClose, ?takeProfit, ?stopLoss];
    final allVals = <double>[
      ...candles.expand((c) => [c.high, c.low]),
      ...levels,
    ];
    final max = allVals.reduce((a, b) => a > b ? a : b);
    final min = allVals.reduce((a, b) => a < b ? a : b);
    final range = (max - min) == 0 ? 1 : (max - min);
    double scaleY(double v) => _pad + (height - 2 * _pad) * (1 - (v - min) / range);

    final step = plotW / candles.length;
    final bodyW = (step * 0.55).clamp(2.0, double.infinity);
    double x(int i) => i * step + step / 2;

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
      oldDelegate.candles != candles || oldDelegate.overlay != overlay;
}
