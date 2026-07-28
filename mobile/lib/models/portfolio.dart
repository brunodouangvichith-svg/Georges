import 'decision.dart';

/// Miroir de `api/schemas.py:PortfolioDecisionOut` (= DecisionOut + les
/// champs calculés à la volée par `api/routers/portfolios.py`). Composition
/// plutôt qu'héritage : `decision` porte les champs communs, les champs
/// supplémentaires sont ajoutés à côté.
class PortfolioDecision {
  final Decision decision;
  final int? quantity;
  final double? currentPrice;
  final double? pnlPct;
  final DateTime? priceUpdatedAt;

  PortfolioDecision({
    required this.decision,
    required this.quantity,
    required this.currentPrice,
    required this.pnlPct,
    required this.priceUpdatedAt,
  });

  factory PortfolioDecision.fromJson(Map<String, dynamic> json) => PortfolioDecision(
        decision: Decision.fromJson(json),
        quantity: json['quantity'] as int?,
        currentPrice: (json['current_price'] as num?)?.toDouble(),
        pnlPct: (json['pnl_pct'] as num?)?.toDouble(),
        priceUpdatedAt: json['price_updated_at'] != null ? DateTime.parse(json['price_updated_at'] as String) : null,
      );
}

/// Miroir de `api/schemas.py:PortfolioOut`.
class Portfolio {
  final int id;
  final String name;
  final DateTime createdAt;
  final List<PortfolioDecision> decisions;
  final double? totalPnlAmount;
  final double? totalInvested;

  Portfolio({
    required this.id,
    required this.name,
    required this.createdAt,
    required this.decisions,
    required this.totalPnlAmount,
    required this.totalInvested,
  });

  factory Portfolio.fromJson(Map<String, dynamic> json) => Portfolio(
        id: json['id'] as int,
        name: json['name'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
        decisions: (json['decisions'] as List)
            .map((e) => PortfolioDecision.fromJson(e as Map<String, dynamic>))
            .toList(),
        totalPnlAmount: (json['total_pnl_amount'] as num?)?.toDouble(),
        totalInvested: (json['total_invested'] as num?)?.toDouble(),
      );
}
