import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/page.dart';
import '../models/pattern.dart';

/// Miroir de web/src/api/queries.js:useSecurityPatterns.
class PatternsRepository {
  PatternsRepository(this._ref);

  final Ref _ref;

  Future<Page<Pattern>> fetch(String symbol, {int limit = 1}) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.get('/securities/$symbol/patterns', params: {'limit': limit});
    return Page.fromJson(json as Map<String, dynamic>, Pattern.fromJson);
  }

  /// Dernière figure de chaque titre en une seule requête
  /// (`GET /securities/patterns/latest`), indexée par symbole. Un titre sans
  /// figure est absent de la map.
  Future<Map<String, Pattern>> fetchLatest() async {
    final client = _ref.read(apiClientProvider);
    final json = await client.get('/securities/patterns/latest');
    return {
      for (final item in json as List)
        if (item is Map) (item['symbol'] as String): Pattern.fromJson(Map<String, dynamic>.from(item)),
    };
  }
}

final patternsRepositoryProvider = Provider<PatternsRepository>((ref) => PatternsRepository(ref));

final securityPatternsProvider = FutureProvider.autoDispose.family<Page<Pattern>, String>((ref, symbol) {
  return ref.read(patternsRepositoryProvider).fetch(symbol, limit: 1);
});

/// Radar de l'écran Univers : une requête pour tout l'univers au lieu d'un
/// `securityPatternsProvider` par titre (~100 appels, qui saturaient le pool
/// de connexions de l'API — même correction que côté web).
final latestPatternsProvider = FutureProvider.autoDispose<Map<String, Pattern>>((ref) {
  return ref.read(patternsRepositoryProvider).fetchLatest();
});
