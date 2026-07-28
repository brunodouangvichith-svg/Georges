import 'portfolio.dart';

/// Miroir de `api/schemas.py:AllocateBudgetResponse`.
class AllocateBudgetResponse {
  final Portfolio portfolio;
  final String summary;

  AllocateBudgetResponse({required this.portfolio, required this.summary});

  factory AllocateBudgetResponse.fromJson(Map<String, dynamic> json) => AllocateBudgetResponse(
        portfolio: Portfolio.fromJson(json['portfolio'] as Map<String, dynamic>),
        summary: json['summary'] as String,
      );
}
