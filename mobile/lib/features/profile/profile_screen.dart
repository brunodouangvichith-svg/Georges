import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../../data/invalidate_all.dart';

/// Écran "Profil" poussé (`Navigator.push`, pas une route go_router — même
/// précédent que `features/decision_detail/`, voir CLAUDE.md). Contenu
/// minimal pour ce portail simple (Phase 9) : l'email du compte connecté,
/// la version installée (même patron que `JADE/mobile/lib/features/memory/
/// profile_screen.dart:_loadAppVersion`, utile pour savoir précisément quel
/// build est testé), et la déconnexion — pas d'éditeur de profil enrichi
/// (bio, préférences...), qui n'a pas d'équivalent dans George.
class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
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

  Future<void> _signOut(BuildContext context, WidgetRef ref) async {
    await Supabase.instance.client.auth.signOut();
    invalidateAllData(ref);
    if (!context.mounted) return;
    // Un simple Navigator.pop() ici ne fait que révéler l'écran principal
    // (_AppShell) déjà présent en dessous de ce Profil poussé — le
    // `redirect:` du routeur (app.dart) ne rattrape le passage vers /login
    // qu'après coup, une fois `authStateProvider` mis à jour de façon
    // asynchrone, ce qui laissait l'app affichée sur l'écran principal au
    // lieu de l'écran de connexion (bug observé en direct sur appareil).
    // `context.go('/login')` navigue directement, sans dépendre de ce
    // décalage de timing : go_router remplace toute la pile (y compris ce
    // Profil poussé de façon impérative) par le seul écran de connexion.
    context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final email = Supabase.instance.client.auth.currentUser?.email;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Profil'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Se déconnecter',
            onPressed: () => _signOut(context, ref),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ListTile(
            leading: const Icon(Icons.person_outline),
            title: const Text('Connecté en tant que'),
            subtitle: Text(email ?? '—'),
          ),
          if (_appVersion != null)
            ListTile(
              leading: const Icon(Icons.info_outline),
              title: const Text('Version'),
              subtitle: Text('George v$_appVersion'),
            ),
          const SizedBox(height: 24),
          OutlinedButton.icon(
            onPressed: () => _signOut(context, ref),
            icon: const Icon(Icons.logout),
            label: const Text('Se déconnecter'),
          ),
        ],
      ),
    );
  }
}
