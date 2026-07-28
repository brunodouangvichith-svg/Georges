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
