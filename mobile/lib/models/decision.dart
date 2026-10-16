/// Miroir de `api/schemas.py:DecisionOut`.
///
/// Les champs `exit*` ne sont remplis que par le job de suivi (statut
/// `sortie_proposee`, voir engine/monitor_decisions.py) — optionnels dans le
/// constructeur pour ne pas obliger les écrans/tests qui n'en ont pas besoin à
/// les fournir.
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
  final String? exitScenario;
  final bool? exitVolumeConfirmed;
  final String? exitJustification;
  final DateTime? exitProposedAt;

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
    this.exitScenario,
    this.exitVolumeConfirmed,
    this.exitJustification,
    this.exitProposedAt,
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
        exitScenario: json['exit_scenario'] as String?,
        exitVolumeConfirmed: json['exit_volume_confirmed'] as bool?,
        exitJustification: json['exit_justification'] as String?,
        exitProposedAt: json['exit_proposed_at'] == null ? null : DateTime.parse(json['exit_proposed_at'] as String),
      );
}
