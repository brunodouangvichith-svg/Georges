import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/page.dart';
import '../models/security.dart';

/// Miroir de web/src/api/queries.js:useSecurities — un appel = une fonction.
class SecuritiesRepository {
  SecuritiesRepository(this._ref);

  final Ref _ref;

  Future<Page<Security>> fetch({int? basketId, int limit = 200}) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.get('/securities', params: {'basket_id': basketId, 'limit': limit});
    return Page.fromJson(json as Map<String, dynamic>, Security.fromJson);
  }
}

final securitiesRepositoryProvider = Provider<SecuritiesRepository>((ref) => SecuritiesRepository(ref));

/// Liste des titres suivis — équivalent de useSecurities({basketId}).
/// `.autoDispose` : mêmes règles de cache/libération que le comportement par
/// défaut de React Query (une requête sans observateur actif est libérée).
final securitiesProvider =
    FutureProvider.autoDispose.family<Page<Security>, int?>((ref, basketId) {
  return ref.read(securitiesRepositoryProvider).fetch(basketId: basketId);
});
