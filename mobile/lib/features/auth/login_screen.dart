import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// Écran de connexion — affiché à la place de l'app principale tant que
/// `isLoggedInProvider` est faux (voir `app.dart`'s `redirect:`).
///
/// Structure reprise de deux projets frères du même auteur, à sa demande
/// explicite : le popup de création de compte (champs email/mot de
/// passe/confirmation, boutons ❌ Annuler / ✅ Enregistrer) suit exactement
/// `JADE/mobile/lib/features/auth/login_screen.dart:_showSignUpDialog` ;
/// le bouton "Continuer avec Google" (`signInWithOAuth`) suit le flux déjà
/// prouvé en production de `MeteoIA/static/index.html`. Aucune navigation
/// manuelle après un succès (connexion, inscription, ou retour OAuth) : le
/// `redirect:` du routeur bascule tout seul dès que `authStateProvider`
/// voit une session.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _isLoading = false;
  bool _obscurePassword = true;
  String? _errorMessage;
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
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      await Supabase.instance.client.auth.signInWithPassword(
        email: _emailController.text.trim(),
        password: _passwordController.text,
      );
      // Signale au gestionnaire de mots de passe natif (Google Password
      // Manager sur Android) que la saisie est terminée avec succès — c'est
      // ce qui déclenche sa propre popup "Enregistrer le mot de passe ?".
      // Le champ email/mot de passe est déjà annoté via `autofillHints`
      // (AutofillHints.email/.password) et regroupé dans un `AutofillGroup`
      // ci-dessous ; sans cet appel, l'OS ne sait jamais que la saisie a
      // abouti et ne propose jamais d'enregistrer.
      TextInput.finishAutofillContext();
    } on AuthException catch (e) {
      setState(() => _errorMessage = e.message);
    } catch (e) {
      setState(() => _errorMessage = 'Erreur inattendue : $e');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _signInWithGoogle() async {
    setState(() => _errorMessage = null);
    try {
      await Supabase.instance.client.auth.signInWithOAuth(
        OAuthProvider.google,
        redirectTo: 'io.supabase.george://login-callback/',
      );
    } on AuthException catch (e) {
      setState(() => _errorMessage = e.message);
    } catch (e) {
      setState(() => _errorMessage = 'Erreur inattendue : $e');
    }
  }

  /// Popup "mot de passe oublié" — demande juste l'email, puis
  /// `resetPasswordForEmail` (Supabase envoie lui-même l'email contenant le
  /// lien, rien à coder côté app pour l'envoi). Le lien renvoie vers ce même
  /// deep link `io.supabase.george://login-callback/` que l'OAuth Google ;
  /// voir `app.dart`/`auth_providers.dart:isPasswordRecoveryProvider` pour
  /// la suite du parcours (forcé vers `/reset-password`, pas `/univers`).
  ///
  /// Pas de récupération d'"email oublié" : aucun mécanisme sûr n'existe
  /// pour retrouver un compte sans connaître au moins son email (Supabase
  /// n'a ni identifiant secondaire ni recherche par nom ici) — le texte
  /// d'aide sous le lien renvoie donc vers un contact support plutôt que
  /// d'inventer une fonctionnalité qui n'existerait que par un faux
  /// sentiment de sécurité.
  Future<void> _showForgotPasswordDialog() async {
    final emailController = TextEditingController(
      text: _emailController.text.trim(),
    );
    var isSubmitting = false;
    var sent = false;
    String? dialogError;

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          title: const Text('Mot de passe oublié'),
          content: sent
              ? const Text(
                  'Si un compte existe pour cet email, un lien de réinitialisation vient d\'être envoyé. '
                  'Cliquez sur ce lien pour choisir un nouveau mot de passe.',
                )
              : Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Recevez un lien par email pour choisir un nouveau mot de passe.',
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: emailController,
                      autofocus: true,
                      keyboardType: TextInputType.emailAddress,
                      decoration: const InputDecoration(
                        labelText: 'Email',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    if (dialogError != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: Text(
                          dialogError!,
                          style: TextStyle(
                            color: Theme.of(dialogContext).colorScheme.error,
                          ),
                        ),
                      ),
                    const SizedBox(height: 12),
                    Text(
                      'Vous ne vous souvenez plus de l\'email utilisé pour votre compte ? Contactez le support.',
                      style: Theme.of(dialogContext).textTheme.bodySmall,
                    ),
                  ],
                ),
          actions: sent
              ? [
                  TextButton(
                    onPressed: () => Navigator.of(dialogContext).pop(),
                    child: const Text('OK'),
                  ),
                ]
              : [
                  TextButton(
                    onPressed: isSubmitting
                        ? null
                        : () => Navigator.of(dialogContext).pop(),
                    child: const Text('❌ Annuler'),
                  ),
                  FilledButton(
                    onPressed: isSubmitting
                        ? null
                        : () async {
                            final email = emailController.text.trim();
                            if (email.isEmpty) {
                              setDialogState(
                                () => dialogError = 'Entrez un email.',
                              );
                              return;
                            }
                            setDialogState(() {
                              isSubmitting = true;
                              dialogError = null;
                            });
                            try {
                              await Supabase.instance.client.auth
                                  .resetPasswordForEmail(
                                    email,
                                    redirectTo:
                                        'io.supabase.george://login-callback/',
                                  );
                              setDialogState(() {
                                isSubmitting = false;
                                sent = true;
                              });
                            } on AuthException catch (e) {
                              setDialogState(() {
                                isSubmitting = false;
                                dialogError = e.message;
                              });
                            } catch (e) {
                              setDialogState(() {
                                isSubmitting = false;
                                dialogError = 'Erreur inattendue : $e';
                              });
                            }
                          },
                    child: isSubmitting
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Envoyer le lien'),
                  ),
                ],
        ),
      ),
    );

    emailController.dispose();
  }

  Future<void> _showSignUpFailureDialog(
    BuildContext dialogContext,
    String message,
  ) {
    return showDialog<void>(
      context: dialogContext,
      builder: (context) => AlertDialog(
        title: const Text('Création de compte échouée'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  /// Affiché à la place d'une redirection automatique quand `signUp` ne
  /// renvoie pas de session active (`response.session == null`) -- c'est le
  /// cas dès que l'option "Confirm email" est activée côté projet Supabase
  /// (Authentication → Sign In / Providers → Email), qui déclenche l'envoi
  /// automatique de l'email de confirmation par Supabase lui-même : rien à
  /// coder côté app pour l'envoi, seulement pour ne plus supposer une
  /// connexion immédiate après "Enregistrer".
  Future<void> _showConfirmationEmailSentDialog(
    BuildContext dialogContext,
    String email,
  ) {
    return showDialog<void>(
      context: dialogContext,
      builder: (context) => AlertDialog(
        title: const Text('Vérifiez votre boîte mail'),
        content: Text(
          'Un email de confirmation a été envoyé à $email. Cliquez sur le lien qu\'il contient pour activer votre '
          'compte, puis connectez-vous ci-dessous.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  Future<void> _showSignUpDialog() async {
    final emailController = TextEditingController();
    final passwordController = TextEditingController();
    final confirmController = TextEditingController();
    var isSubmitting = false;
    var obscurePassword = true;
    var obscureConfirm = true;

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          title: const Text('Créer un compte'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: emailController,
                  keyboardType: TextInputType.emailAddress,
                  autofillHints: const [AutofillHints.newUsername],
                  decoration: const InputDecoration(
                    labelText: 'Email',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: passwordController,
                  obscureText: obscurePassword,
                  autofillHints: const [AutofillHints.newPassword],
                  decoration: InputDecoration(
                    labelText: 'Mot de passe',
                    border: const OutlineInputBorder(),
                    suffixIcon: IconButton(
                      icon: Icon(
                        obscurePassword
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                      ),
                      tooltip: obscurePassword
                          ? 'Afficher le mot de passe'
                          : 'Masquer le mot de passe',
                      onPressed: () => setDialogState(
                        () => obscurePassword = !obscurePassword,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: confirmController,
                  obscureText: obscureConfirm,
                  autofillHints: const [AutofillHints.newPassword],
                  decoration: InputDecoration(
                    labelText: 'Confirmer le mot de passe',
                    border: const OutlineInputBorder(),
                    suffixIcon: IconButton(
                      icon: Icon(
                        obscureConfirm
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                      ),
                      tooltip: obscureConfirm
                          ? 'Afficher le mot de passe'
                          : 'Masquer le mot de passe',
                      onPressed: () => setDialogState(
                        () => obscureConfirm = !obscureConfirm,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: isSubmitting
                  ? null
                  : () => Navigator.of(dialogContext).pop(),
              child: const Text('❌ Annuler'),
            ),
            FilledButton(
              onPressed: isSubmitting
                  ? null
                  : () async {
                      final password = passwordController.text;
                      if (password != confirmController.text) {
                        await _showSignUpFailureDialog(
                          dialogContext,
                          'Les mots de passe ne correspondent pas.',
                        );
                        return;
                      }

                      setDialogState(() => isSubmitting = true);
                      final email = emailController.text.trim();
                      try {
                        final response = await Supabase.instance.client.auth
                            .signUp(email: email, password: password);
                        if (!dialogContext.mounted) return;
                        Navigator.of(dialogContext).pop();
                        if (response.session == null) {
                          // "Confirm email" activé côté Supabase : pas de
                          // session tout de suite, l'email vient d'être
                          // envoyé par Supabase -- on l'explique plutôt que
                          // de laisser croire que la connexion a échoué.
                          if (!mounted) return;
                          await _showConfirmationEmailSentDialog(
                            context,
                            email,
                          );
                        }
                        // Sinon (session déjà active), le `redirect:` du
                        // routeur (voir app.dart) bascule automatiquement
                        // dès que authStateProvider la voit — rien d'autre à
                        // faire ici.
                      } on AuthException catch (e) {
                        setDialogState(() => isSubmitting = false);
                        if (!dialogContext.mounted) return;
                        await _showSignUpFailureDialog(
                          dialogContext,
                          e.message,
                        );
                      } catch (e) {
                        setDialogState(() => isSubmitting = false);
                        if (!dialogContext.mounted) return;
                        await _showSignUpFailureDialog(
                          dialogContext,
                          'Erreur inattendue : $e',
                        );
                      }
                    },
              child: isSubmitting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('✅ Enregistrer'),
            ),
          ],
        ),
      ),
    );

    emailController.dispose();
    passwordController.dispose();
    confirmController.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;

    return Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 32),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Align(
                      alignment: Alignment.center,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 24,
                          vertical: 10,
                        ),
                        decoration: BoxDecoration(
                          color: Colors.lightBlue.shade100,
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: Text(
                          'GeorGe',
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.displaySmall?.copyWith(
                            fontWeight: FontWeight.bold,
                            // 36 (taille par défaut Material 3 de displaySmall) * 1.20 * 1.20.
                            fontSize: 51.84,
                            color: Colors.black87,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                    if (_errorMessage != null)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 16),
                        child: Text(
                          _errorMessage!,
                          style: TextStyle(color: colors.error),
                          textAlign: TextAlign.center,
                        ),
                      ),
                    AutofillGroup(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          TextField(
                            controller: _emailController,
                            keyboardType: TextInputType.emailAddress,
                            autofillHints: const [AutofillHints.email],
                            decoration: const InputDecoration(
                              labelText: 'Email',
                              border: OutlineInputBorder(),
                            ),
                          ),
                          const SizedBox(height: 12),
                          TextField(
                            controller: _passwordController,
                            obscureText: _obscurePassword,
                            autofillHints: const [AutofillHints.password],
                            decoration: InputDecoration(
                              labelText: 'Mot de passe',
                              border: const OutlineInputBorder(),
                              suffixIcon: IconButton(
                                icon: Icon(
                                  _obscurePassword
                                      ? Icons.visibility_outlined
                                      : Icons.visibility_off_outlined,
                                ),
                                tooltip: _obscurePassword
                                    ? 'Afficher le mot de passe'
                                    : 'Masquer le mot de passe',
                                onPressed: () => setState(
                                  () => _obscurePassword = !_obscurePassword,
                                ),
                              ),
                            ),
                            onSubmitted: (_) => _login(),
                          ),
                        ],
                      ),
                    ),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton(
                        onPressed: _isLoading
                            ? null
                            : _showForgotPasswordDialog,
                        child: const Text('Mot de passe oublié ?'),
                      ),
                    ),
                    const SizedBox(height: 8),
                    FilledButton.icon(
                      onPressed: _isLoading ? null : _login,
                      icon: const Icon(Icons.login),
                      label: const Text('Se connecter'),
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: _isLoading ? null : _showSignUpDialog,
                      icon: const Icon(Icons.person_add_alt),
                      label: const Text('Créer un compte'),
                    ),
                    const SizedBox(height: 12),
                    const Divider(),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: _isLoading ? null : _signInWithGoogle,
                      icon: const Icon(Icons.login, color: Colors.black87),
                      label: const Text(
                        'Continuer avec Google',
                        style: TextStyle(color: Colors.black87),
                      ),
                      style: OutlinedButton.styleFrom(
                        backgroundColor: Colors.lightBlue.shade100,
                      ),
                    ),
                    if (_isLoading)
                      const Padding(
                        padding: EdgeInsets.only(top: 20),
                        child: Center(
                          child: SizedBox(
                            width: 24,
                            height: 24,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
            if (_appVersion != null)
              Positioned(
                left: 8,
                bottom: 8,
                child: Text(
                  'George v$_appVersion',
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(color: colors.outline),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
