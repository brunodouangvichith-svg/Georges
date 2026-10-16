import 'package:dio/dio.dart';

import 'api_exception.dart';
import 'auth/auth_interceptor.dart';
import 'env.dart';

/// Wrapper HTTP (get/post/patch/delete) — miroir de web/src/api/client.js
/// (`apiFetch`/`apiPost`/`apiDelete`). Le `receiveTimeout` par défaut doit
/// couvrir le cold start du plan gratuit Render (`george-api`, voir
/// CLAUDE.md section Hosting) — le service se met en veille après une
/// période d'inactivité et peut mettre jusqu'à ~50s à répondre au premier
/// appel suivant, ce qui n'est pas une vraie panne mais se comportait comme
/// telle avec l'ancien défaut de 30s (calé sur un backend local toujours
/// éveillé) : l'app affichait "Impossible de contacter l'API" alors que le
/// service était juste en train de se réveiller. Les appels backend
/// connus pour être lents pour d'autres raisons (/agents/collect,
/// /decisions/{id}/explanation, /chat) passent un `receiveTimeout` encore
/// plus long explicitement au niveau de l'appel. `/prices/refresh` n'en a
/// plus besoin depuis qu'il est asynchrone côté serveur (statut + polling,
/// voir `PricesRefreshRepository`) : chaque appel HTTP individuel reste
/// rapide, seule la boucle de polling dure longtemps.
class ApiClient {
  final Dio _dio;

  ApiClient()
      : _dio = Dio(BaseOptions(
          baseUrl: apiBaseUrl,
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 60),
        )) {
    _dio.interceptors.add(AuthInterceptor());
  }

  Future<dynamic> get(String path, {Map<String, dynamic>? params, Duration? receiveTimeout}) async {
    try {
      final response = await _dio.get(
        path,
        queryParameters: _cleanParams(params),
        options: Options(receiveTimeout: receiveTimeout),
      );
      return response.data;
    } on DioException catch (e) {
      throw _toApiException(path, e);
    }
  }

  Future<dynamic> post(String path, {Map<String, dynamic>? body, Duration? receiveTimeout}) async {
    try {
      final response = await _dio.post(
        path,
        data: body ?? {},
        options: Options(receiveTimeout: receiveTimeout),
      );
      return response.data;
    } on DioException catch (e) {
      throw _toApiException(path, e);
    }
  }

  /// Mise à jour partielle — miroir de `apiPatch` (web/src/api/client.js),
  /// utilisée par l'édition des seuils d'alerte obligataires. Seuls les champs
  /// présents dans [body] sont modifiés côté serveur.
  Future<dynamic> patch(String path, {Map<String, dynamic>? body}) async {
    try {
      final response = await _dio.patch(path, data: body ?? {});
      return response.data;
    } on DioException catch (e) {
      throw _toApiException(path, e);
    }
  }

  Future<dynamic> delete(String path) async {
    try {
      final response = await _dio.delete(path);
      return response.statusCode == 204 ? null : response.data;
    } on DioException catch (e) {
      throw _toApiException(path, e);
    }
  }

  Map<String, dynamic>? _cleanParams(Map<String, dynamic>? params) {
    if (params == null) return null;
    final cleaned = <String, dynamic>{};
    for (final entry in params.entries) {
      if (entry.value != null && entry.value != '') cleaned[entry.key] = entry.value;
    }
    return cleaned;
  }

  ApiException _toApiException(String path, DioException e) {
    final statusCode = e.response?.statusCode;
    if (statusCode != null) {
      // FastAPI renvoie le motif lisible dans `detail` (ex. 409 "Décision 12
      // n'est plus au statut 'proposee'.") — plus utile à afficher que le
      // simple libellé HTTP.
      final data = e.response?.data;
      final detail = data is Map && data['detail'] is String ? data['detail'] as String : null;
      return ApiException(
        path: path,
        statusCode: statusCode,
        message: detail ?? e.response?.statusMessage ?? e.message ?? '',
      );
    }
    return ApiException(path: path, message: e.message ?? 'Erreur réseau');
  }
}
