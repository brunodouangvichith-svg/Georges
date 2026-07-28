import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/agent_event.dart';
import '../models/collection_task_response.dart';
import '../models/page.dart';

/// Miroir de web/src/api/queries.js:useAgentActivity/useTriggerCollection.
class AgentsRepository {
  AgentsRepository(this._ref);

  final Ref _ref;

  Future<Page<AgentEvent>> fetchActivity({String? status, int limit = 6}) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.get('/agents/activity', params: {'status': status, 'limit': limit});
    return Page.fromJson(json as Map<String, dynamic>, AgentEvent.fromJson);
  }

  /// Interroge FRED/BCE côté serveur — timeout allongé comme les autres
  /// appels réseau lents (voir lib/core/api_client.dart).
  Future<CollectionTaskResponse> collect(String taskType, {int? reportId}) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.post(
      '/agents/collect',
      body: {'task_type': taskType, 'report_id': reportId},
      receiveTimeout: const Duration(seconds: 90),
    );
    return CollectionTaskResponse.fromJson(json as Map<String, dynamic>);
  }
}

final agentsRepositoryProvider = Provider<AgentsRepository>((ref) => AgentsRepository(ref));

final agentActivityProvider = FutureProvider.autoDispose<Page<AgentEvent>>((ref) {
  return ref.read(agentsRepositoryProvider).fetchActivity(limit: 6);
});
