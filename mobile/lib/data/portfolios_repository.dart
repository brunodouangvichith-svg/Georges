import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/allocate_budget_response.dart';
import '../models/portfolio.dart';

/// Miroir de web/src/api/queries.js:usePortfolios/useCreatePortfolio/
/// useDeletePortfolio/useRemoveDecisionFromPortfolio/useAllocateBudget.
/// `/portfolios` renvoie une liste brute (pas de `Page[T]`).
class PortfoliosRepository {
  PortfoliosRepository(this._ref);

  final Ref _ref;

  Future<List<Portfolio>> fetch() async {
    final client = _ref.read(apiClientProvider);
    final json = await client.get('/portfolios');
    return (json as List).map((e) => Portfolio.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Portfolio> create(String name, List<int> decisionIds) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.post('/portfolios', body: {'name': name, 'decision_ids': decisionIds});
    return Portfolio.fromJson(json as Map<String, dynamic>);
  }

  Future<void> delete(int portfolioId) async {
    final client = _ref.read(apiClientProvider);
    await client.delete('/portfolios/$portfolioId');
  }

  Future<Portfolio> removeDecision(int portfolioId, int decisionId) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.delete('/portfolios/$portfolioId/decisions/$decisionId');
    return Portfolio.fromJson(json as Map<String, dynamic>);
  }

  /// Calcul déterministe côté serveur (engine/portfolio_allocation.py), pas
  /// un appel LLM — pas de timeout allongé nécessaire ici.
  Future<AllocateBudgetResponse> allocate(int portfolioId, double budget) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.post('/portfolios/$portfolioId/allocate', body: {'budget': budget});
    return AllocateBudgetResponse.fromJson(json as Map<String, dynamic>);
  }
}

final portfoliosRepositoryProvider = Provider<PortfoliosRepository>((ref) => PortfoliosRepository(ref));

final portfoliosProvider = FutureProvider.autoDispose<List<Portfolio>>((ref) {
  return ref.read(portfoliosRepositoryProvider).fetch();
});
