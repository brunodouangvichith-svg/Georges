import 'dart:async';

import 'package:flutter/foundation.dart';

/// Adapte n'importe quel `Stream` en `Listenable` pour le `refreshListenable`
/// de `GoRouter` — recette bien connue de la doc go_router, mais qui n'est
/// **pas** exportée par le package lui-même (vérifié : absente de
/// `go_router` 17.3.0, seulement présente comme exemple à copier dans son
/// propre code), donc écrite ici plutôt que supposée importable.
class GoRouterRefreshStream extends ChangeNotifier {
  GoRouterRefreshStream(Stream<dynamic> stream) {
    notifyListeners();
    _subscription = stream.asBroadcastStream().listen((_) => notifyListeners());
  }

  late final StreamSubscription<dynamic> _subscription;

  @override
  void dispose() {
    _subscription.cancel();
    super.dispose();
  }
}
