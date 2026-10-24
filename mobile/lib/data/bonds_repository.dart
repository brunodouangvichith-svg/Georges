import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/bond.dart';

/// Miroir des hooks Obligataire de web/src/api/queries.js (useBondDashboard,
/// useBondHistory, useBondThresholds, useBondAlertEvents, useBondBulletin,
/// useUpdateBondThreshold, useRefreshBonds) — routes de api/routers/bonds.py.
class BondsRepository {
  BondsRepository(this._ref);

  final Ref _ref;

  Future<BondDashboard> dashboard() async {
    final json = await _ref.read(apiClientProvider).get('/bonds');
    return BondDashboard.fromJson(json as Map<String, dynamic>);
  }

  /// OAT/Bund sont mensuels, les Treasuries quotidiens : `limit` compte des
  /// observations, pas des jours — on prend le maximum autorisé (2000) et on
  /// filtre par date côté écran, comme web/src/views/Obligataire.jsx.
  Future<List<BondHistoryPoint>> history(String instrument, {int limit = 2000}) async {
    final json = await _ref.read(apiClientProvider).get('/bonds/$instrument/history', params: {'limit': limit});
    return (json as List).map((e) => BondHistoryPoint.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<BondAlertThreshold>> thresholds() async {
    final json = await _ref.read(apiClientProvider).get('/bonds/alerts/thresholds');
    return (json as List).map((e) => BondAlertThreshold.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<BondAlertEvent>> alertEvents({String? status, int limit = 20}) async {
    final json = await _ref.read(apiClientProvider).get('/bonds/alerts/events', params: {'status': status, 'limit': limit});
    return (json as List).map((e) => BondAlertEvent.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<BondBulletin> bulletin() async {
    final json = await _ref.read(apiClientProvider).get('/bonds/bulletin');
    return BondBulletin.fromJson(json as Map<String, dynamic>);
  }

  /// N'envoie que les champs modifiés (null = inchangé), même sémantique que
  /// PATCH /bonds/alerts/thresholds/{id} côté API.
  Future<BondAlertThreshold> updateThreshold(int id, {double? thresholdPct, bool? enabled}) async {
    final body = <String, dynamic>{};
    if (thresholdPct != null) body['threshold_pct'] = thresholdPct;
    if (enabled != null) body['enabled'] = enabled;
    final json = await _ref.read(apiClientProvider).patch('/bonds/alerts/thresholds/$id', body: body);
    return BondAlertThreshold.fromJson(json as Map<String, dynamic>);
  }

  Future<BondRefreshResult> refresh() async {
    final json = await _ref.read(apiClientProvider).post('/bonds/refresh', receiveTimeout: const Duration(seconds: 120));
    return BondRefreshResult.fromJson(json as Map<String, dynamic>);
  }
}

final bondsRepositoryProvider = Provider<BondsRepository>((ref) => BondsRepository(ref));

final bondDashboardProvider = FutureProvider.autoDispose<BondDashboard>((ref) {
  return ref.read(bondsRepositoryProvider).dashboard();
});

final bondHistoryProvider = FutureProvider.autoDispose.family<List<BondHistoryPoint>, String>((ref, instrument) {
  return ref.read(bondsRepositoryProvider).history(instrument);
});

final bondThresholdsProvider = FutureProvider.autoDispose<List<BondAlertThreshold>>((ref) {
  return ref.read(bondsRepositoryProvider).thresholds();
});

/// Alertes encore actives (statut `triggered`).
final bondActiveAlertsProvider = FutureProvider.autoDispose<List<BondAlertEvent>>((ref) {
  return ref.read(bondsRepositoryProvider).alertEvents(status: 'triggered');
});

final bondBulletinProvider = FutureProvider.autoDispose<BondBulletin>((ref) {
  return ref.read(bondsRepositoryProvider).bulletin();
});

/// Invalide tout l'onglet Obligataire après une mise à jour des taux.
void invalidateBondData(WidgetRef ref) {
  ref.invalidate(bondDashboardProvider);
  ref.invalidate(bondHistoryProvider);
  ref.invalidate(bondThresholdsProvider);
  ref.invalidate(bondActiveAlertsProvider);
  ref.invalidate(bondBulletinProvider);
}
