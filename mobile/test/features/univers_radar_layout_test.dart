import 'dart:math' as math;

import 'package:flutter_test/flutter_test.dart';
import 'package:george_mobile/features/univers/widgets/univers_radar_layout.dart';
import 'package:george_mobile/models/decision.dart';
import 'package:george_mobile/models/pattern.dart';
import 'package:george_mobile/models/security.dart';

Security _s(String symbol, String sector) =>
    Security(symbol: symbol, name: symbol, country: 'FR', currency: 'EUR', sector: sector);

void main() {
  test('groups by sector, biggest first, and labels only sectors of 3+ securities', () {
    final securities = [
      _s('A1', 'Petit'),
      for (var i = 0; i < 5; i++) _s('B$i', 'Gros'),
    ];
    final layout = buildRadarLayout(securities, const {}, const {});
    expect(layout.items.map((i) => i.symbol).take(5), ['B0', 'B1', 'B2', 'B3', 'B4']);
    expect(layout.items.first.angle, closeTo(-math.pi / 2, 1e-9));
    expect(layout.labels.map((l) => l.sector), ['Gros']);
    // 6 valeurs + 2 secteurs × 2 cases d'espace = 10 cases sur le cercle.
    expect(layout.step, closeTo(2 * math.pi / 10, 1e-9));
  });

  test('carries pattern confidence (clamped) and decision, and finds the nearest tick', () {
    final securities = [for (var i = 0; i < 4; i++) _s('S$i', 'Tech')];
    final pattern = Pattern(
      id: 1,
      symbol: 'S1',
      patternType: 'Double Top',
      detectedAt: DateTime(2026, 10, 1),
      confidence: 140,
      context: const {},
    );
    final decision = Decision(
      id: 1,
      symbol: 'S1',
      patternId: 1,
      decisionType: 'Alléger',
      status: 'proposee',
      entryPrice: 10,
      takeProfit: 8,
      stopLoss: 11,
      confidence: 80,
      rationale: null,
      createdAt: DateTime(2026, 10, 1),
    );
    final layout = buildRadarLayout(securities, {'S1': pattern}, {'S1': decision});
    final s1 = layout.items[1];
    expect(s1.confidence, 100);
    expect(s1.decision, 'Alléger');
    expect(layout.items[0].confidence, isNull);
    expect(layout.nearest(s1.angle + layout.step * 0.4)?.symbol, 'S1');
    expect(buildRadarLayout(const [], const {}, const {}).nearest(0), isNull);
  });

  test('groups sub-sectors by family and gathers small families in "Autres secteurs"', () {
    final securities = [
      _s('A', 'Santé / Biotechnologie'),
      _s('B', 'Santé / Pharmacie'),
      _s('C', 'Santé'),
      _s('D', 'Énergie / Utilities'),
      _s('E', 'Médias'),
      _s('F', 'Assurance'),
    ];
    final layout = buildRadarLayout(securities, const {}, const {});
    expect(layout.labels.map((l) => l.sector), ['Santé', otherFamily]);
    expect(layout.items.map((i) => i.symbol), ['A', 'B', 'C', 'D', 'E', 'F']);
  });
}
