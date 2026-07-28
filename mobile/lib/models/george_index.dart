/// Miroir de `api/schemas.py:GeorgeIndexOut`.
class GeorgeIndex {
  final int basketId;
  final String basketName;
  final double? georgeIndex;
  final double? performance1j;
  final double? performance1s;
  final double? performance1m;

  GeorgeIndex({
    required this.basketId,
    required this.basketName,
    required this.georgeIndex,
    required this.performance1j,
    required this.performance1s,
    required this.performance1m,
  });

  factory GeorgeIndex.fromJson(Map<String, dynamic> json) => GeorgeIndex(
        basketId: json['basket_id'] as int,
        basketName: json['basket_name'] as String,
        georgeIndex: (json['george_index'] as num?)?.toDouble(),
        performance1j: (json['performance_1j'] as num?)?.toDouble(),
        performance1s: (json['performance_1s'] as num?)?.toDouble(),
        performance1m: (json['performance_1m'] as num?)?.toDouble(),
      );
}
