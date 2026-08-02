# mobile

Application mobile Flutter pour George — V1 (MVP), consomme directement
l'API FastAPI existante (`api/`), sans notifications push (voir "Hors
périmètre V1" plus bas). Un portail d'accès simple (Supabase Auth, Phase 9)
protège l'accès depuis cette V2 — voir "Authentification" plus bas et
`CLAUDE.md` (section Auth) pour l'architecture complète.

## Commandes

```
flutter pub get
flutter analyze
flutter test
```

## Lancer l'app contre le backend

Le backend doit tourner (`uvicorn api.main:app --reload --host 0.0.0.0` —
`--host 0.0.0.0` est nécessaire dès qu'un émulateur/appareil doit joindre la
machine hôte, pas seulement `127.0.0.1`). L'URL de base de l'API se
configure via `--dart-define=API_BASE_URL=...` (défaut `http://localhost:8000`,
comme `web/.env.example` → `VITE_API_BASE_URL`) :

```
# Émulateur Android (10.0.2.2 alias le localhost de la machine hôte)
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000

# Simulateur iOS (localhost fonctionne directement)
flutter run --dart-define=API_BASE_URL=http://localhost:8000

# Appareil physique sur le même réseau (remplacer par l'IP LAN réelle)
flutter run --dart-define=API_BASE_URL=http://<ip-lan-machine-hote>:8000

# Backend réel hébergé sur Render (n'importe où, pas besoin du même Wi-Fi)
flutter run --dart-define=API_BASE_URL=https://george-api-mmut.onrender.com
```

CORS (`api/main.py:allow_origins`) ne concerne que les clients navigateur —
non-sujet pour un build natif Android/iOS. Android 9+ bloque le trafic HTTP
en clair par défaut : un build de développement pointant vers un backend en
`http://` (non `https://`) nécessite une configuration réseau autorisant le
cleartext (à ajouter si un vrai appareil Android refuse la connexion) — non
applicable au backend Render, qui est en `https://`. Les builds distribués
pour test (voir CLAUDE.md, section Hosting) pointent vers l'URL Render, pas
vers une IP locale — le service Render gratuit se met en veille après
inactivité (~50s de réveil au premier appel).

## Authentification (Supabase, Phase 9)

Chaque appel à l'API doit maintenant porter un jeton Supabase valide (voir
`CLAUDE.md` section Auth) — l'app affiche un écran de connexion tant qu'aucune
session n'existe. Deux nouvelles variables `--dart-define` sont requises :

```
flutter run \
  --dart-define=API_BASE_URL=http://10.0.2.2:8000 \
  --dart-define=SUPABASE_URL=https://<ref>.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=<clé anon publique>
```

Sans ces deux variables, l'écran de connexion s'affiche mais toute tentative
de connexion échoue (URL/clé vides) — utile pour vérifier rapidement que
l'app compile, pas pour un test de connexion réel. La connexion Google passe
par un deep link natif (`io.supabase.george://login-callback/`, configuré
dans `android/app/src/main/AndroidManifest.xml` ; l'équivalent iOS
`Info.plist`/`CFBundleURLTypes` doit recevoir une entrée `CFBundleURLTypes`
avec le même schéma custom — déposé en documentation ici mais **non
vérifié** : un build iOS ne peut pas être compilé/exécuté depuis cette
machine Windows, voir "iOS cannot be built or run from Windows" dans
`CLAUDE.md`).

## Périmètre V1

3 écrans consommant l'API REST existante : **Univers** (watchlist filtrable,
détail décision + graphique chandelier + explication LLM, chat, activité des
agents, tuile macro fictive, rafraîchissement des prix / collecte macro),
**Paniers** (KPIs, George Index par panier, répartition sectorielle, table de
décisions filtrable, sélection → création de portefeuille), **Mon
Portefeuille** (portefeuilles nommés, PnL, allocation budgétaire via un champ
numérique simple).

**Hors périmètre V1** (reporté à une phase ultérieure) : notifications push
(FCM), synthèse vocale / reconnaissance vocale natives (`flutter_tts`,
`speech_to_text`), cache hors-ligne, digest quotidien programmé, tests
end-to-end type Detox, tout produit Firebase. L'authentification (Supabase,
Phase 9) a depuis été ajoutée — voir la section dédiée ci-dessus et
`CLAUDE.md` (section Auth) pour le détail des décisions de périmètre.

## Architecture

- `lib/core/` — client HTTP (`dio`), résolution de l'URL de base, exception
  API typée, `core/auth/` (session Supabase, pont Riverpod, intercepteur Dio
  qui pose l'en-tête `Authorization`).
- `lib/models/` — une classe par schéma de `api/schemas.py`, écrite à la main
  (pas de génération OpenAPI — voir la justification dans `CLAUDE.md`).
- `lib/data/` — un repository par ressource API + les providers Riverpod
  associés (miroir de `web/src/api/queries.js`).
- `lib/features/` — un dossier par écran (`univers/`, `decision_detail/`,
  `paniers/`, `portefeuille/`, `auth/` — écran de connexion, `profile/` —
  écran de profil/déconnexion poussé depuis l'AppBar).
- Gestion d'état : Riverpod (`FutureProvider.family` par ressource,
  invalidation manuelle via `ref.invalidate(...)` après chaque mutation —
  équivalent du cache déclaratif de React Query côté web).
- Navigation : `go_router` (3 onglets + une route poussée pour le détail
  d'une décision).
