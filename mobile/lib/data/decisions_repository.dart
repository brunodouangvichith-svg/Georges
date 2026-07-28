import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/decision.dart';
import '../models/explanation.dart';
import '../models/page.dart';

/// Miroir de web/src/api/queries.js:useDecisions/useExplainDecision.
class DecisionsRepository {
  DecisionsRepository(this._ref);

  final Ref _ref;

  Future<Page<Decision>> fetch({String? decisionType, String? status, int? basketId, int limit = 200}) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.get('/decisions', params: {
      'decision_type': decisionType,
      'status': status,
      'basket_id': basketId,
      'limit': limit,
    });
    return Page.fromJson(json as Map<String, dynamic>, Decision.fromJson);
  }

  /// Appel LLM (Mistral côté backend) — timeout allongé, voir
  /// lib/core/api_client.dart pour la justification.
  Future<Explanation> explain(int decisionId, {bool includeSecondOpinion = false}) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.post(
      '/decisions/$decisionId/explanation',
      body: {'include_second_opinion': includeSecondOpinion},
      receiveTimeout: const Duration(seconds: 90),
    );
    return Explanation.fromJson(json as Map<String, dynamic>);
  }
}

final decisionsRepositoryProvider = Provider<DecisionsRepository>((ref) => DecisionsRepository(ref));

class DecisionsFilter {
  final String? decisionType;
  final String? status;
  final int? basketId;

  const DecisionsFilter({this.decisionType, this.status, this.basketId});

  @override
  bool operator ==(Object other) =>
      other is DecisionsFilter &&
      other.decisionType == decisionType &&
      other.status == status &&
      other.basketId == basketId;

  @override
  int get hashCode => Object.hash(decisionType, status, basketId);
}

final decisionsProvider = FutureProvider.autoDispose.family<Page<Decision>, DecisionsFilter>((ref, filter) {
  return ref.read(decisionsRepositoryProvider).fetch(
        decisionType: filter.decisionType,
        status: filter.status,
        basketId: filter.basketId,
      );
});
