import 'package:flutter_test/flutter_test.dart';

import 'package:george_mobile/models/bond.dart';
import 'package:george_mobile/models/decision.dart';
import 'package:george_mobile/models/performance.dart';

void main() {
  test('Decision.fromJson reads the exit fields filled by the monitor job', () {
    final d = Decision.fromJson({
      'id': 7,
      'symbol': 'AIR.PA',
      'pattern_id': null,
      'decision_type': 'Achat',
      'status': 'sortie_proposee',
      'entry_price': 150,
      'take_profit': 165.5,
      'stop_loss': null,
      'confidence': 61.2,
      'rationale': null,
      'exit_scenario': 'sortie_partielle',
      'exit_volume_confirmed': false,
      'exit_justification': 'Stop-loss franchi sans volume.',
      'exit_proposed_at': '2026-10-14T18:00:00Z',
      'created_at': '2026-10-01T08:00:00Z',
    });
    expect(d.exitScenario, 'sortie_partielle');
    expect(d.exitVolumeConfirmed, isFalse);
    expect(d.exitProposedAt, DateTime.utc(2026, 10, 14, 18));
    expect(d.stopLoss, isNull);
  });

  test('Performance.fromJson keeps null averages null (never a fabricated 0)', () {
    final p = Performance.fromJson({
      'summary': {
        'count': 0,
        'wins': 0,
        'losses': 0,
        'win_rate_pct': null,
        'avg_pnl_pct': null,
        'avg_gain_pct': null,
        'avg_loss_pct': null,
        'total_pnl_pct': null,
        'best_pnl_pct': null,
        'worst_pnl_pct': null,
      },
      'by_pattern': [
        {
          'pattern_type': 'Sans figure',
          'count': 1,
          'wins': 1,
          'losses': 0,
          'win_rate_pct': 100,
          'avg_pnl_pct': 5,
          'avg_gain_pct': 5,
          'avg_loss_pct': null,
          'total_pnl_pct': 5,
          'best_pnl_pct': 5,
          'worst_pnl_pct': 5,
        },
      ],
      'trades': [],
    });
    expect(p.summary.avgPnlPct, isNull);
    expect(p.byPattern.single.patternType, 'Sans figure');
    expect(p.byPattern.single.stats.winRatePct, 100.0);
  });

  test('BondYieldCard.fromJson keeps a missing 24h variation as null', () {
    final c = BondYieldCard.fromJson({
      'instrument': 'OAT_FR_10Y',
      'value_pct': 3.2,
      'observed_at': '2026-09-01',
      'fetched_at': '2026-10-16T07:00:00Z',
      'source_name': 'FRED',
      'source_url': null,
      'variations_bps': {'24h': null, '7j': 3, '30j': -10.5},
    });
    expect(c.variationsBps['24h'], isNull);
    expect(c.variationsBps['30j'], -10.5);
  });
}
