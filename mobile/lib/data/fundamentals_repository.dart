import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_exception.dart';
import '../core/providers.dart';
import '../models/dividend.dart';
import '../models/fundamentals.dart';
import '../models/page.dart';

/// Miroir de web/src/api/queries.js:useSecurityFundamentals/useSecurityDividends.
class FundamentalsRepository {
  FundamentalsRepository(this._ref);

  final Ref _ref;

  /// `null` avant le premier import quotidien pour ce titre (404 attendu,
  /// pas une vraie erreur — même principe que le 404 attendu ailleurs dans
  /// ce client pour une ressource pas encore créée).
  Future<Fundamentals?> fetch(String symbol) async {
    final client = _ref.read(apiClientProvider);
    try {
      final json = await client.get('/securities/$symbol/fundamentals');
      return Fundamentals.fromJson(json as Map<String, dynamic>);
    } on ApiException catch (e) {
      if (e.statusCode == 404) return null;
      rethrow;
    }
  }

  Future<Page<Dividend>> fetchDividends(String symbol, {int limit = 5}) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.get('/securities/$symbol/dividends', params: {'limit': limit});
    return Page.fromJson(json as Map<String, dynamic>, Dividend.fromJson);
  }
}

final fundamentalsRepositoryProvider = Provider<FundamentalsRepository>((ref) => FundamentalsRepository(ref));

final securityFundamentalsProvider = FutureProvider.autoDispose.family<Fundamentals?, String>((ref, symbol) {
  return ref.read(fundamentalsRepositoryProvider).fetch(symbol);
});

final securityDividendsProvider = FutureProvider.autoDispose.family<Page<Dividend>, String>((ref, symbol) {
  return ref.read(fundamentalsRepositoryProvider).fetchDividends(symbol, limit: 5);
});
