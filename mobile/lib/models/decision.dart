/// Miroir de `api/schemas.py:DecisionOut`.
class Decision {
  final int id;
  final String symbol;
  final int? patternId;
  final String decisionType;
  final String status;
  final double entryPrice;
  final double? takeProfit;
  final double? stopLoss;
  final double confidence;
  final String? rationale;
  final DateTime createdAt;

  Decision({
    required this.id,
    required this.symbol,
    required this.patternId,
    required this.decisionType,
    required this.status,
    required this.entryPrice,
    required this.takeProfit,
    required this.stopLoss,
    required this.confidence,
    required this.rationale,
    required this.createdAt,
  });

  factory Decision.fromJson(Map<String, dynamic> json) => Decision(
        id: json['id'] as int,
        symbol: json['symbol'] as String,
        patternId: json['pattern_id'] as int?,
        decisionType: json['decision_type'] as String,
        status: json['status'] as String,
        entryPrice: (json['entry_price'] as num).toDouble(),
        takeProfit: (json['take_profit'] as num?)?.toDouble(),
        stopLoss: (json['stop_loss'] as num?)?.toDouble(),
        confidence: (json['confidence'] as num).toDouble(),
        rationale: json['rationale'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}
