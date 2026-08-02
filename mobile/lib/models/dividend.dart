/// Miroir de `api/schemas.py:DividendOut`.
class Dividend {
  final String symbol;
  final DateTime exDate;
  final double amount;

  Dividend({required this.symbol, required this.exDate, required this.amount});

  factory Dividend.fromJson(Map<String, dynamic> json) => Dividend(
        symbol: json['symbol'] as String,
        exDate: DateTime.parse(json['ex_date'] as String),
        amount: (json['amount'] as num).toDouble(),
      );
}
