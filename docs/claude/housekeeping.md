# Entretien du dépôt (housekeeping)

Inventaire de ce qui est à ranger, établi le 26/11/2026 sur `main` (`6d05bbf`) à partir du graphe graphify, puis vérifié dans Git et les fichiers. **Rien n'a été supprimé.** Les tailles et l'état des branches sont ceux de ce jour : les revérifier avant d'agir.

## Règles

- Le dépôt est **public** : aucun secret ni réglage propre à une machine.
- Une branche fusionnée en « squash » n'est pas reconnue par `git branch -d`. Avant de la supprimer, comparer son dernier commit à celui de la PR, ou lancer `git cherry main <branche>`.
- Ne jamais supprimer ni pousser une branche **sans distant** sans avoir lu son contenu et ses notes.
- Ne pas supprimer un fichier sur la seule foi du graphe : confirmer les imports par une recherche texte (les imports dans le corps d'une fonction comptent).
- Après toute modification de code : `graphify update .`.

## Branches

### Fusionnées dans `main`, supprimables en local et sur `origin`

| Branche | PR |
| --- | --- |
| `claude/responsive-graphiques-7b4d7a` (retirer d'abord son worktree) | 33 |
| `docs/decouper-claude-md-main` | 27 |
| `feat/accueil-sans-journal-ni-index` | 30 |
| `feat/backtest-detecteurs` (dernier commit local repris par la 26) | 25, 26 |
| `feat/web-telephone` | 29 |
| `feat/zoom-radar` | 32 |
| `fix/backtest-cours-corrompus` | 26 |
| `fix/datefr-date-seule` | 37 |
| `fix/defilement-page-telephone` | 31 |
| `fix/rapport-oat-valeur-actuelle` | 34 |
| `fix/rapport-rappel-obligataire` | 35 |
| `fix/retablir-horaires-github` | 28 |
| `ui/retirer-onglet-obligataire` | 36 |

### À conserver pour l'instant

- `docs/decouper-claude-md` : ses documents sont repris dans `main` (versions plus récentes), mais elle est la **seule à contenir `scripts/graph3d.py`**, le générateur de la vue 3D. Récupérer ce script avant de la supprimer.
- Toute autre branche locale sans distant : travail non publié, à traiter au cas par cas.

## Worktrees

`git worktree list` montre ceux de `.claude/worktrees/`.

- `responsive-graphiques-7b4d7a` (environ 258 Mo) : branche fusionnée ; seul contenu non suivi, `graphify-out/`. Retirable après avoir vérifié qu'aucune session ne l'utilise.
- Les autres : vérifier que leur branche est fusionnée avant retrait.

## Fichiers non suivis

| Élément | Constat | Proposition |
| --- | --- | --- |
| `.claude/settings.json` | Hooks graphify avec un chemin absolu propre à un poste | Ne pas commiter tel quel ; ignorer `.claude/` |
| `graphify-out/` (environ 20 Mo) | Non suivi, alors que `CLAUDE.md` parle d'un `graph.json` commité | Choisir : l'ignorer et corriger `CLAUDE.md`, ou suivre `graph.json` |
| `.gitattributes` | Une ligne, pilote de fusion pour `graphify-out/graph.json` | Utile seulement si `graph.json` est suivi |

`.gitignore` n'exclut aujourd'hui que `.claude/settings.local.json`.

## Code qui n'est plus utilisé, ou en partie

| Élément | État vérifié | Avant de supprimer |
| --- | --- | --- |
| `web/src/views/Obligataire.jsx` et son test | Plus affiché depuis la PR 36, conservé volontairement | Décision de l'utilisateur |
| `BondHistoryChart.jsx`, `bondChartLayout.js` et leurs tests | Importés seulement par cet écran | Partent avec lui |
| Hooks obligataires de `api/queries.js` | `useBondDashboard` sert encore à Rapport | Garder celui-là ; vérifier les autres un à un |
| `ResponsePopup.jsx`, `useElementWidth.js` | Partagés avec Trading ou Univers | Ne pas supprimer |
| `ingestion/ohlcv.py` | `download_symbol` sert à `price_history.py` et `backtest_detectors.py` | Ne pas supprimer le module |
| Table `prices_ohlcv` | Plus lue par l'analyse (`CLAUDE.md`) | Migration écrite à la main, après sauvegarde |
| `mobile/` et `build_mobile_apk.yml` | Application mise de côté ; workflow manuel | Ne pas porter de fonctions ni lancer le build sans demander |
| `cloudflare-cron/` | Désactivé, `crons = []` | Vérifier que le déclencheur est bien retiré côté Cloudflare ; ne jamais l'activer avec les horaires GitHub |

## Fichiers à la racine

Aucun code Python n'importe `edgar_client.py` ni le `mistral_client.py` de la racine (le client utilisé est `agents/mistral_client.py`).

| Fichiers | Constat |
| --- | --- |
| `GeorgeDashboard.jsx`, `george_web_interface.html`, `edgar_client.py` | Prototypes de juillet 2026, cités par l'historique (`docs/claude/`) |
| `mistral_client.py` | Prototype ; cité par `README.md` et les documents de prompts |
| `*.pdf`, `*.docx` | Documents de présentation, environ 220 Ko |
| `TAVILY_ALTERNATIVES.md` | Aucun autre fichier ne le cite |
| `whitelist_journaux.json` | **Utilisé** par `agents/geopolitical_veille.py` : à garder |

Piste : déplacer prototypes et documents dans `docs/archive/`, puis corriger les références.

## Espace disque (régénérable, non versionné)

| Dossier | Taille | Régénération |
| --- | --- | --- |
| `mobile/build` | 1,1 Go | build Flutter |
| `.venv` | 703 Mo | `pip install -e ".[dev]"` (utile au quotidien) |
| `.claude/worktrees` | 277 Mo | voir « Worktrees » |
| `web/node_modules` | 233 Mo | `npm install` dans `web/` |
| `mobile/.dart_tool` | 191 Mo | `flutter pub get` |

## Tâches planifiées

Horaires `cron` des fichiers de `.github/workflows/`, en UTC. GitHub peut les déclencher avec des heures de retard.

| Workflow | Horaire |
| --- | --- |
| `keep_api_warm.yml` | toutes les 10 minutes |
| `daily_energy_import.yml` | chaque jour, 06:00 |
| `daily_bond_yields.yml` | chaque jour, 07:00 |
| `daily_fundamentals_import.yml` | chaque jour, 20:00 |
| `daily_george_veille.yml` | chaque jour, 21:00 |
| `price_history_and_detection.yml` | lundi et mercredi, 20:00 |
| `weekly_jane_veille_web.yml` | samedi, 20:00 |
| `weekly_confidence_model_training.yml` | dimanche, 20:00 |
| `weekly_geopolitical_veille.yml` | dimanche, 22:00 |
| `tests.yml` | pull request, push sur `main`, manuel |
| `build_mobile_apk.yml` | manuel |

## Documentation et suivi

- `TODO.md` ne contient qu'un sujet : mesurer la valeur prédictive du second avis de Jane, quand assez de décisions seront clôturées.
- Les fichiers de `docs/claude/` sont un historique : ils citent des workflows disparus (`daily_yfinance_import.yml`, `weekly_price_history_import.yml`). Ne pas les prendre pour l'état actuel.
- `graphify-out/graph3d.html` n'est pas régénéré par `graphify update .`.

## Routine proposée

| Quand | Action |
| --- | --- |
| Après chaque fusion | Supprimer la branche et son worktree ; `git pull` sur `main` |
| Chaque semaine | Contrôler les exécutions dans l'onglet Actions |
| Chaque mois | `git fetch --prune`, revoir les branches et worktrees, relire `TODO.md` |
