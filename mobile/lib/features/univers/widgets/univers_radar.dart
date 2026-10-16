import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import 'univers_radar_layout.dart';

/// Radar de l'univers — port de `web/src/components/UniversRadar.jsx` :
///
/// - une graduation par valeur suivie, regroupées par secteur ;
/// - barre radiale = confiance de la dernière figure détectée (pas de barre
///   = aucune figure), couleur = décision en cours (vert achat/renfort,
///   orange surveiller, rouge alléger, bleu aucune), trait épais ≥ 75 % ;
/// - la valeur sélectionnée est surlignée et ses vraies clôtures (`closes`)
///   traversent le disque ;
/// - le champ de lignes intérieur est décoratif (graine fixe) : il ne
///   représente aucune donnée.
///
/// Un tap près d'une graduation sélectionne la valeur. Le radar se zoome au
/// pincement (jusqu'à ×5) pour viser une graduation précise ; un bouton
/// « Réinitialiser le zoom » apparaît dès qu'on a zoomé. À l'échelle 1, un
/// glissement vertical d'un doigt fait toujours défiler l'écran. La liste
/// « Watchlist » sous le radar reste le chemin des lecteurs d'écran.
class UniversRadar extends StatefulWidget {
  const UniversRadar({
    super.key,
    required this.layout,
    required this.selectedSymbol,
    required this.onSelect,
    this.closes = const [],
  });

  final RadarLayout layout;
  final String? selectedSymbol;
  final ValueChanged<String> onSelect;
  final List<double> closes;

  static const double _viewHeight = 680;
  static const double _cx = 380;
  static const double _cy = 340;
  static const double maxZoom = 5;

  @override
  State<UniversRadar> createState() => _UniversRadarState();
}

class _UniversRadarState extends State<UniversRadar> {
  final _zoom = TransformationController();
  bool _zoomed = false;

  @override
  void initState() {
    super.initState();
    _zoom.addListener(_onZoomChanged);
  }

  @override
  void dispose() {
    _zoom
      ..removeListener(_onZoomChanged)
      ..dispose();
    super.dispose();
  }

  void _onZoomChanged() {
    final zoomed = _zoom.value.getMaxScaleOnAxis() > 1.01;
    if (zoomed != _zoomed) setState(() => _zoomed = zoomed);
  }

