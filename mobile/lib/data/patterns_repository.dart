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
}

final patternsRepositoryProvider = Provider<PatternsRepository>((ref) => PatternsRepository(ref));

final securityPatternsProvider = FutureProvider.autoDispose.family<Page<Pattern>, String>((ref, symbol) {
  return ref.read(patternsRepositoryProvider).fetch(symbol, limit: 1);
});
