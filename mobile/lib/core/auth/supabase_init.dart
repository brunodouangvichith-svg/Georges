import 'package:supabase_flutter/supabase_flutter.dart';

import '../env.dart';

/// Initialise le client Supabase partagé (`Supabase.instance.client`),
/// appelé une fois dans `main.dart` avant `runApp(...)`. `authFlowType:
/// AuthFlowType.pkce` (via `authOptions`, pas un paramètre direct de
/// `initialize` — vérifié contre le package installé) est requis pour que
/// `signInWithOAuth` fonctionne via un deep link natif plutôt que le
/// rechargement de page utilisé côté web.
Future<void> initSupabase() async {
  await Supabase.initialize(
    url: supabaseUrl,
    publishableKey: supabaseAnonKey,
    authOptions: const FlutterAuthClientOptions(authFlowType: AuthFlowType.pkce),
  );
}
