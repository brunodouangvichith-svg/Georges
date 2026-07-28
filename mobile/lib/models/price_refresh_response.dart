/// Miroir de `api/schemas.py:PriceRefreshResponse`.
class PriceRefreshResponse {
  final int total;
  final int updatedCount;
  final List<String> failedSymbols;

  PriceRefreshResponse({required this.total, required this.updatedCount, required this.failedSymbols});

  factory PriceRefreshResponse.fromJson(Map<String, dynamic> json) => PriceRefreshResponse(
        total: json['total'] as int,
        updatedCount: json['updated_count'] as int,
        failedSymbols: (json['failed_symbols'] as List).cast<String>(),
      );
}
