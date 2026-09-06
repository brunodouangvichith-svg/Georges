/// Miroir de `api/schemas.py:PriceRefreshStatus`. Remplace
/// `PriceRefreshResponse` : le backend répond désormais immédiatement avec
/// un statut (voir `PricesRefreshRepository.refresh`, qui fait le polling).
class PriceRefreshStatus {
  final String status; // "idle" | "running" | "done" | "failed"
  final int? total;
  final int? updatedCount;
  final List<String>? failedSymbols;
  final String? error;

  PriceRefreshStatus({
    required this.status,
    this.total,
    this.updatedCount,
    this.failedSymbols,
    this.error,
  });

  bool get isRunning => status == 'running';
  bool get isDone => status == 'done';
  bool get isFailed => status == 'failed';

  factory PriceRefreshStatus.fromJson(Map<String, dynamic> json) => PriceRefreshStatus(
        status: json['status'] as String,
        total: json['total'] as int?,
        updatedCount: json['updated_count'] as int?,
        failedSymbols: (json['failed_symbols'] as List?)?.cast<String>(),
        error: json['error'] as String?,
      );
}
