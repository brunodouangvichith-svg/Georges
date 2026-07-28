/// Enveloppe de pagination générique — miroir de `api/schemas.py:Page[T]`,
/// partagée par toutes les listes de l'API.
class Page<T> {
  final List<T> items;
  final int total;
  final int limit;
  final int offset;

  Page({required this.items, required this.total, required this.limit, required this.offset});

  factory Page.fromJson(Map<String, dynamic> json, T Function(Map<String, dynamic>) fromJsonT) {
    return Page<T>(
      items: (json['items'] as List).map((e) => fromJsonT(e as Map<String, dynamic>)).toList(),
      total: json['total'] as int,
      limit: json['limit'] as int,
      offset: json['offset'] as int,
    );
  }
}
