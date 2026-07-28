import 'agent_event.dart';

/// Miroir de `api/schemas.py:CollectionTaskResponse`.
class CollectionTaskResponse {
  final List<AgentEvent> validated;
  final int quarantinedCount;

  CollectionTaskResponse({required this.validated, required this.quarantinedCount});

  factory CollectionTaskResponse.fromJson(Map<String, dynamic> json) => CollectionTaskResponse(
        validated: (json['validated'] as List).map((e) => AgentEvent.fromJson(e as Map<String, dynamic>)).toList(),
        quarantinedCount: json['quarantined_count'] as int,
      );
}
