/// Miroir de `api/schemas.py:EnergyPriceOut`.
class EnergyPrice {
  final String commodityCode;
  final double price;
  final String unit;
  final String currency;
  final double? change24hPct;
  final DateTime? priceObservedAt;
  final DateTime snapshotDate;

  EnergyPrice({
    required this.commodityCode,
    required this.price,
    required this.unit,
    required this.currency,
    this.change24hPct,
    this.priceObservedAt,
    required this.snapshotDate,
  });

  factory EnergyPrice.fromJson(Map<String, dynamic> json) => EnergyPrice(
        commodityCode: json['commodity_code'] as String,
        price: (json['price'] as num).toDouble(),
        unit: json['unit'] as String,
        currency: json['currency'] as String,
        change24hPct: (json['change_24h_pct'] as num?)?.toDouble(),
        priceObservedAt:
            json['price_observed_at'] != null ? DateTime.parse(json['price_observed_at'] as String) : null,
        snapshotDate: DateTime.parse(json['snapshot_date'] as String),
      );
}
