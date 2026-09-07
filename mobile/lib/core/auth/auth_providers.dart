import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// Stream brut de Supabase, isolé dans son propre provider plutôt
/// qu'appelé directement là où il est utilisé (`app.dart`) — sinon
/// `Supabase.instance` (jamais initialisé dans les tests widget, qui ne
/// passent pas par `main()`) serait touché même quand `isLoggedInProvider`
/// est overridé, faisant planter tout test qui pompe `GeorgeApp` sans
/// mocker Supabase. En passant par ce provider, un test peut l'overrider
/// (`authChangeStreamProvider.overrideWithValue(const Stream.empty())`)
/// sans jamais toucher le singleton réel.
final authChangeStreamProvider = Provider<Stream<AuthState>>((ref) {
  return Supabase.instance.client.auth.onAuthStateChange;
});

/// État d'authentification — pont Riverpod sur le stream natif de Supabase
/// (`onAuthStateChange`, couvre `initialSession`/`signedIn`/`signedOut`/
/// `tokenRefreshed`). Volontairement `StreamProvider` plutôt qu'un
/// `NotifierProvider` fait main : Supabase expose déjà la source de vérité
/// sous forme de stream, un `NotifierProvider` ne ferait que réimplémenter
/// un écouteur avec plus de code pour le même résultat.
///
/// Volontairement **pas** `.autoDispose`, contrairement à tous les
/// providers de données de `data/` (`securitiesProvider` etc.) : l'état
/// d'auth doit survivre à la navigation puisqu'il pilote le `redirect:` du
/// routeur pour toute l'app (voir `app.dart`).
final authStateProvider = StreamProvider<AuthState>((ref) {
  return ref.watch(authChangeStreamProvider);
});

/// Dérivé pratique : `true` dès qu'une session existe.
///
/// **Vrai bug corrigé ici** : au démarrage à froid avec une session déjà
/// persistée (ex. connexion Google précédente), `authStateProvider` reste en
/// `AsyncValue.loading` pendant un court instant après que `Supabase.
/// initialize()` a pourtant déjà restauré la session en mémoire de façon
/// synchrone — `onAuthStateChange` n'émet son premier événement
/// (`initialSession`) qu'un peu après. Se rabattre sur `false` pendant cette
/// fenêtre (l'ancien comportement) faisait passer l'app par `/login` avant
/// de rebondir tout seul vers `/univers` une fois le stream émis — un aller-
/// retour visible, et potentiellement l'app restant bloquée sur `/login` si
/// l'utilisateur interagit avec l'écran de connexion pendant cette fenêtre.
/// `Supabase.instance.client.auth.currentSession` reflète déjà l'état
/// restauré à cet instant précis, donc on l'utilise comme repli tant que le
/// stream n'a pas encore émis, plutôt que de supposer "non connecté".
final isLoggedInProvider = Provider<bool>((ref) {
  final authState = ref.watch(authStateProvider);
  if (authState.hasValue) return authState.value?.session != null;
  return Supabase.instance.client.auth.currentSession != null;
});

/// `true` dès que le dernier événement d'auth reçu est `AuthChangeEvent.
/// passwordRecovery` — l'utilisateur vient de cliquer le lien "mot de passe
/// oublié" reçu par email (`login_screen.dart:_showForgotPasswordDialog`,
/// `resetPasswordForEmail`). Ce lien ouvre une session Supabase techniquement
/// "connectée" (même schéma de deep link `io.supabase.george://
/// login-callback/` que l'OAuth Google, voir `app.dart`), mais l'utilisateur
/// n'a pas encore choisi de nouveau mot de passe — sans ce provider,
/// `isLoggedInProvider` serait déjà vrai et le routeur enverrait directement
/// vers `/univers`, laissant n'importe qui avec un vieux lien de
/// réinitialisation entrer dans le compte sans jamais avoir à changer le mot
/// de passe. Redevient faux dès que `updateUser(password: ...)` réussit
/// (`reset_password_screen.dart`) : Supabase émet alors un nouvel événement
/// `userUpdated`, pas `passwordRecovery`, donc ce provider retombe à `false`
/// sans code supplémentaire ici.
final isPasswordRecoveryProvider = Provider<bool>((ref) {
  final authState = ref.watch(authStateProvider);
  return authState.value?.event == AuthChangeEvent.passwordRecovery;
});
