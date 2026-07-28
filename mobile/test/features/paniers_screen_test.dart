import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:george_mobile/data/baskets_repository.dart';
import 'package:george_mobile/data/decisions_repository.dart';
import 'package:george_mobile/data/securities_repository.dart';
import 'package:george_mobile/features/paniers/paniers_screen.dart';
import 'package:george_mobile/models/basket.dart';
import 'package:george_mobile/models/decision.dart';
import 'package:george_mobile/models/page.dart' as model;
import 'package:george_mobile/models/security.dart';

void main() {
  testWidgets('PaniersScreen renders KPIs and a decision row from mocked providers', (tester) async {
    final fakeSecurities = model.Page<Security>(
      items: [Security(symbol: 'MC.PA', name: 'LVMH', country: 'FR', currency: 'EUR', sector: 'Luxe')],
      total: 1,
      limit: 200,
      offset: 0,
    );
    final fakeDecision = Decision(
      id: 1,
      symbol: 'MC.PA',
      patternId: null,
      decisionType: 'Achat',
      status: 'confirmee',
      entryPrice: 100,
      takeProfit: 110,
      stopLoss: 95,
      confidence: 72,
      rationale: null,
      createdAt: DateTime(2026, 1, 1),
    );
    final fakeDecisions = model.Page<Decision>(items: [fakeDecision], total: 1, limit: 200, offset: 0);
    final fakeBaskets = [Basket(id: 1, name: 'Luxe', type: 'sector')];

    await tester.pumpWidget(ProviderScope(
      overrides: [
        basketsProvider.overrideWith((ref) async => fakeBaskets),
        securitiesProvider(null).overrideWith((ref) async => fakeSecurities),
        decisionsProvider(const DecisionsFilter()).overrideWith((ref) async => fakeDecisions),
      ],
      child: const MaterialApp(home: PaniersScreen()),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Paniers & décisions'), findsOneWidget);
    expect(find.text('MC.PA'), findsWidgets);
  });
}
