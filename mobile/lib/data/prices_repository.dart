import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/page.dart';
import '../models/price_bar.dart';

/// Miroir de web/src/api/queries.js:useSecurityPrices.
class PricesRepository {
  PricesRepository(this._ref);

  final Ref _ref;

  Future<Page<PriceBar>> fetch(String symbol, {int limit = 250}) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.get('/securities/$symbol/prices', params: {'limit': limit});
    return Page.fromJson(json as Map<String, dynamic>, PriceBar.fromJson);
  }
}

final pricesRepositoryProvider = Provider<PricesRepository>((ref) => PricesRepository(ref));

final securityPricesProvider = FutureProvider.autoDispose.family<Page<PriceBar>, String>((ref, symbol) {
  return ref.read(pricesRepositoryProvider).fetch(symbol, limit: 250);
});

/// Historique complet (jusqu'à 10 ans, price_history_long) pour le popup
/// agrandi du graphique — `securityPricesProvider` ci-dessus reste à 250
/// séances (~1 an) pour le petit graphique inline, volontairement léger ;
/// le popup, lui, doit montrer la vraie courbe sur toute sa profondeur
/// disponible plutôt qu'un simple extrait. `3000` correspond au plafond
/// réel de `GET /securities/{symbol}/prices` (~2600 séances sur 10 ans).
final securityFullPricesProvider = FutureProvider.autoDispose.family<Page<PriceBar>, String>((ref, symbol) {
  return ref.read(pricesRepositoryProvider).fetch(symbol, limit: 3000);
});
