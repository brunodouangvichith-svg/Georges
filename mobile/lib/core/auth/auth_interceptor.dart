import 'package:dio/dio.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// Pose l'en-tête `Authorization: Bearer <jeton>` sur chaque appel API à
/// partir de la session Supabase active — parle directement au singleton
/// `Supabase.instance.client` plutôt que de lire un `Ref` Riverpod, pour que
/// `ApiClient` (`core/api_client.dart`) reste indépendant de Riverpod comme
/// aujourd'hui. Un utilisateur non connecté (`currentSession == null`,
/// avant login ou après déconnexion) envoie simplement la requête sans
/// en-tête ; le backend répond alors 401 (voir `api/auth.py:require_user`).
class AuthInterceptor extends QueuedInterceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final accessToken = Supabase.instance.client.auth.currentSession?.accessToken;
    if (accessToken != null) {
      options.headers['Authorization'] = 'Bearer $accessToken';
    }
    handler.next(options);
  }
}
