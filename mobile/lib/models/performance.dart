/// Miroir de `api/schemas.py:PerformanceOut` (GET /decisions/performance,
/// calculs dans engine/performance.py). Les moyennes valent `null` quand il
/// n'y a rien à moyenner — jamais un 0 fabriqué. `totalPnlPct` est une somme
/// de %, pas un rendement composé.
class PerformanceStats {
  final int count;
  final int wins;
  final int losses;
  final double? winRatePct;
  final double? avgPnlPct;
  final double? avgGainPct;
  final double? avgLossPct;
  final double? totalPnlPct;
  final double? bestPnlPct;
  final double? worstPnlPct;

  PerformanceStats({
    required this.count,
    required this.wins,
    required this.losses,
    required this.winRatePct,
    required this.avgPnlPct,
    required this.avgGainPct,
    required this.avgLossPct,
    required this.totalPnlPct,
    required this.bestPnlPct,
    required this.worstPnlPct,
  });

  factory PerformanceStats.fromJson(Map<String, dynamic> json) => PerformanceStats(
        count: json['count'] as int,
        wins: json['wins'] as int,
        losses: json['losses'] as int,
        winRatePct: _toDouble(json['win_rate_pct']),
        avgPnlPct: _toDouble(json['avg_pnl_pct']),
        avgGainPct: _toDouble(json['avg_gain_pct']),
        avgLossPct: _toDouble(json['avg_loss_pct']),
        totalPnlPct: _toDouble(json['total_pnl_pct']),
        bestPnlPct: _toDouble(json['best_pnl_pct']),
        worstPnlPct: _toDouble(json['worst_pnl_pct']),
      );
}

class PatternPerformance {
  final String patternType;
  final PerformanceStats stats;

  PatternPerformance({required this.patternType, required this.stats});

  factory PatternPerformance.fromJson(Map<String, dynamic> json) => PatternPerformance(
        patternType: json['pattern_type'] as String,
        stats: PerformanceStats.fromJson(json),
      );
}

class TradeOutcome {
  final int decisionId;
  final String symbol;
  final String decisionType;
  final String? patternType;
  final double entryPrice;
  final String result; // "take_profit_hit" | "stop_loss_hit"
  final double pnlPct;
  final DateTime closedAt;

  TradeOutcome({
    required this.decisionId,
    required this.symbol,
    required this.decisionType,
    required this.patternType,
    required this.entryPrice,
    required this.result,
    required this.pnlPct,
    required this.closedAt,
  });

  factory TradeOutcome.fromJson(Map<String, dynamic> json) => TradeOutcome(
        decisionId: json['decision_id'] as int,
        symbol: json['symbol'] as String,
        decisionType: json['decision_type'] as String,
        patternType: json['pattern_type'] as String?,
        entryPrice: (json['entry_price'] as num).toDouble(),
        result: json['result'] as String,
        pnlPct: (json['pnl_pct'] as num).toDouble(),
        closedAt: DateTime.parse(json['closed_at'] as String),
      );
}

class Performance {
  final PerformanceStats summary;
  final List<PatternPerformance> byPattern;
  final List<TradeOutcome> trades;

  Performance({required this.summary, required this.byPattern, required this.trades});

  factory Performance.fromJson(Map<String, dynamic> json) => Performance(
        summary: PerformanceStats.fromJson(json['summary'] as Map<String, dynamic>),
        byPattern: (json['by_pattern'] as List)
            .map((e) => PatternPerformance.fromJson(e as Map<String, dynamic>))
            .toList(),
        trades: (json['trades'] as List).map((e) => TradeOutcome.fromJson(e as Map<String, dynamic>)).toList(),
      );
}

double? _toDouble(Object? value) => value == null ? null : (value as num).toDouble();
