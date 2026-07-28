import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';

/// Miroir de web/src/api/queries.js:useChat — appel LLM, timeout allongé.
class ChatRepository {
  ChatRepository(this._ref);

  final Ref _ref;

  Future<String> ask(String question) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.post(
      '/chat',
      body: {'question': question},
      receiveTimeout: const Duration(seconds: 90),
    );
    return (json as Map<String, dynamic>)['answer'] as String;
  }
}

final chatRepositoryProvider = Provider<ChatRepository>((ref) => ChatRepository(ref));
