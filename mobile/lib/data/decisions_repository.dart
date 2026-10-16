import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/decision.dart';
import '../models/explanation.dart';
import '../models/page.dart';
import '../models/performance.dart';

/// Miroir de web/src/api/queries.js:useDecisions/useExplainDecision et des
/// mutations du cycle de vie (useConfirmDecision, useProposeLevels,
/// useConfirmExit, useProposeDecisions, useMonitorDecisions, usePerformance).
/// George ne passe jamais d'ordre : « confirmer » enregistre seulement une
/// position suivie, « confirmer la sortie » la clôture et écrit son résultat
/// dans decision_outcomes (voir api/routers/decisions.py).
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

  /// Valide une décision `proposee`. [takeProfit]/[stopLoss] ne sont envoyés
  /// que s'ils ont été modifiés (null = garder la valeur proposée).
  Future<Decision> confirm(int decisionId, {double? takeProfit, double? stopLoss}) async {
    final client = _ref.read(apiClientProvider);
    final body = <String, dynamic>{};
    if (takeProfit != null) body['take_profit'] = takeProfit;
    if (stopLoss != null) body['stop_loss'] = stopLoss;
    final json = await client.post('/decisions/$decisionId/confirm', body: body);
    return Decision.fromJson(json as Map<String, dynamic>);
  }

  /// Recalcule take-profit/stop-loss d'une décision `proposee` sur le dernier prix.
  Future<Decision> proposeLevels(int decisionId) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.post('/decisions/$decisionId/propose-levels');
    return Decision.fromJson(json as Map<String, dynamic>);
  }

  /// Clôture définitive d'une décision `sortie_proposee`.
  Future<Decision> confirmExit(int decisionId) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.post('/decisions/$decisionId/confirm-exit');
    return Decision.fromJson(json as Map<String, dynamic>);
  }

  /// Lance la détection de nouvelles propositions. Renvoie le nombre créé.
  Future<int> proposeNew() async {
    final client = _ref.read(apiClientProvider);
    final json = await client.post('/decisions/propose', receiveTimeout: const Duration(seconds: 120));
    return (json as List).length;
  }

  /// Lance le job de suivi des positions. Renvoie le nombre de sorties proposées.
  Future<int> monitor() async {
    final client = _ref.read(apiClientProvider);
    final json = await client.post('/decisions/monitor', receiveTimeout: const Duration(seconds: 120));
    return (json as List).length;
  }

  Future<Performance> performance() async {
    final client = _ref.read(apiClientProvider);
    final json = await client.get('/decisions/performance');
    return Performance.fromJson(json as Map<String, dynamic>);
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

/// Performance réalisée (positions clôturées uniquement).
final performanceProvider = FutureProvider.autoDispose<Performance>((ref) {
  return ref.read(decisionsRepositoryProvider).performance();
});
