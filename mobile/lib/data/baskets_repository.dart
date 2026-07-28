import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/basket.dart';
import '../models/george_index.dart';

/// Miroir de web/src/api/queries.js:useBaskets/useGeorgeIndex. `/baskets`
/// renvoie une liste brute (pas de `Page[T]`), voir api/routers/baskets.py.
class BasketsRepository {
  BasketsRepository(this._ref);

  final Ref _ref;

  Future<List<Basket>> fetch() async {
    final client = _ref.read(apiClientProvider);
    final json = await client.get('/baskets');
    return (json as List).map((e) => Basket.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<GeorgeIndex> georgeIndex(int basketId) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.get('/baskets/$basketId/george-index');
    return GeorgeIndex.fromJson(json as Map<String, dynamic>);
  }
}

final basketsRepositoryProvider = Provider<BasketsRepository>((ref) => BasketsRepository(ref));

final basketsProvider = FutureProvider.autoDispose<List<Basket>>((ref) {
  return ref.read(basketsRepositoryProvider).fetch();
});

final georgeIndexProvider = FutureProvider.autoDispose.family<GeorgeIndex, int>((ref, basketId) {
  return ref.read(basketsRepositoryProvider).georgeIndex(basketId);
});