  @override
  Widget build(BuildContext context) {
    final layout = widget.layout;
    final withPattern = layout.items.where((it) => it.confidence != null).length;
    return Semantics(
      image: true,
      label:
          "Radar de l'univers : ${layout.items.length} valeurs réparties en ${layout.labels.length} grands secteurs, "
          '$withPattern avec une figure détectée. La longueur des barres suit la confiance de la figure. '
          'Pincez pour zoomer.',
      child: AspectRatio(
        aspectRatio: radarViewWidth / UniversRadar._viewHeight,
        child: LayoutBuilder(
          builder: (context, constraints) {
            final k = constraints.maxWidth / radarViewWidth;
            return Stack(
              children: [
                Positioned.fill(
                  child: ClipRect(
                    child: InteractiveViewer(
                      transformationController: _zoom,
                      minScale: 1,
                      maxScale: UniversRadar.maxZoom,
                      // À l'échelle 1, pas de déplacement : le glissement
                      // vertical reste au défilement de l'écran.
                      panEnabled: _zoomed,
                      child: GestureDetector(
                        behavior: HitTestBehavior.opaque,
                        onTapUp: (details) {
                          // Coordonnées locales au radar non zoomé : le zoom
                          // d'InteractiveViewer est déjà défait ici.
                          final dx = details.localPosition.dx / k - UniversRadar._cx;
                          final dy = details.localPosition.dy / k - UniversRadar._cy;
                          final r = math.sqrt(dx * dx + dy * dy);
                          // Bande généreuse autour de l'anneau, pensée pour le doigt.
                          if (r < rTickIn - 40 || r > rBar + 70) return;
                          final item = layout.nearest(math.atan2(dy, dx));
                          if (item != null) widget.onSelect(item.symbol);
                        },
                        child: CustomPaint(
                          size: Size(constraints.maxWidth, constraints.maxWidth * UniversRadar._viewHeight / radarViewWidth),
                          painter: _RadarPainter(
                            layout: layout,
                            selectedSymbol: widget.selectedSymbol,
                            closes: widget.closes,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                if (_zoomed)
                  Positioned(
                    left: 0,
                    top: 0,
                    child: TextButton.icon(
                      onPressed: () => _zoom.value = Matrix4.identity(),
                      icon: const Icon(Icons.zoom_out_map, size: 16),
                      label: const Text('Réinitialiser le zoom'),
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }
}

Color radarDecisionColor(String? decision) {
  if (decision == null) return AppColors.accent;
  if (isBullishDecision(decision)) return AppColors.positive;
  if (decision == 'Surveiller') return AppColors.warning;
  return AppColors.negative;
}

/// Champ de lignes décoratif, calculé une seule fois en unités du viewBox.
final Path _flowPath = () {
  final rand = math.Random(42);
  final path = Path();
  const cx = UniversRadar._cx;
  const cy = UniversRadar._cy;
  for (var i = 0; i < 150; i++) {
    final a0 = rand.nextDouble() * math.pi * 2;
    final r0 = math.sqrt(rand.nextDouble()) * rIn;
    var x = cx + math.cos(a0) * r0;
    var y = cy + math.sin(a0) * r0;
    path.moveTo(x, y);
    final steps = 18 + rand.nextInt(45);
    for (var s = 0; s < steps; s++) {
      final ang = math.sin((x - cx) * 0.011) * 2.3 + math.cos((y - cy) * 0.013) * 1.9 + (i % 3) * 0.5;
      x += math.cos(ang) * 6;
      y += math.sin(ang) * 6;
      final dx = x - cx;
      final dy = y - cy;
      if (math.sqrt(dx * dx + dy * dy) > rIn - 2) break;
      path.lineTo(x, y);
    }
  }
  return path;
}();

class _RadarPainter extends CustomPainter {
  _RadarPainter({required this.layout, required this.selectedSymbol, required this.closes});

  final RadarLayout layout;
  final String? selectedSymbol;
  final List<double> closes;

  @override
  void paint(Canvas canvas, Size size) {
    final k = size.width / radarViewWidth;
    final cx = UniversRadar._cx * k;
    final cy = UniversRadar._cy * k;
    Offset polar(double angle, double r) => Offset(cx + math.cos(angle) * r * k, cy + math.sin(angle) * r * k);

    canvas.drawCircle(Offset(cx, cy), rIn * k, Paint()..color = AppColors.panel);
    canvas.drawPath(
      _flowPath.transform(Matrix4.diagonal3Values(k, k, 1).storage),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 0.5
        ..color = AppColors.accent.withValues(alpha: 0.28),
    );

    _paintTrail(canvas, k);

    canvas.drawCircle(
      Offset(cx, cy),
      (rIn + 2) * k,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = AppColors.hairline,
    );

    final tickPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.8
      ..color = AppColors.textDim;
    RadarItem? selected;
    for (final it in layout.items) {
      canvas.drawLine(polar(it.angle, rTickIn), polar(it.angle, rTickOut), tickPaint);
      if (it.symbol == selectedSymbol) {
        selected = it;
        continue;
      }
      final confidence = it.confidence;
      if (confidence == null) continue;
      final strong = confidence >= 75;
      canvas.drawLine(
        polar(it.angle, rBar),
        polar(it.angle, rBar + confidence * barScale),
        Paint()
          ..strokeWidth = strong ? 2.2 : 1.1
          ..strokeCap = StrokeCap.butt
          ..color = radarDecisionColor(it.decision).withValues(alpha: strong ? 1 : 0.7),
      );
    }

    if (selected != null) {
      final confidence = selected.confidence;
      final paint = Paint()
        ..strokeWidth = 3.5
        ..color = AppColors.text;
      if (confidence == null) {
        canvas.drawLine(polar(selected.angle, rTickIn - 4 * radarScale), polar(selected.angle, rTickOut + 6 * radarScale), paint);
      } else {
        canvas.drawLine(polar(selected.angle, rBar), polar(selected.angle, rBar + confidence * barScale), paint);
      }
    }

    for (final label in layout.labels) {
      final c = math.cos(label.angle);
      final anchor = c > 0.25 ? _Anchor.end : (c < -0.25 ? _Anchor.start : _Anchor.middle);
      final p = polar(label.angle, rSectorLabel);
      _drawText(canvas, size, label.text, Offset(p.dx, p.dy + 4 * k), anchor,
          fontSize: 9, weight: FontWeight.w600, color: AppColors.textDim);
    }

    if (selected != null) {
      final c = math.cos(selected.angle);
      final anchor = c > 0.2 ? _Anchor.start : (c < -0.2 ? _Anchor.end : _Anchor.middle);
      final p = polar(selected.angle, rBar + 52 * radarScale);
      final text =
          '${selected.symbol} · ${selected.confidence == null ? "sans figure" : "${selected.confidence!.round()} %"}';
      _drawText(canvas, size, text, Offset(p.dx, p.dy + 4 * k), anchor,
          fontSize: 11, weight: FontWeight.w700, color: AppColors.text);
    }
  }

  /// Clôtures réelles de la valeur sélectionnée, en travers du disque, avec
  /// une perle toutes les ~n/14 séances et un double anneau sur la dernière.
  void _paintTrail(Canvas canvas, double k) {
    if (closes.length < 2) return;
    final minV = closes.reduce(math.min);
    final maxV = closes.reduce(math.max);
    final span = (maxV - minV) == 0 ? 1.0 : maxV - minV;
    final n = closes.length;
    const cx = UniversRadar._cx;
    const cy = UniversRadar._cy;
    Offset point(int i) => Offset(
          (cx - 220 * radarScale + (i / (n - 1)) * 400 * radarScale) * k,
          (cy + 150 * radarScale - ((closes[i] - minV) / span) * 150 * radarScale) * k,
        );
    final path = Path()..moveTo(point(0).dx, point(0).dy);
    for (var i = 1; i < n; i++) {
      final p = point(i);
      path.lineTo(p.dx, p.dy);
    }
    canvas.drawPath(
      path,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.1
        ..color = AppColors.text,
    );
    final fill = Paint()..color = AppColors.panel;
    final ring = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = AppColors.text;
    final every = math.max(1, (n / 14).ceil());
    for (var i = 0; i < n - 1; i += every) {
      canvas.drawCircle(point(i), 2.4, fill);
      canvas.drawCircle(point(i), 2.4, ring);
    }
    final last = point(n - 1);
    canvas.drawCircle(last, 4.5, fill);
    canvas.drawCircle(
      last,
      4.5,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..color = AppColors.accent,
    );
  }

  void _drawText(
    Canvas canvas,
    Size size,
    String text,
    Offset baseline,
    _Anchor anchor, {
    required double fontSize,
    required FontWeight weight,
    required Color color,
  }) {
    final base = monoTextStyle(fontSize: fontSize, fontWeight: weight);
    final outline = TextPainter(
      text: TextSpan(
        text: text,
        style: base.copyWith(
          foreground: Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 3
            ..color = AppColors.panel,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    final fill = TextPainter(
      text: TextSpan(text: text, style: base.copyWith(color: color)),
      textDirection: TextDirection.ltr,
    )..layout();
    var left = switch (anchor) {
      _Anchor.start => baseline.dx,
      _Anchor.end => baseline.dx - fill.width,
      _Anchor.middle => baseline.dx - fill.width / 2,
    };
    left = left.clamp(2.0, math.max(2.0, size.width - fill.width - 2));
    final top = baseline.dy - fill.height * 0.75;
    outline.paint(canvas, Offset(left, top));
    fill.paint(canvas, Offset(left, top));
  }

  @override
  bool shouldRepaint(covariant _RadarPainter old) =>
      old.layout != layout || old.selectedSymbol != selectedSymbol || old.closes != closes;
}

enum _Anchor { start, middle, end }
