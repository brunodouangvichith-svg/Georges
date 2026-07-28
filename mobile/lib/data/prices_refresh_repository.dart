import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/price_refresh_response.dart';

/// Miroir de web/src/api/queries.js:useRefreshPrices — déclenchement manuel
/// de ingestion.ohlcv pour tout l'univers (~1 min), timeout allongé.
class PricesRefreshRepository {
  PricesRefreshRepository(this._ref);

  final Ref _ref;

  Future<PriceRefreshResponse> refresh() async {
    final client = _ref.read(apiClientProvider);
    final json = await client.post('/prices/refresh', receiveTimeout: const Duration(seconds: 120));
    return PriceRefreshResponse.fromJson(json as Map<String, dynamic>);
  }
}

final pricesRefreshRepositoryProvider = Provider<PricesRefreshRepository>((ref) => PricesRefreshRepository(ref));
