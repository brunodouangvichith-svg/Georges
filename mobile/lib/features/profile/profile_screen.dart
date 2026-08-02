import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../../core/theme/app_theme.dart';
import '../../data/invalidate_all.dart';

const _prefsNameKey = 'profile_name';
const _prefsBioKey = 'profile_bio';
const _prefsContactsKey = 'profile_contacts';
const _prefsAvatarPathKey = 'profile_avatar_path';

class _Contact {
  _Contact(this.name, this.email);

  final String name;
  final String email;

  Map<String, String> toJson() => {'name': name, 'email': email};

  static _Contact fromJson(Map<String, dynamic> json) => _Contact(json['name'] as String, json['email'] as String);
}

/// Écran "Profil" poussé (`Navigator.push`, pas une route go_router — même
/// précédent que `features/decision_detail/`, voir CLAUDE.md). Au-delà du
/// minimum initial (email du compte, déconnexion), gagne ici des champs
/// Nom/Bio/Contacts demandés directement par l'utilisateur — stockés
/// uniquement en local (`shared_preferences`, sur l'appareil), puisqu'aucune
/// table backend n'existe pour ça (portail d'accès simple, Phase 9 : pas de
/// données par utilisateur côté serveur, voir CLAUDE.md section Auth). Ce
/// n'est donc pas synchronisé entre appareils, contrairement au reste des
/// données de l'app qui viennent de l'API.
class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  String? _appVersion;
  SharedPreferences? _prefs;
  String? _avatarPath;

  final _nameController = TextEditingController();
  final _bioController = TextEditingController();
  final _contactNameController = TextEditingController();
  final _contactEmailController = TextEditingController();
  List<_Contact> _contacts = [];

  @override
  void initState() {
    super.initState();
    _loadAppVersion();
    _loadProfile();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _bioController.dispose();
    _contactNameController.dispose();
    _contactEmailController.dispose();
    super.dispose();
  }

  Future<void> _loadAppVersion() async {
    final info = await PackageInfo.fromPlatform();
    if (!mounted) return;
    setState(() => _appVersion = '${info.version}+${info.buildNumber}');
  }

  Future<void> _loadProfile() async {
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    _prefs = prefs;
    _nameController.text = prefs.getString(_prefsNameKey) ?? '';
    _bioController.text = prefs.getString(_prefsBioKey) ?? '';
    final rawContacts = prefs.getString(_prefsContactsKey);
    final avatarPath = prefs.getString(_prefsAvatarPathKey);
    setState(() {
      _contacts = rawContacts == null
          ? []
          : (jsonDecode(rawContacts) as List)
              .map((e) => _Contact.fromJson(e as Map<String, dynamic>))
              .toList();
      // Le fichier peut avoir disparu (cache vidé par l'OS, désinstallation
      // partielle...) — on ne fait confiance au chemin que s'il existe
      // vraiment, sinon on retombe sur l'icône par défaut plutôt que sur une
      // image cassée.
      _avatarPath = avatarPath != null && File(avatarPath).existsSync() ? avatarPath : null;
    });
  }

  Future<void> _pickAvatar(ImageSource source) async {
    final picked = await ImagePicker().pickImage(source: source, maxWidth: 512, imageQuality: 85);
    if (picked == null || !mounted) return;
    // Copié vers un nom de fichier stable dans le répertoire documents de
    // l'app (pas le chemin renvoyé par image_picker, qui peut pointer vers
    // un cache temporaire nettoyé par l'OS) pour survivre aux redémarrages.
    final docsDir = await getApplicationDocumentsDirectory();
    final savedPath = '${docsDir.path}/profile_avatar.jpg';
    await File(picked.path).copy(savedPath);
    await _prefs?.setString(_prefsAvatarPathKey, savedPath);
    if (!mounted) return;
    setState(() => _avatarPath = savedPath);
  }

  Future<void> _showAvatarPicker(BuildContext context) async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_camera_outlined),
              title: const Text('Prendre une photo'),
              onTap: () => Navigator.of(sheetContext).pop(ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Choisir dans la galerie'),
              onTap: () => Navigator.of(sheetContext).pop(ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
    if (source != null) await _pickAvatar(source);
  }

  void _saveName(String value) => _prefs?.setString(_prefsNameKey, value);

  void _saveBio(String value) => _prefs?.setString(_prefsBioKey, value);

  void _saveContacts() {
    _prefs?.setString(_prefsContactsKey, jsonEncode(_contacts.map((c) => c.toJson()).toList()));
  }

  void _addContact() {
    final name = _contactNameController.text.trim();
    final email = _contactEmailController.text.trim();
    if (name.isEmpty || email.isEmpty) return;
    setState(() => _contacts = [..._contacts, _Contact(name, email)]);
    _saveContacts();
    _contactNameController.clear();
    _contactEmailController.clear();
  }

  void _removeContact(int index) {
    setState(() => _contacts = [..._contacts]..removeAt(index));
    _saveContacts();
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
        centerTitle: true,
        title: Text(
          'Profil',
          // 20 (taille par défaut de ce thème pour titleTextStyle d'AppBar) * 1.10.
          style: Theme.of(context).appBarTheme.titleTextStyle?.copyWith(fontSize: 22),
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Center(
                  child: Stack(
                    children: [
                      CircleAvatar(
                        radius: 40,
                        backgroundColor: Colors.lightBlue.shade100,
                        backgroundImage: _avatarPath != null ? FileImage(File(_avatarPath!)) : null,
                        child: _avatarPath == null ? const Icon(Icons.person, size: 44, color: Colors.black87) : null,
                      ),
                      Positioned(
                        right: 0,
                        bottom: 0,
                        child: Material(
                          color: AppColors.accent,
                          shape: const CircleBorder(),
                          child: InkWell(
                            customBorder: const CircleBorder(),
                            onTap: () => _showAvatarPicker(context),
                            child: const Padding(
                              padding: EdgeInsets.all(6),
                              child: Icon(Icons.photo_camera, size: 16, color: Colors.white),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                ListTile(
                  leading: const Icon(Icons.email_outlined),
                  title: const Text('Connecté en tant que'),
                  subtitle: Text(email ?? '—'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _nameController,
                  decoration: const InputDecoration(labelText: 'Nom', border: OutlineInputBorder()),
                  onChanged: _saveName,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _bioController,
                  decoration: const InputDecoration(labelText: 'Bio', border: OutlineInputBorder()),
                  maxLines: 3,
                  onChanged: _saveBio,
                ),
                const SizedBox(height: 20),
                Text('Contacts', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                for (var i = 0; i < _contacts.length; i++)
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.person_outline),
                      title: Text(_contacts[i].name),
                      subtitle: Text(_contacts[i].email),
                      trailing: IconButton(
                        icon: Icon(Icons.delete_outline, color: Colors.red.shade400),
                        tooltip: 'Retirer ce contact',
                        onPressed: () => _removeContact(i),
                      ),
                    ),
                  ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _contactNameController,
                        decoration: const InputDecoration(labelText: 'Nom', border: OutlineInputBorder(), isDense: true),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextField(
                        controller: _contactEmailController,
                        keyboardType: TextInputType.emailAddress,
                        decoration: const InputDecoration(labelText: 'Email', border: OutlineInputBorder(), isDense: true),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.add_circle, color: AppColors.accent),
                      tooltip: 'Ajouter ce contact',
                      onPressed: _addContact,
                    ),
                  ],
                ),
                if (_appVersion != null) const SizedBox(height: 24),
              ],
            ),
          ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
              child: Row(
                children: [
                  if (_appVersion != null)
                    Text(
                      'George v$_appVersion',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Theme.of(context).colorScheme.outline),
                    ),
                  const Spacer(),
                  OutlinedButton.icon(
                    onPressed: () => _signOut(context, ref),
                    icon: const Text('🚪'),
                    label: const Text('Se déconnecter'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
