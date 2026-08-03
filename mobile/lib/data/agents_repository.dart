import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/agent_event.dart';
import '../models/page.dart';

/// Miroir de web/src/api/queries.js:useAgentActivity. Le déclenchement
/// manuel de collecte (`useTriggerCollection`/`POST /agents/collect`) n'a
/// pas d'équivalent mobile — retiré ici à la demande directe de
/// l'utilisateur (bouton "Collecte macro" de l'écran Univers) ; `web/`
/// garde le sien.
class AgentsRepository {
  AgentsRepository(this._ref);

  final Ref _ref;

  Future<Page<AgentEvent>> fetchActivity({String? status, int limit = 6}) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.get('/agents/activity', params: {'status': status, 'limit': limit});
    return Page.fromJson(json as Map<String, dynamic>, AgentEvent.fromJson);
  }
}

final agentsRepositoryProvider = Provider<AgentsRepository>((ref) => AgentsRepository(ref));

final agentActivityProvider = FutureProvider.autoDispose<Page<AgentEvent>>((ref) {
  return ref.read(agentsRepositoryProvider).fetchActivity(limit: 6);
});
