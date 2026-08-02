import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
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
    if (context.mounted) Navigator.of(context).pop();
    // Le `redirect:` du routeur (voir app.dart) bascule automatiquement vers
    // /login dès que authStateProvider voit l'événement signedOut — rien
    // d'autre à faire ici.
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
