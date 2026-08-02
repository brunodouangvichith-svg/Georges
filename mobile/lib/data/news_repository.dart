import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/news_item.dart';

/// Miroir de `api/routers/news.py` — pas de pagination (`Page[T]`), c'est
/// une liste brute d'au plus 10 actualités, même précédent que `GET /baskets`.
class NewsRepository {
  NewsRepository(this._ref);

  final Ref _ref;

  Future<List<NewsItem>> fetch() async {
    final client = _ref.read(apiClientProvider);
    final json = await client.get('/news');
    return (json as List).map((e) => NewsItem.fromJson(e as Map<String, dynamic>)).toList();
  }
}

final newsRepositoryProvider = Provider<NewsRepository>((ref) => NewsRepository(ref));

final newsProvider = FutureProvider.autoDispose<List<NewsItem>>((ref) {
  return ref.read(newsRepositoryProvider).fetch();
});
