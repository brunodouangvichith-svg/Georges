import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'core/auth/auth_providers.dart';
import 'core/auth/go_router_refresh_stream.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/login_screen.dart';
import 'features/paniers/paniers_screen.dart';
import 'features/portefeuille/portefeuille_screen.dart';
import 'features/profile/profile_screen.dart';
import 'features/univers/univers_screen.dart';

/// Navigation à 3 onglets (Univers / Paniers / Mon Portefeuille) — même
/// simplicité que web/src/App.jsx (pas de routeur là-bas, juste un
/// `useState`) ; go_router n'est là que pour le comportement natif du bouton
/// retour et pour permettre plus tard une route poussée "détail de décision".
///
/// Le routeur est maintenant un `Provider<GoRouter>` (plutôt qu'un `final`
/// top-level) pour pouvoir lire `isLoggedInProvider` dans `redirect:` — le
/// portail d'accès simple (Phase 9, voir CLAUDE.md section Auth) bascule
/// vers `/login` si non connecté, ou loin de `/login` si déjà connecté.
/// `refreshListenable` passe par `AuthRouterRefreshNotifier` (`ref.listen`
/// sur `authStateProvider`), pas un abonnement séparé au stream Supabase
/// brut — voir la docstring de cette classe pour la vraie course qu'un
/// abonnement séparé provoquait (connexion réussie mais jamais de
/// navigation, confirmé en direct sur appareil).
final _goRouterProvider = Provider<GoRouter>((ref) {
  final refreshNotifier = AuthRouterRefreshNotifier(ref);
  ref.onDispose(refreshNotifier.dispose);
  return GoRouter(
    initialLocation: '/univers',
    refreshListenable: refreshNotifier,
    redirect: (context, state) {
      // Le retour du deep link OAuth Google (`io.supabase.george://
      // login-callback/?code=...`, voir login_screen.dart:_signInWithGoogle)
      // arrive ici aussi : le SDK Supabase l'intercepte déjà en interne pour
      // échanger le code contre une session, mais go_router le reçoit
      // séparément comme une location à router — et comme aucune route ne
      // matche ce schéma personnalisé, il affiche sa page d'erreur générique
      // "Page Not Found" (`GoException: no routes for location: io.supabase
      // .george://...`), vu en direct sur appareil. Il faut l'intercepter ici
      // avant le matching de routes plutôt que de le laisser 404.
      if (state.uri.scheme == 'io.supabase.george') {
        return ref.read(isLoggedInProvider) ? '/univers' : '/login';
      }
      final loggedIn = ref.read(isLoggedInProvider);
      final onLoginPage = state.matchedLocation == '/login';
      if (!loggedIn) return onLoginPage ? null : '/login';
      if (onLoginPage) return '/univers';
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) => _AppShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(routes: [
            GoRoute(path: '/univers', builder: (context, state) => const UniversScreen()),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(path: '/paniers', builder: (context, state) => const PaniersScreen()),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(path: '/portefeuille', builder: (context, state) => const PortefeuilleScreen()),
          ]),
        ],
      ),
    ],
  );
});

class GeorgeApp extends ConsumerWidget {
  const GeorgeApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(_goRouterProvider);
    return MaterialApp.router(
      title: 'George',
      theme: buildAppTheme(),
      routerConfig: router,
    );
  }
}

class _AppShell extends StatefulWidget {
  const _AppShell({required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  State<_AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<_AppShell> {
  String? _appVersion;

  @override
  void initState() {
    super.initState();
    _loadAppVersion();
  }

  Future<void> _loadAppVersion() async {
    final info = await PackageInfo.fromPlatform();
    if (!mounted) return;
    setState(() => _appVersion = '${info.version}+${info.buildNumber}');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        centerTitle: true,
        leadingWidth: 96,
        leading: _appVersion == null
            ? null
            : Center(
                child: Padding(
                  padding: const EdgeInsets.only(left: 12),
                  child: Text(
                    'George v$_appVersion',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Theme.of(context).colorScheme.outline),
                    overflow: TextOverflow.visible,
                    softWrap: false,
                  ),
                ),
              ),
        // 22 (taille par défaut du titre d'AppBar, Material 3 titleLarge) * 1.25 * 1.10.
        title: const Text('George', style: TextStyle(fontSize: 30.25, fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: const Icon(Icons.person_outline),
            tooltip: 'Profil',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const ProfileScreen()),
            ),
          ),
        ],
      ),
      body: widget.navigationShell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: widget.navigationShell.currentIndex,
        onDestinationSelected: (index) => widget.navigationShell.goBranch(
          index,
          initialLocation: index == widget.navigationShell.currentIndex,
        ),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.dashboard_outlined), label: 'Univers'),
          NavigationDestination(icon: Icon(Icons.pie_chart_outline), label: 'Paniers'),
          NavigationDestination(icon: Icon(Icons.account_balance_wallet_outlined), label: 'Portefeuille'),
        ],
      ),
    );
  }
}
