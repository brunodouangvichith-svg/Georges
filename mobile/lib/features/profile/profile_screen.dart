import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../../data/invalidate_all.dart';

/// Écran "Profil" poussé (`Navigator.push`, pas une route go_router — même
/// précédent que `features/decision_detail/`, voir CLAUDE.md). Contenu
/// minimal pour ce portail simple (Phase 9) : juste l'email du compte
/// connecté et la déconnexion — pas d'éditeur de profil enrichi (bio,
/// préférences...), qui n'a pas d'équivalent dans George.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  Future<void> _signOut(BuildContext context, WidgetRef ref) async {
    await Supabase.instance.client.auth.signOut();
    invalidateAllData(ref);
    if (context.mounted) Navigator.of(context).pop();
    // Le `redirect:` du routeur (voir app.dart) bascule automatiquement vers
    // /login dès que authStateProvider voit l'événement signedOut — rien
    // d'autre à faire ici.
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
