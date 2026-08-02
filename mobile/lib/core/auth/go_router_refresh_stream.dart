import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_providers.dart';

/// Notifie go_router (`refreshListenable`) exactement quand
/// `authStateProvider` (donc `isLoggedInProvider`) vient de se mettre à
/// jour — via `ref.listen`, jamais un abonnement séparé au stream brut de
/// Supabase.
///
/// Un vrai bug a été trouvé avec cette dernière approche (version
/// initiale de ce fichier, un `ChangeNotifier` abonné directement à
/// `authChangeStreamProvider`) : deux abonnements indépendants au même
/// stream (un pour `authStateProvider` en interne, un pour rafraîchir le
/// routeur) se déclenchent dans l'ordre où ils ont été enregistrés, pas
/// dans un ordre garanti par leur relation logique. Celui du routeur étant
/// enregistré en premier (à la construction de `_goRouterProvider`), il
/// tourne AVANT que `authStateProvider` n'ait fini de traiter le même
/// événement — `redirect:` lisait alors encore l'ancien état (non
/// connecté) juste après une connexion pourtant réussie, empêchant toute
/// navigation. Confirmé en direct via des SnackBars de diagnostic : le
/// login Supabase aboutissait bien (`signInWithPassword` réussi), sans
/// jamais quitter l'écran de connexion. `ref.listen` élimine cette course
/// par construction : Riverpod ne l'appelle qu'après avoir mis à jour
/// l'état du provider écouté, jamais avant.
class AuthRouterRefreshNotifier extends ChangeNotifier {
  AuthRouterRefreshNotifier(Ref ref) {
    ref.listen(authStateProvider, (previous, next) => notifyListeners());
  }
}
