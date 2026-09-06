import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';

/// Miroir de `data/chat_repository.dart` — appel LLM, timeout allongé.
/// Interroge `agents/jane.py:ask` (POST /jane/ask), la base de connaissances
/// de Jane, en dehors de tout contexte de décision. Distinct de
/// `ChatRepository`, qui répond sur les titres/décisions suivis par George.
class JaneRepository {
  JaneRepository(this._ref);

  final Ref _ref;

  Future<String> ask(String question) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.post(
      '/jane/ask',
      body: {'question': question},
      receiveTimeout: const Duration(seconds: 90),
    );
    return (json as Map<String, dynamic>)['answer'] as String;
  }
}

final janeRepositoryProvider = Provider<JaneRepository>(
  (ref) => JaneRepository(ref),
);
