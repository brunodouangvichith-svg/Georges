import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';

/// Miroir de `api/schemas.py:ShareEmailResponse`.
class ShareEmailResult {
  final bool sent;
  final bool chartAttached;

  ShareEmailResult({required this.sent, required this.chartAttached});

  factory ShareEmailResult.fromJson(Map<String, dynamic> json) => ShareEmailResult(
        sent: json['sent'] as bool,
        chartAttached: json['chart_attached'] as bool,
      );
}

/// Partage par email d'une popup de réponse de George (ad hoc, pas une
/// phase du roadmap) — le texte est reformulé côté serveur (Mistral) et,
/// si `symbol` est fourni, le graphique 10 ans du titre est joint en pièce
/// jointe. Timeout allongé comme les autres appels LLM/longs de ce client
/// (rendu d'image + reformulation + envoi Resend, tous bloquants côté API).
class ShareRepository {
  ShareRepository(this._ref);

  final Ref _ref;

  Future<ShareEmailResult> shareByEmail({
    required String toEmail,
    required String subject,
    required String text,
    String? symbol,
  }) async {
    final client = _ref.read(apiClientProvider);
    final json = await client.post(
      '/share/email',
      body: {
        'to_email': toEmail,
        'subject': subject,
        'text': text,
        if (symbol != null) 'symbol': symbol,
      },
      receiveTimeout: const Duration(seconds: 90),
    );
    return ShareEmailResult.fromJson(json as Map<String, dynamic>);
  }
}

final shareRepositoryProvider = Provider<ShareRepository>((ref) => ShareRepository(ref));
