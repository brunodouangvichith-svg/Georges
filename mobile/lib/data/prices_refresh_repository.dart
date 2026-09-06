import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/providers.dart';
import '../models/price_refresh_status.dart';

/// Miroir de web/src/api/queries.js:useRefreshPrices — déclenchement manuel
/// de ingestion.price_history pour tout l'univers (10 ans d'historique par
/// titre, ~1-2 min réseau/yfinance).
///
/// Le backend (`api/routers/prices.py`) est asynchrone : `POST /refresh`
/// répond immédiatement avec `status: "running"` et exécute le
/// téléchargement en tâche de fond ; `refresh()` fait ensuite le polling sur
/// `GET /refresh` jusqu'à `status in {"done", "failed"}`. Remplace l'ancien
/// design synchrone dont le timeout mobile fixe (2 min) finissait par être
/// dépassé une fois le backend passé à 10 ans d'historique.
///
/// Deux garde-fous ajoutés après revue (`_state` du backend est en mémoire
/// seule, sans persistance — voir `api/routers/prices.py` — et ne survit
/// donc pas à un redémarrage du service Render pendant un job) :
/// - `_maxWait` borne la durée totale du polling : sans ça, un redémarrage
///   serveur en plein job réinitialise silencieusement `_state` à `"idle"`,
///   que cette boucle prendrait pour "toujours en cours" et attendrait
///   indéfiniment — pire que l'ancien timeout fixe qui, lui, finissait
///   toujours par afficher une erreur.
/// - `_maxConsecutiveErrors` tolère quelques échecs réseau transitoires sur
///   un seul appel `GET` sans faire échouer tout le rafraîchissement : avec
///   ~1-2 min de polling toutes les 3s, il y a beaucoup plus de fenêtres de
///   risque réseau qu'avec l'ancien appel bloquant unique.
class PricesRefreshRepository {
  PricesRefreshRepository(this._ref);

  static const _pollInterval = Duration(seconds: 3);
  static const _maxWait = Duration(minutes: 10);
  static const _maxConsecutiveErrors = 3;

  final Ref _ref;

  Future<PriceRefreshStatus> refresh() async {
    final client = _ref.read(apiClientProvider);
    await client.post('/prices/refresh');

    final deadline = DateTime.now().add(_maxWait);
    var consecutiveErrors = 0;
    while (true) {
      if (DateTime.now().isAfter(deadline)) {
        throw Exception(
          'Le rafraîchissement des prix prend plus de ${_maxWait.inMinutes} minutes — réessayez plus tard.',
        );
      }

      PriceRefreshStatus status;
      try {
        final json = await client.get('/prices/refresh');
        status = PriceRefreshStatus.fromJson(json as Map<String, dynamic>);
        consecutiveErrors = 0;
      } catch (_) {
        consecutiveErrors++;
        if (consecutiveErrors > _maxConsecutiveErrors) rethrow;
        await Future.delayed(_pollInterval);
        continue;
      }

      if (status.isDone || status.isFailed) return status;
      await Future.delayed(_pollInterval);
    }
  }
}

final pricesRefreshRepositoryProvider = Provider<PricesRefreshRepository>((ref) => PricesRefreshRepository(ref));
