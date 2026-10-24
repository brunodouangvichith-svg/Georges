import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:george_mobile/data/bonds_repository.dart';
import 'package:george_mobile/features/obligataire/obligataire_screen.dart';
import 'package:george_mobile/models/bond.dart';

void main() {
  testWidgets('ObligataireScreen renders yields, red rise / green fall, and editable thresholds', (tester) async {
    final now = DateTime.now();
    final history = [
      BondHistoryPoint(observedAt: now.subtract(const Duration(days: 60)), valuePct: 3.1),
      BondHistoryPoint(observedAt: now.subtract(const Duration(days: 30)), valuePct: 3.3),
    ];
    final dashboard = BondDashboard(
      cards: [
        BondYieldCard(
          instrument: 'OAT_FR_10Y',
          valuePct: 3.35,
          observedAt: '2026-09-01',
          sourceName: 'FRED',
          sourceUrl: null,
          variationsBps: const {'24h': null, '7j': 4, '30j': -12},
        ),
        BondYieldCard(
          instrument: 'UST_US_2Y',
          valuePct: null,
          observedAt: null,
          sourceName: null,
          sourceUrl: null,
          variationsBps: const {},
        ),
      ],
      spreadOatBundBps: 78,
      usCurveSlopeBps: null,
    );

    await tester.pumpWidget(ProviderScope(
      overrides: [
        bondDashboardProvider.overrideWith((ref) async => dashboard),
        for (final code in ['OAT_FR_10Y', 'BUND_DE_10Y', 'UST_US_10Y', 'UST_US_2Y'])
          bondHistoryProvider(code).overrideWith((ref) async => history),
        bondThresholdsProvider.overrideWith((ref) async => [
              BondAlertThreshold(
                id: 1,
                instrument: 'OAT_FR_10Y',
                direction: 'above',
                thresholdPct: 3.5,
                enabled: true,
                updatedAt: DateTime(2026, 10, 1),
              ),
            ]),
        bondActiveAlertsProvider.overrideWith((ref) async => <BondAlertEvent>[]),
        bondBulletinProvider.overrideWith(
          (ref) async => BondBulletin(bulletin: 'OAT 10 ans à 3,35 %.', generatedAt: DateTime(2026, 10, 16, 8)),
        ),
      ],
      child: const MaterialApp(home: ObligataireScreen()),
    ));
    await tester.pumpAndSettle();

    expect(find.text('3.35 %'), findsOneWidget);
    expect(find.text('Donnée indisponible (aucune collecte réussie)'), findsOneWidget);
    expect(find.text('+78 pb'), findsOneWidget);

    // Hausse en rouge, baisse en vert.
    final up = tester.widget<Text>(find.text('7j ▲ 4 pb'));
    final down = tester.widget<Text>(find.text('30j ▼ 12 pb'));
    expect(up.style?.color, const Color(0xFFE2555F));
    expect(down.style?.color, const Color(0xFF2FBF82));

    // Plusieurs Scrollable à l'écran (ListView principale, mais aussi le
    // SelectableText du bulletin et le TextField du seuil, qui embarquent
    // chacun un EditableText scrollable) : sans `scrollable:`,
    // scrollUntilVisible lève "Too many elements". La ListView, ancêtre de
    // tous les autres, est le premier Scrollable de l'arbre.
    await tester.scrollUntilVisible(
      find.byTooltip('Enregistrer'),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    // Bouton désactivé tant que rien n'a changé…
    expect(tester.widget<IconButton>(find.widgetWithIcon(IconButton, Icons.check)).onPressed, isNull);
    // …puis actif dès qu'on modifie la valeur.
    await tester.enterText(find.widgetWithText(TextField, '3.5'), '3.6');
    await tester.pump();
    expect(tester.widget<IconButton>(find.widgetWithIcon(IconButton, Icons.check)).onPressed, isNotNull);
  });
}
