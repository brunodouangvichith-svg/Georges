/// Miroir de `api/schemas.py:AgentEventOut`.
class AgentEvent {
  final int id;
  final String agentName;
  final String description;
  final String status;
  final String? symbol;
  final DateTime createdAt;

  AgentEvent({
    required this.id,
    required this.agentName,
    required this.description,
    required this.status,
    required this.symbol,
    required this.createdAt,
  });

  factory AgentEvent.fromJson(Map<String, dynamic> json) => AgentEvent(
        id: json['id'] as int,
        agentName: json['agent_name'] as String,
        description: json['description'] as String,
        status: json['status'] as String,
        symbol: json['symbol'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}
