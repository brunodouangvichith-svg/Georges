/// Miroir de `api/schemas.py:BasketOut`.
class Basket {
  final int id;
  final String name;
  final String type;

  Basket({required this.id, required this.name, required this.type});

  factory Basket.fromJson(Map<String, dynamic> json) => Basket(
        id: json['id'] as int,
        name: json['name'] as String,
        type: json['type'] as String,
      );
}
