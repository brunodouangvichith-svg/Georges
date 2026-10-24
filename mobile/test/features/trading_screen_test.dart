import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:george_mobile/data/decisions_repository.dart';
import 'package:george_mobile/features/trading/trading_screen.dart';
import 'package:george_mobile/models/decision.dart';
import 'package:george_mobile/models/page.dart' as model;
import 'package:george_mobile/models/performance.dart';

Decision _decision(int id, String symbol, String status, {String? exitScenario}) => Decision(
      id: id,
      symbol: symbol,
      patternId: 1,
      decisionType: 'Achat',
      status: status,
      entryPrice: 100,
      takeProfit: 110,
      stopLoss: 95,
      confidence: 72,
      rationale: null,
      createdAt: DateTime(2026, 10, 1),
      exitScenario: exitScenario,
      exitVolumeConfirmed: exitScenario == null ? null : true,
      exitJustification: exitScenario == null ? null : 'Take-profit franchi le 14/10.',
    );

model.Page<Decision> _page(List<Decision> items) =>
    model.Page<Decision>(items: items, total: items.length, limit: 200, offset: 0);

PerformanceStats _stats({required int count, double? total}) => PerformanceStats(
      count: count,
      wins: count,
      losses: 0,
      winRatePct: count == 0 ? null : 100,
      avgPnlPct: total,
      avgGainPct: total,
      avgLossPct: null,
      totalPnlPct: total,
      bestPnlPct: total,
      worstPnlPct: total,
    );

Widget _app({required Performance performance}) => ProviderScope(
      overrides: [
        decisionsProvider(const DecisionsFilter(status: 'proposee'))
            .overrideWith((ref) async => _page([_decision(1, 'MC.PA', 'proposee')])),
        decisionsProvider(const DecisionsFilter(status: 'confirmee')).overrideWith((ref) async => _page([])),
        decisionsProvider(const DecisionsFilter(status: 'sortie_proposee'))
            .overrideWith((ref) async => _page([_decision(2, 'AIR.PA', 'sortie_proposee', exitScenario: 'sortie_totale')])),
        decisionsProvider(const DecisionsFilter(status: 'cloturee'))
            .overrideWith((ref) async => _page([_decision(3, 'OR.PA', 'cloturee')])),
        performanceProvider.overrideWith((ref) async => performance),
      ],
      child: const MaterialApp(home: TradingScreen()),
    );

void main() {
  testWidgets('TradingScreen shows counts per status and a proposed decision with its actions', (tester) async {
    await tester.pumpWidget(_app(performance: Performance(summary: _stats(count: 0), byPattern: const [], trades: const [])));
    await tester.pumpAndSettle();

    expect(find.text('Proposées (1)'), findsOneWidget);
    expect(find.text('En position (0)'), findsOneWidget);
    expect(find.text('MC.PA'), findsOneWidget);
    expect(find.text('Confirmer'), findsOneWidget);
    expect(find.text('Recalculer'), findsOneWidget);
  });

  testWidgets('Exit tab shows the proposed exit scenario and the close button', (tester) async {
    await tester.pumpWidget(_app(performance: Performance(summary: _stats(count: 0), byPattern: const [], trades: const [])));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Sorties (1)'));
    await tester.pumpAndSettle();

    expect(find.text('AIR.PA'), findsOneWidget);
    expect(find.text('Sortie totale · confirmée par le volume'), findsOneWidget);
    expect(find.text('Confirmer la sortie'), findsOneWidget);
  });

  testWidgets('Closed tab shows the realised result from /decisions/performance', (tester) async {
    final perf = Performance(
      summary: _stats(count: 1, total: 8.5),
      byPattern: const [],
      trades: [
        TradeOutcome(
          decisionId: 3,
          symbol: 'OR.PA',
          decisionType: 'Achat',
          patternType: 'Double Bottom',
          entryPrice: 100,
          result: 'take_profit_hit',
          pnlPct: 8.5,
          closedAt: DateTime(2026, 10, 12),
        ),
      ],
    );
    await tester.pumpWidget(_app(performance: perf));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Clôturées (1)'));
    await tester.pumpAndSettle();

    expect(find.text('OR.PA'), findsOneWidget);
    expect(find.text('+8.50 %'), findsOneWidget);
  });

  testWidgets('Performance tab shows the not-significant warning under 10 trades', (tester) async {
    final perf = Performance(summary: _stats(count: 3, total: 4.2), byPattern: const [], trades: const []);
    await tester.pumpWidget(_app(performance: perf));
    await tester.pumpAndSettle();

    // La barre d'onglets défile : l'onglet Performance est hors écran au départ.
    await tester.ensureVisible(find.text('Performance'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Performance'));
    await tester.pumpAndSettle();

    expect(find.text('POSITIONS CLÔTURÉES'), findsOneWidget);
    expect(find.textContaining('ne sont pas significatifs'), findsOneWidget);
  });

  test('parseLevel: empty keeps the proposed value, invalid is NaN, comma accepted', () {
    expect(parseLevel(''), isNull);
    expect(parseLevel('12,5'), 12.5);
    expect(parseLevel('-3')!.isNaN, isTrue);
    expect(parseLevel('abc')!.isNaN, isTrue);
  });
}
