import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'agents_repository.dart';
import 'baskets_repository.dart';
import 'decisions_repository.dart';
import 'patterns_repository.dart';
import 'portfolios_repository.dart';
import 'prices_repository.dart';
import 'securities_repository.dart';

/// Invalide toutes les données dérivées des prix — équivalent de
/// `queryClient.invalidateQueries()` (sans clé = tout) dans
/// web/src/api/queries.js:useRefreshPrices : un nouveau prix affecte
/// potentiellement les patterns, décisions, George Index et portefeuilles.
/// `ref.invalidate(provider)` sur un provider `.family` invalide toutes ses
/// instances, pas seulement un paramètre précis.
void invalidateAllData(WidgetRef ref) {
  ref.invalidate(securitiesProvider);
  ref.invalidate(decisionsProvider);
  ref.invalidate(securityPatternsProvider);
  ref.invalidate(securityPricesProvider);
  ref.invalidate(agentActivityProvider);
  ref.invalidate(basketsProvider);
  ref.invalidate(georgeIndexProvider);
  ref.invalidate(portfoliosProvider);
}
