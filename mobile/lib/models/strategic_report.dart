/// Miroir de `api/schemas.py:StrategicReportSummaryOut` / `StrategicReportOut`
/// (rapport stratégique hebdomadaire, agents/strategic_report.py). `data` est
/// gardé tel quel (JSON calculé en Python côté serveur) et lu via des
/// accesseurs tolérants : une clé absente ou nulle donne `null`, jamais une
/// valeur inventée.
class StrategicReportSummary {
  final int id;
  final DateTime createdAt;
  final String riskLevel;

  StrategicReportSummary({required this.id, required this.createdAt, required this.riskLevel});

  factory StrategicReportSummary.fromJson(Map<String, dynamic> json) => StrategicReportSummary(
        id: json['id'] as int,
        createdAt: DateTime.parse(json['created_at'] as String),
        riskLevel: json['risk_level'] as String,
      );
}

class StrategicReport extends StrategicReportSummary {
  final String narrativeMarkdown;
  final Map<String, dynamic> data;
  final String? modelUsed;

  StrategicReport({
    required super.id,
    required super.createdAt,
    required super.riskLevel,
    required this.narrativeMarkdown,
    required this.data,
    required this.modelUsed,
  });

  factory StrategicReport.fromJson(Map<String, dynamic> json) => StrategicReport(
        id: json['id'] as int,
        createdAt: DateTime.parse(json['created_at'] as String),
        riskLevel: json['risk_level'] as String,
        narrativeMarkdown: json['narrative_markdown'] as String? ?? '',
        data: (json['data'] as Map?)?.cast<String, dynamic>() ?? const {},
        modelUsed: json['model_used'] as String?,
      );

  Map<String, dynamic> get risk => _map(data['risk']);
  Map<String, dynamic>? get cac40Index => data['cac40_index'] == null ? null : _map(data['cac40_index']);
  Map<String, dynamic>? get portfolio => data['portfolio'] == null ? null : _map(data['portfolio']);
  List<Map<String, dynamic>> get cac40 => _list(data['cac40']);
  List<Map<String, dynamic>> get sources => _list(data['sources']);
  List<Map<String, dynamic>> get energy => _list(data['energy']);
  String? get pricesAsOf => data['prices_as_of'] as String?;
}

Map<String, dynamic> _map(Object? value) => (value as Map?)?.cast<String, dynamic>() ?? <String, dynamic>{};

List<Map<String, dynamic>> _list(Object? value) =>
    (value as List?)?.map((e) => (e as Map).cast<String, dynamic>()).toList() ?? const [];

/// Nombre JSON (int ou double) -> double, `null` si absent.
double? numOf(Object? value) => (value as num?)?.toDouble();

/// État du job de génération (`StrategicReportJobStatus`).
class StrategicReportJobStatus {
  final String status;
  final int? reportId;
  final String? error;

  StrategicReportJobStatus({required this.status, this.reportId, this.error});

  bool get isDone => status == 'done';
  bool get isFailed => status == 'failed';

  factory StrategicReportJobStatus.fromJson(Map<String, dynamic> json) => StrategicReportJobStatus(
        status: json['status'] as String,
        reportId: json['report_id'] as int?,
        error: json['error'] as String?,
      );
}
