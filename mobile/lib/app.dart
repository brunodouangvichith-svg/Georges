import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'features/paniers/paniers_screen.dart';
import 'features/portefeuille/portefeuille_screen.dart';
import 'features/univers/univers_screen.dart';

/// Navigation à 3 onglets (Univers / Paniers / Mon Portefeuille) — même
/// simplicité que web/src/App.jsx (pas de routeur là-bas, juste un
/// `useState`) ; go_router n'est là que pour le comportement natif du bouton
/// retour et pour permettre plus tard une route poussée "détail de décision".
final _router = GoRouter(
  initialLocation: '/univers',
  routes: [
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

class GeorgeApp extends StatelessWidget {
  const GeorgeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'George',
      theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
      routerConfig: _router,
    );
  }
}

class _AppShell extends StatelessWidget {
  const _AppShell({required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
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
