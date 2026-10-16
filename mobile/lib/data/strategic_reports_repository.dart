import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/strategic_report.dart';

/// Miroir des hooks « Rapport » de web/src/api/queries.js — routes de
/// api/routers/strategic_reports.py. La génération est asynchrone côté
/// serveur (comme /prices/refresh) : `generate()` lance le job puis
/// interroge son statut jusqu'à `done`/`failed`, avec les mêmes garde-fous
/// que PricesRefreshRepository (durée maximale, erreurs réseau tolérées).
class StrategicReportsRepository {
  StrategicReportsRepository(this._ref);

  static const _pollInterval = Duration(seconds: 3);
  static const _maxWait = Duration(minutes: 8);
  static const _maxConsecutiveErrors = 3;

  final Ref _ref;

  Future<List<StrategicReportSummary>> list({int limit = 30}) async {
    final json = await _ref.read(apiClientProvider).get('/strategic-reports', params: {'limit': limit});
    return (json as List).map((e) => StrategicReportSummary.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// `id` null = dernier rapport ; `null` tant qu'aucun n'a été généré.
  Future<StrategicReport?> fetch(int? id) async {
    final json = await _ref.read(apiClientProvider).get(id == null ? '/strategic-reports/latest' : '/strategic-reports/$id');
    if (json is! Map) return null;
    return StrategicReport.fromJson(json.cast<String, dynamic>());
  }

  Future<StrategicReportJobStatus> generate() async {
    final client = _ref.read(apiClientProvider);
    await client.post('/strategic-reports/generate');
    final deadline = DateTime.now().add(_maxWait);
    var consecutiveErrors = 0;
    while (true) {
      if (DateTime.now().isAfter(deadline)) {
        throw Exception('La génération du rapport prend plus de ${_maxWait.inMinutes} minutes — réessaie plus tard.');
      }
      StrategicReportJobStatus status;
      try {
        final json = await client.get('/strategic-reports/generate');
        status = StrategicReportJobStatus.fromJson(json as Map<String, dynamic>);
        consecutiveErrors = 0;
      } catch (_) {
        consecutiveErrors++;
        if (consecutiveErrors > _maxConsecutiveErrors) rethrow;
        await Future.delayed(_pollInterval);
        continue;
      }
      if (status.isFailed) throw Exception(status.error ?? 'Échec de la génération du rapport.');
      if (status.isDone) return status;
      await Future.delayed(_pollInterval);
    }
  }
}

final strategicReportsRepositoryProvider =
    Provider<StrategicReportsRepository>((ref) => StrategicReportsRepository(ref));

final strategicReportsListProvider = FutureProvider.autoDispose<List<StrategicReportSummary>>((ref) {
  return ref.read(strategicReportsRepositoryProvider).list();
});

/// `null` = dernier rapport.
final strategicReportProvider = FutureProvider.autoDispose.family<StrategicReport?, int?>((ref, id) {
  return ref.read(strategicReportsRepositoryProvider).fetch(id);
});
