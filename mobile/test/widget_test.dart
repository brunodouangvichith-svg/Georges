import 'package:flutter/widgets.dart' show Scrollable;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:george_mobile/app.dart';
import 'package:george_mobile/core/auth/auth_providers.dart';
import 'package:george_mobile/data/agents_repository.dart';
import 'package:george_mobile/data/decisions_repository.dart';
import 'package:george_mobile/data/energy_prices_repository.dart';
import 'package:george_mobile/data/news_repository.dart';
import 'package:george_mobile/data/patterns_repository.dart';
import 'package:george_mobile/data/prices_repository.dart';
import 'package:george_mobile/data/securities_repository.dart';
import 'package:george_mobile/models/agent_event.dart';
import 'package:george_mobile/models/decision.dart';
import 'package:george_mobile/models/page.dart';
import 'package:george_mobile/models/pattern.dart';
import 'package:george_mobile/models/price_bar.dart';
import 'package:george_mobile/models/security.dart';

void main() {
  testWidgets('App boots on the Univers tab: counters, radar and watchlist from mocked data', (
    WidgetTester tester,
  ) async {
    // Comme web/'s vi.mock sur ../api/queries : on mocke les providers plutôt
    // que de laisser un vrai appel réseau partir pendant le test.
    final fakeSecurities = Page<Security>(
      items: [
        Security(
          symbol: 'MC.PA',
          name: 'LVMH',
          country: 'FR',
          currency: 'EUR',
          sector: 'Luxe',
        ),
      ],
      total: 1,
      limit: 200,
      offset: 0,
    );
    final fakeDecisions = Page<Decision>(
      items: const [],
      total: 0,
      limit: 200,
      offset: 0,
    );
    final fakeActivity = Page<AgentEvent>(
      items: const [],
      total: 0,
      limit: 6,
      offset: 0,
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          securitiesProvider(null).overrideWith((ref) async => fakeSecurities),
          decisionsProvider(
            const DecisionsFilter(),
          ).overrideWith((ref) async => fakeDecisions),
          agentActivityProvider.overrideWith((ref) async => fakeActivity),
          // Tuiles énergie/actualités en bas de l'écran : construites quand le
          // test défile jusqu'à la watchlist — sans ces faux, leur vrai appel
          // réseau (Dio) laisse un timer en suspens à la fin du test.
          energyPricesProvider.overrideWith((ref) async => const []),
          newsProvider.overrideWith((ref) async => const []),
          latestPatternsProvider.overrideWith(
            (ref) async => {
              'MC.PA': Pattern(
                id: 1,
                symbol: 'MC.PA',
                patternType: 'Double Top',
                detectedAt: DateTime(2026, 10, 15),
                confidence: 95,
                context: const {},
              ),
            },
          ),
          securityPricesProvider('MC.PA').overrideWith(
            (ref) async => Page<PriceBar>(
              items: [
                for (var i = 0; i < 30; i++)
                  PriceBar(
                    ts: DateTime(2026, 9, 1).add(Duration(days: i)),
                    open: 100.0 + i,
                    high: 102.0 + i,
                    low: 99.0 + i,
                    close: 101.0 + i,
                    volume: 1000,
                  ),
              ],
              total: 30,
              limit: 250,
              offset: 0,
            ),
          ),
          // Portail d'accès simple (Phase 9) : ces deux providers évitent que
          // le routeur ne touche le vrai singleton Supabase (jamais
          // initialisé ici, ce test ne passe pas par main()) et forcent un
          // état "connecté" pour pouvoir vérifier l'écran Univers.
          authChangeStreamProvider.overrideWithValue(const Stream.empty()),
          isLoggedInProvider.overrideWithValue(true),
        ],
        child: const GeorgeApp(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('George / Univers'), findsOneWidget);
    // Dock "Poser une question à George" retiré (_AskDock) : c'était un
    // enfant direct de la Column racine, toujours construit (pas lazy)
    // dès ce premier pump, donc cette assertion n'a pas besoin de défiler.
    expect(find.text('Poser une question à George…'), findsNothing);
    // Compteur « Figures actives » = 1 (la figure du lot), valeur
    // sélectionnée par défaut = le premier titre, avec sa figure.
    expect(find.text('FIGURES ACTIVES'), findsOneWidget);
    // Le panneau de la valeur sélectionnée est sous le radar : la liste ne le
    // construit qu'une fois approché, d'où le défilement.
    await tester.scrollUntilVisible(
      find.text('95%'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('LVMH'), findsWidgets);
    expect(find.text('Double Top'), findsWidgets);

    // La watchlist est plus bas dans la liste (construite à la demande).
    await tester.scrollUntilVisible(
      find.text('WATCHLIST / FIGURES ACTIVES'),
      400,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('MC.PA'), findsWidgets);

    // Bouton flottant "Ask Jane" — présence uniquement, pas de tap : ouvrir
    // la fiche déclencherait SpeechToText.initialize() (canal de plateforme
    // absent en test), déjà couvert défensivement côté widget lui-même
    // (voir ask_jane_sheet.dart) plutôt que re-testé ici.
    expect(find.text('🧠'), findsOneWidget);
    expect(find.byTooltip('Analyse Technique - Ask Jane'), findsOneWidget);
  });
}
