import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/auth/auth_providers.dart';
import 'core/auth/go_router_refresh_stream.dart';
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
/// `refreshListenable` lit `authChangeStreamProvider` (pas
/// `Supabase.instance` directement) pour redéclencher `redirect:` à chaque
/// changement de session — et pour rester overridable dans les tests
/// widget qui pompent `GeorgeApp` sans initialiser un vrai client Supabase.
final _goRouterProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/univers',
    refreshListenable: GoRouterRefreshStream(ref.watch(authChangeStreamProvider)),
    redirect: (context, state) {
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
      theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
      routerConfig: router,
    );
  }
}

class _AppShell extends StatelessWidget {
  const _AppShell({required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('George'),
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
      body: navigationShell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
        onDestinationSelected: (index) => navigationShell.goBranch(
          index,
          initialLocation: index == navigationShell.currentIndex,
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
