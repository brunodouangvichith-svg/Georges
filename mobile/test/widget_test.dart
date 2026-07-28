import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:george_mobile/app.dart';
import 'package:george_mobile/data/agents_repository.dart';
import 'package:george_mobile/data/decisions_repository.dart';
import 'package:george_mobile/data/securities_repository.dart';
import 'package:george_mobile/models/agent_event.dart';
import 'package:george_mobile/models/decision.dart';
import 'package:george_mobile/models/page.dart';
import 'package:george_mobile/models/security.dart';

void main() {
  testWidgets('App boots on the Univers tab and lists mocked securities', (WidgetTester tester) async {
    // Comme web/'s vi.mock sur ../api/queries : on mocke les providers plutôt
    // que de laisser un vrai appel réseau partir pendant le test.
    final fakeSecurities = Page<Security>(
      items: [
        Security(symbol: 'MC.PA', name: 'LVMH', country: 'FR', currency: 'EUR', sector: 'Luxe'),
      ],
      total: 1,
      limit: 200,
      offset: 0,
    );
    final fakeDecisions = Page<Decision>(items: const [], total: 0, limit: 200, offset: 0);
    final fakeActivity = Page<AgentEvent>(items: const [], total: 0, limit: 6, offset: 0);

    await tester.pumpWidget(ProviderScope(
      overrides: [
        securitiesProvider(null).overrideWith((ref) async => fakeSecurities),
        decisionsProvider(const DecisionsFilter()).overrideWith((ref) async => fakeDecisions),
        agentActivityProvider.overrideWith((ref) async => fakeActivity),
      ],
      child: const GeorgeApp(),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Univers suivi'), findsOneWidget);
    expect(find.text('MC.PA — LVMH'), findsOneWidget);
  });
}
