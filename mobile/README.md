# mobile

Application mobile Flutter pour George — V1 (MVP), consomme directement
l'API FastAPI existante (`api/`), sans authentification ni notifications
push (voir "Hors périmètre V1" plus bas).

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
```

CORS (`api/main.py:allow_origins`) ne concerne que les clients navigateur —
non-sujet pour un build natif Android/iOS. Android 9+ bloque le trafic HTTP
en clair par défaut : un build de développement pointant vers un backend en
`http://` (non `https://`) nécessite une configuration réseau autorisant le
cleartext (à ajouter si un vrai appareil Android refuse la connexion).

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
`speech_to_text`), cache hors-ligne, digest quotidien programmé,
authentification (Firebase Auth ou autre), tests end-to-end type Detox, tout
produit Firebase. Voir `CLAUDE.md` (section App mobile) pour le détail des
décisions de périmètre.

## Architecture

- `lib/core/` — client HTTP (`dio`), résolution de l'URL de base, exception
  API typée.
- `lib/models/` — une classe par schéma de `api/schemas.py`, écrite à la main
  (pas de génération OpenAPI — voir la justification dans `CLAUDE.md`).
- `lib/data/` — un repository par ressource API + les providers Riverpod
  associés (miroir de `web/src/api/queries.js`).
- `lib/features/` — un dossier par écran (`univers/`, `decision_detail/`,
  `paniers/`, `portefeuille/`).
- Gestion d'état : Riverpod (`FutureProvider.family` par ressource,
  invalidation manuelle via `ref.invalidate(...)` après chaque mutation —
  équivalent du cache déclaratif de React Query côté web).
- Navigation : `go_router` (3 onglets + une route poussée pour le détail
  d'une décision).
