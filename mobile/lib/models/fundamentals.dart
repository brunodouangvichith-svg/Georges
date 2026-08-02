/// Miroir de `api/schemas.py:FundamentalsOut`. Toutes les colonnes de
/// contenu sont nullables côté schéma (couverture yfinance bonne mais pas
/// garantie champ par champ, voir `ingestion/models.py:CompanyFundamentals`).
class Fundamentals {
  final String symbol;
  final DateTime observedAt;
  final String? sector;
  final String? industry;
  final String? country;
  final String? currency;
  final String? exchange;
  final String? longName;
  final String? website;
  final String? longBusinessSummary;
  final int? fullTimeEmployees;
  final int? marketCap;
  final double? trailingPe;
  final double? forwardPe;
  final double? dividendYield;
  final double? beta;
  final double? fiftyTwoWeekHigh;
  final double? fiftyTwoWeekLow;

  Fundamentals({
    required this.symbol,
    required this.observedAt,
    this.sector,
    this.industry,
    this.country,
    this.currency,
    this.exchange,
    this.longName,
    this.website,
    this.longBusinessSummary,
    this.fullTimeEmployees,
    this.marketCap,
    this.trailingPe,
    this.forwardPe,
    this.dividendYield,
    this.beta,
    this.fiftyTwoWeekHigh,
    this.fiftyTwoWeekLow,
  });

  factory Fundamentals.fromJson(Map<String, dynamic> json) => Fundamentals(
        symbol: json['symbol'] as String,
        observedAt: DateTime.parse(json['observed_at'] as String),
        sector: json['sector'] as String?,
        industry: json['industry'] as String?,
        country: json['country'] as String?,
        currency: json['currency'] as String?,
        exchange: json['exchange'] as String?,
        longName: json['long_name'] as String?,
        website: json['website'] as String?,
        longBusinessSummary: json['long_business_summary'] as String?,
        fullTimeEmployees: json['full_time_employees'] as int?,
        marketCap: json['market_cap'] as int?,
        trailingPe: (json['trailing_pe'] as num?)?.toDouble(),
        forwardPe: (json['forward_pe'] as num?)?.toDouble(),
        dividendYield: (json['dividend_yield'] as num?)?.toDouble(),
        beta: (json['beta'] as num?)?.toDouble(),
        fiftyTwoWeekHigh: (json['fifty_two_week_high'] as num?)?.toDouble(),
        fiftyTwoWeekLow: (json['fifty_two_week_low'] as num?)?.toDouble(),
      );
}
