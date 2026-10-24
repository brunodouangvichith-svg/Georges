import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/bond.dart';

/// Une série de l'historique des taux (un instrument).
class BondSeries {
  const BondSeries({
    required this.label,
    required this.color,
    required this.points,
    this.width = 1.6,
    this.dashed = false,
  });

  final String label;
  final Color color;
  final List<BondHistoryPoint> points;
  final double width;
  final bool dashed;
}

/// Courbes des taux sur la période choisie — miroir mobile de
/// web/src/components/BondHistoryChart.jsx, dessiné à la main (CustomPainter)
/// comme candlestick_chart.dart. Couleurs bleu/blanc/orange/gris : le vert et
/// le rouge restent réservés au sens des variations.
class BondHistoryChart extends StatelessWidget {
  const BondHistoryChart({super.key, required this.series, this.height = 220});

  final List<BondSeries> series;
  final double height;

  @override
  Widget build(BuildContext context) {
    final nonEmpty = series.where((s) => s.points.length > 1).toList();
    if (nonEmpty.isEmpty) {
      return SizedBox(
        height: 80,
        child: Center(
          child: Text(
            'Aucun historique sur cette période.',
            style: TextStyle(color: Theme.of(context).colorScheme.outline),
          ),
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          height: height,
          width: double.infinity,
          child: CustomPaint(painter: _BondChartPainter(nonEmpty)),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 14,
          runSpacing: 4,
          children: [
            for (final s in nonEmpty)
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(width: 14, height: s.width + 1, color: s.color),
                  const SizedBox(width: 6),
                  Text(s.label, style: const TextStyle(fontSize: 11.5, color: AppColors.textDim)),
                ],
              ),
          ],
        ),
      ],
    );
  }
}

class _BondChartPainter extends CustomPainter {
  _BondChartPainter(this.series);

  final List<BondSeries> series;

  static const _leftPad = 40.0;
  static const _bottomPad = 18.0;

  @override
  void paint(Canvas canvas, Size size) {
    var minT = double.infinity, maxT = -double.infinity;
    var minY = double.infinity, maxY = -double.infinity;
    for (final s in series) {
      for (final p in s.points) {
        final t = p.observedAt.millisecondsSinceEpoch.toDouble();
        minT = math.min(minT, t);
        maxT = math.max(maxT, t);
        minY = math.min(minY, p.valuePct);
        maxY = math.max(maxY, p.valuePct);
      }
    }
    if (maxT <= minT) maxT = minT + 1;
    final pad = math.max((maxY - minY) * 0.08, 0.05);
    minY -= pad;
    maxY += pad;

    final plotW = size.width - _leftPad;
    final plotH = size.height - _bottomPad;
    double x(DateTime d) => _leftPad + (d.millisecondsSinceEpoch - minT) / (maxT - minT) * plotW;
    double y(double v) => plotH - (v - minY) / (maxY - minY) * plotH;

    // Grille + graduations en % (4 paliers).
    final grid = Paint()
      ..color = AppColors.hairline
      ..strokeWidth = 1;
    for (var i = 0; i <= 4; i++) {
      final v = minY + (maxY - minY) * i / 4;
      final gy = y(v);
      canvas.drawLine(Offset(_leftPad, gy), Offset(size.width, gy), grid);
      _text(canvas, '${v.toStringAsFixed(2)}%', Offset(0, gy - 7), 10);
    }

    // Dates de début et de fin sous l'axe.
    final start = DateTime.fromMillisecondsSinceEpoch(minT.round());
    final end = DateTime.fromMillisecondsSinceEpoch(maxT.round());
    _text(canvas, _monthYear(start), Offset(_leftPad, plotH + 4), 10);
    final endLabel = _monthYear(end);
    _text(canvas, endLabel, Offset(size.width - endLabel.length * 6.0, plotH + 4), 10);

    for (final s in series) {
      final paint = Paint()
        ..color = s.color
        ..strokeWidth = s.width
        ..style = PaintingStyle.stroke;
      final path = Path();
      for (var i = 0; i < s.points.length; i++) {
        final p = s.points[i];
        final o = Offset(x(p.observedAt), y(p.valuePct));
        if (i == 0) {
          path.moveTo(o.dx, o.dy);
        } else {
          path.lineTo(o.dx, o.dy);
        }
      }
      if (s.dashed) {
        _drawDashed(canvas, path, paint);
      } else {
        canvas.drawPath(path, paint);
      }
    }
  }

  void _drawDashed(Canvas canvas, Path path, Paint paint) {
    const dash = 5.0, gap = 3.0;
    for (final metric in path.computeMetrics()) {
      var distance = 0.0;
      while (distance < metric.length) {
        final next = math.min(distance + dash, metric.length);
        canvas.drawPath(metric.extractPath(distance, next), paint);
        distance = next + gap;
      }
    }
  }

  static const _months = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];

  String _monthYear(DateTime d) => '${_months[d.month - 1]} ${d.year}';

  void _text(Canvas canvas, String text, Offset offset, double fontSize) {
    final tp = TextPainter(
      text: TextSpan(text: text, style: TextStyle(color: AppColors.textDim, fontSize: fontSize)),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, offset);
  }

  @override
  bool shouldRepaint(covariant _BondChartPainter oldDelegate) => oldDelegate.series != series;
}
