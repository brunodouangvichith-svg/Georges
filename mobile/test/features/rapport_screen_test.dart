import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:george_mobile/data/strategic_reports_repository.dart';
import 'package:george_mobile/features/rapport/markdown_blocks.dart';
import 'package:george_mobile/features/rapport/rapport_screen.dart';
import 'package:george_mobile/models/strategic_report.dart';

StrategicReport _report() => StrategicReport.fromJson({
      'id': 3,
      'created_at': '2026-10-16T09:00:00Z',
      'risk_level': 'orange',
      'model_used': 'mistral-large-latest',
      'narrative_markdown': '## Synthèse exécutive\n\n- L\'inflation atteint **3,1 %** [1].',
      'data': {
        'prices_as_of': '2026-10-15',
        'risk': {
          'level': 'orange',
          'oat_10y_pct': 4.9,
          'oat_observed_at': '2026-09-01',
          'bund_10y_pct': 3.5,
          'spread_oat_bund_bps': 140,
          'criteria': {'rouge': 'OAT > 5 %', 'vert': 'spread < 120 pb', 'orange': 'entre les deux'},
        },
        'cac40_index': {'close': 7934.7, 'as_of': '2026-10-15', 'week_change_pct': 1.68},
        'energy': [
          {'code': 'BRENT_CRUDE_USD', 'price': 106, 'as_of': '2026-10-16'},
        ],
        'portfolio': {
          'initial_capital': 100000,
          'fee_rate': 0.0015,
          'min_cash_ratio': 0.45,
          'cash': 92036.0,
          'total_value': 99986.0,
          'performance_since_start_pct': -0.01,
          'previous_total_value': null,
          'performance_since_previous_pct': null,
          'positions': [
            {'symbol': 'AIR.PA', 'name': 'Airbus', 'quantity': 40, 'price': 198.75, 'value': 7950, 'weight_pct': 7.95},
          ],
          'trades': [
            {'symbol': 'AIR.PA', 'name': 'Airbus', 'side': 'achat', 'quantity': 40, 'price': 198.75, 'gross': 7950, 'fees': 11.93, 'rationale': 'Signal George « Achat »'},
          ],
        },
        'cac40': [
          {'symbol': 'AIR.PA', 'name': 'Airbus', 'sector': 'Industrie', 'close': 198.75, 'week_change_pct': 2.1, 'decision_type': 'Achat', 'confidence': 80, 'pattern_type': 'Double Bottom', 'portfolio_action': 'Achat simulé(e) : 40'},
          {'symbol': 'MC.PA', 'name': 'LVMH', 'sector': 'Luxe', 'close': 396, 'week_change_pct': -3, 'decision_type': null, 'confidence': null, 'pattern_type': null, 'portfolio_action': null},
        ],
        'sources': [
          {'n': 1, 'theme': 'Inflation', 'titre': 'Inflation en septembre', 'url': 'https://www.insee.fr/x'},
        ],
      },
    });

Widget _app(StrategicReport? report) => ProviderScope(
      overrides: [
        strategicReportProvider(null).overrideWith((ref) async => report),
        strategicReportsListProvider.overrideWith((ref) async => report == null ? <StrategicReportSummary>[] : [report]),
      ],
      child: const MaterialApp(home: RapportScreen()),
    );

void main() {
  testWidgets('RapportScreen shows risk level, key figures, commentary and portfolio', (tester) async {
    await tester.pumpWidget(_app(_report()));
    await tester.pumpAndSettle();

    expect(find.text('ORANGE'), findsOneWidget);
    expect(find.text('+140 pb'), findsOneWidget);

    // ListView construit ses enfants à la demande : le commentaire est sous
    // le pli de l'écran de test (800 × 600), il faut défiler pour le créer.
    await tester.scrollUntilVisible(find.textContaining('Synthèse exécutive'), 300, scrollable: find.byType(Scrollable).first);
    expect(find.textContaining('Synthèse exécutive'), findsOneWidget);

    await tester.scrollUntilVisible(find.text('Positions'), 300, scrollable: find.byType(Scrollable).first);
    expect(find.textContaining('Achat 40 × Airbus'), findsOneWidget);

    await tester.scrollUntilVisible(find.text('LVMH'), 300, scrollable: find.byType(Scrollable).first);
    expect(find.text('LVMH'), findsOneWidget);
  });

  testWidgets('RapportScreen shows an empty state with a generate button', (tester) async {
    await tester.pumpWidget(_app(null));
    await tester.pumpAndSettle();
    expect(find.textContaining("Aucun rapport n'a encore été généré"), findsOneWidget);
    expect(find.text('Générer le rapport de la semaine'), findsOneWidget);
  });

  test('parseMarkdownBlocks / parseMarkdownInline', () {
    final blocks = parseMarkdownBlocks('## Titre\n\n- un\n- deux\n\nTexte\nsuite\n\n1. a\n2. b');
    expect(blocks.map((b) => b.type).toList(), ['h2', 'ul', 'p', 'ol']);
    expect(blocks[1].items, ['un', 'deux']);
    expect(blocks[2].text, 'Texte suite');

    final segs = parseMarkdownInline('Hausse **forte** [2].');
    expect(segs.map((s) => s.type).toList(), ['text', 'bold', 'text', 'ref', 'text']);
    expect(segs[3].ref, 2);
  });
}
