/// Miroirs des schémas Obligataire Watch de `api/schemas.py`
/// (BondYieldCardOut, BondDashboardOut, BondYieldHistoryPointOut,
/// BondAlertThresholdOut, BondAlertEventOut, BondBulletinOut,
/// BondRefreshResponse). Aucune valeur fabriquée : un instrument jamais
/// collecté garde `valuePct == null`.
class BondYieldCard {
  final String instrument;
  final double? valuePct;
  final String? observedAt;
  final String? sourceName;
  final String? sourceUrl;
  final Map<String, double?> variationsBps;

  BondYieldCard({
    required this.instrument,
    required this.valuePct,
    required this.observedAt,
    required this.sourceName,
    required this.sourceUrl,
    required this.variationsBps,
  });

  factory BondYieldCard.fromJson(Map<String, dynamic> json) {
    final raw = (json['variations_bps'] as Map<String, dynamic>?) ?? const {};
    return BondYieldCard(
      instrument: json['instrument'] as String,
      valuePct: (json['value_pct'] as num?)?.toDouble(),
      observedAt: json['observed_at'] as String?,
      sourceName: json['source_name'] as String?,
      sourceUrl: json['source_url'] as String?,
      variationsBps: raw.map((key, value) => MapEntry(key, (value as num?)?.toDouble())),
    );
  }
}

class BondDashboard {
  final List<BondYieldCard> cards;
  final double? spreadOatBundBps;
  final double? usCurveSlopeBps;

  BondDashboard({required this.cards, required this.spreadOatBundBps, required this.usCurveSlopeBps});

  factory BondDashboard.fromJson(Map<String, dynamic> json) => BondDashboard(
        cards: (json['cards'] as List).map((e) => BondYieldCard.fromJson(e as Map<String, dynamic>)).toList(),
        spreadOatBundBps: (json['spread_oat_bund_bps'] as num?)?.toDouble(),
        usCurveSlopeBps: (json['us_curve_slope_bps'] as num?)?.toDouble(),
      );
}

class BondHistoryPoint {
  final DateTime observedAt;
  final double valuePct;

  BondHistoryPoint({required this.observedAt, required this.valuePct});

  factory BondHistoryPoint.fromJson(Map<String, dynamic> json) => BondHistoryPoint(
        observedAt: DateTime.parse(json['observed_at'] as String),
        valuePct: (json['value_pct'] as num).toDouble(),
      );
}

class BondAlertThreshold {
  final int id;
  final String instrument;
  final String direction; // "above" | "below"
  final double thresholdPct;
  final bool enabled;
  final DateTime updatedAt;

  BondAlertThreshold({
    required this.id,
    required this.instrument,
    required this.direction,
    required this.thresholdPct,
    required this.enabled,
    required this.updatedAt,
  });

  factory BondAlertThreshold.fromJson(Map<String, dynamic> json) => BondAlertThreshold(
        id: json['id'] as int,
        instrument: json['instrument'] as String,
        direction: json['direction'] as String,
        thresholdPct: (json['threshold_pct'] as num).toDouble(),
        enabled: json['enabled'] as bool,
        updatedAt: DateTime.parse(json['updated_at'] as String),
      );
}

class BondAlertEvent {
  final int id;
  final String instrument;
  final double thresholdPct;
  final double observedValuePct;
  final String direction;
  final String status;
  final DateTime triggeredAt;
  final String message;

  BondAlertEvent({
    required this.id,
    required this.instrument,
    required this.thresholdPct,
    required this.observedValuePct,
    required this.direction,
    required this.status,
    required this.triggeredAt,
    required this.message,
  });

  factory BondAlertEvent.fromJson(Map<String, dynamic> json) => BondAlertEvent(
        id: json['id'] as int,
        instrument: json['instrument'] as String,
        thresholdPct: (json['threshold_pct'] as num).toDouble(),
        observedValuePct: (json['observed_value_pct'] as num).toDouble(),
        direction: json['direction'] as String,
        status: json['status'] as String,
        triggeredAt: DateTime.parse(json['triggered_at'] as String),
        message: json['message'] as String,
      );
}

class BondBulletin {
  final String bulletin;
  final DateTime generatedAt;

  BondBulletin({required this.bulletin, required this.generatedAt});

  factory BondBulletin.fromJson(Map<String, dynamic> json) => BondBulletin(
        bulletin: json['bulletin'] as String,
        generatedAt: DateTime.parse(json['generated_at'] as String),
      );
}

class BondRefreshResult {
  final List<String> instrumentsUpdated;
  final List<String> instrumentsFailed;
  final int alertsCreated;

  BondRefreshResult({required this.instrumentsUpdated, required this.instrumentsFailed, required this.alertsCreated});

  factory BondRefreshResult.fromJson(Map<String, dynamic> json) => BondRefreshResult(
        instrumentsUpdated: (json['instruments_updated'] as List).cast<String>(),
        instrumentsFailed: (json['instruments_failed'] as List).cast<String>(),
        alertsCreated: json['alerts_created'] as int,
      );
}
