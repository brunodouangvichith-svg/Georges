/// Miroir de `api/schemas.py:PatternOut`. `context` reste un `dict`/`Map`
/// libre côté API (une forme différente par type de pattern) — voir
/// `CandlestickChart`'s overlay, qui l'interprète génériquement plutôt que de
/// typer chaque forme possible.
class Pattern {
  final int id;
  final String symbol;
  final String patternType;
  final DateTime detectedAt;
  final double confidence;
  final Map<String, dynamic> context;

  Pattern({
    required this.id,
    required this.symbol,
    required this.patternType,
    required this.detectedAt,
    required this.confidence,
    required this.context,
  });

  factory Pattern.fromJson(Map<String, dynamic> json) => Pattern(
        id: json['id'] as int,
        symbol: json['symbol'] as String,
        patternType: json['pattern_type'] as String,
        detectedAt: DateTime.parse(json['detected_at'] as String),
        confidence: (json['confidence'] as num).toDouble(),
        context: Map<String, dynamic>.from(json['context'] as Map),
      );
}
