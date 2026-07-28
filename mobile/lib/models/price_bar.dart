/// Miroir de `api/schemas.py:PriceBarOut`.
class PriceBar {
  final DateTime ts;
  final double open;
  final double high;
  final double low;
  final double close;
  final int volume;

  PriceBar({
    required this.ts,
    required this.open,
    required this.high,
    required this.low,
    required this.close,
    required this.volume,
  });

  factory PriceBar.fromJson(Map<String, dynamic> json) => PriceBar(
        ts: DateTime.parse(json['ts'] as String),
        open: (json['open'] as num).toDouble(),
        high: (json['high'] as num).toDouble(),
        low: (json['low'] as num).toDouble(),
        close: (json['close'] as num).toDouble(),
        volume: json['volume'] as int,
      );
}
