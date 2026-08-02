import 'package:supabase_flutter/supabase_flutter.dart';

import '../env.dart';

/// Initialise le client Supabase partagé (`Supabase.instance.client`),
/// appelé une fois dans `main.dart` avant `runApp(...)`. `authFlowType:
/// AuthFlowType.pkce` (via `authOptions`, pas un paramètre direct de
/// `initialize` — vérifié contre le package installé) est requis pour que
/// `signInWithOAuth` fonctionne via un deep link natif plutôt que le
/// rechargement de page utilisé côté web.
///
/// `debug: true` explicite (plutôt que le défaut `kDebugMode`, qui vaut
/// `false` en build release) : les erreurs silencieuses de
/// `SupabaseAuth._handleDeeplink` (ex. échec de `getSessionFromUrl` après
/// un retour OAuth — jamais remontées à l'UI, seulement loguées) ne
/// seraient sinon visibles nulle part, y compris via `adb logcat`, sur
/// l'APK release utilisé pour les tests réels sur téléphone.
Future<void> initSupabase() async {
  await Supabase.initialize(
    url: supabaseUrl,
    publishableKey: supabaseAnonKey,
    authOptions: const FlutterAuthClientOptions(authFlowType: AuthFlowType.pkce),
    debug: true,
  );
}
