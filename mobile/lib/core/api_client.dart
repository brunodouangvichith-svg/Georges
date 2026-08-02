import 'package:dio/dio.dart';

import 'api_exception.dart';
import 'auth/auth_interceptor.dart';
import 'env.dart';

/// Wrapper HTTP à 3 verbes — miroir de web/src/api/client.js
/// (`apiFetch`/`apiPost`/`apiDelete`). Timeouts par défaut volontairement
/// courts pour faire remonter vite une vraie panne (API/DB down) ; les 4
/// appels backend connus pour être lents (/prices/refresh, /agents/collect,
/// /decisions/{id}/explanation, /chat) passent un `receiveTimeout` plus long
/// explicitement au niveau de l'appel, pas via ce défaut global.
class ApiClient {
  final Dio _dio;

  ApiClient()
      : _dio = Dio(BaseOptions(
          baseUrl: apiBaseUrl,
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 30),
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
      return ApiException(path: path, statusCode: statusCode, message: e.response?.statusMessage ?? e.message ?? '');
    }
    return ApiException(path: path, message: e.message ?? 'Erreur réseau');
  }
}
