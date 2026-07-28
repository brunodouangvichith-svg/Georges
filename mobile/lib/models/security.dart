/// Miroir de `api/schemas.py:SecurityOut`.
class Security {
  final String symbol;
  final String name;
  final String country;
  final String currency;
  final String sector;
  final String? theme;

  Security({
    required this.symbol,
    required this.name,
    required this.country,
    required this.currency,
    required this.sector,
    this.theme,
  });

  factory Security.fromJson(Map<String, dynamic> json) => Security(
        symbol: json['symbol'] as String,
        name: json['name'] as String,
        country: json['country'] as String,
        currency: json['currency'] as String,
        sector: json['sector'] as String,
        theme: json['theme'] as String?,
      );
}
