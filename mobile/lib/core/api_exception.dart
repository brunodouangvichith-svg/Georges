/// Erreur typée levée par [ApiClient] sur toute réponse non-2xx ou tout
/// échec réseau — miroir du `throw new Error(...)` de web/src/api/client.js.
class ApiException implements Exception {
  final int? statusCode;
  final String path;
  final String message;

  ApiException({required this.path, required this.message, this.statusCode});

  @override
  String toString() =>
      statusCode != null ? '$statusCode sur $path : $message' : 'Erreur sur $path : $message';
}
