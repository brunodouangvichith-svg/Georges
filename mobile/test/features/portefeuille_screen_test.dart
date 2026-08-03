import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:george_mobile/data/portfolios_repository.dart';
import 'package:george_mobile/features/portefeuille/portefeuille_screen.dart';
import 'package:george_mobile/models/decision.dart';
import 'package:george_mobile/models/portfolio.dart';

void main() {
  testWidgets('PortefeuilleScreen renders a mocked portfolio and its decisions', (tester) async {
    final decision = Decision(
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
    final portfolioDecision = PortfolioDecision(
      decision: decision,
      quantity: 10,
      currentPrice: 105,
      pnlPct: 5,
      priceUpdatedAt: DateTime(2026, 1, 2, 9, 30),
      dayChangePct: 2.5,
    );
    final portfolio = Portfolio(
      id: 1,
      name: 'Portefeuille croissance',
      createdAt: DateTime(2026, 1, 1),
      decisions: [portfolioDecision],
      totalPnlAmount: 50,
      totalInvested: 1000,
    );

    await tester.pumpWidget(ProviderScope(
      overrides: [
        portfoliosProvider.overrideWith((ref) async => [portfolio]),
      ],
      child: const MaterialApp(home: PortefeuilleScreen()),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Portefeuille croissance'), findsOneWidget);
    expect(find.text('MC.PA'), findsOneWidget);
  });
}
