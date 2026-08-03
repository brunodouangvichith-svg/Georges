# George

Agent d'analyse technique des marchés financiers. Ce dépôt suit la roadmap détaillée dans `George_Prompts_Claude_Code.md` (8 phases). Ce README couvre les **Phases 0 à 4, et 6** (la Phase 5 « application mobile » a été volontairement sautée pour l'instant — voir CLAUDE.md) : fondations du projet (structure, Docker, schéma de base de données), moteur quantitatif (ingestion des prix, détection de patterns), mémoire historique/apprentissage continu (backtesting, score de confiance appris, paniers, George Index), l'API + l'interface web MVP branchée sur des données réelles, la couche LLM conversationnelle (explication des décisions, `/chat`, rapports indexés dans pgvector, second avis de Jane), le cycle de vie complet d'une décision (proposition automatique à partir d'une figure réelle, niveaux de sortie calculés, confirmation, suivi, clôture), et des portefeuilles nommés persistés en base (hors roadmap, demandés directement par l'utilisateur).

## Structure du dépôt

```
ingestion/   ingestion de données (yfinance) + schéma DB (migrations Alembic) — Phase 0/1
engine/      moteur de détection de patterns + scoring de confiance — Phase 1/2, déjà en place
agents/      explainer, /chat, rapports pgvector, second avis de Jane — Phase 4, déjà en place ; sous-agents de veille (presse, macro, géopolitique...) — Phase 7 (pas encore implémenté)
api/         API FastAPI — Phase 3, déjà en place
web/         interface web React (Vite + Tailwind), branchée sur l'API — Phase 3, déjà en place
mobile/      application mobile — Phase 5, volontairement sautée pour l'instant (voir CLAUDE.md)
infra/       docker-compose.yml et configuration d'infrastructure
tests/       tests pytest
```

## Prérequis

- [Docker](https://www.docker.com/) (avec Docker Compose v2) — pour lancer PostgreSQL, Redis, MinIO, Adminer.
- Python 3.11+.
- Une clé API [Mistral](https://console.mistral.ai/) (offre gratuite avec quota) pour la Phase 4 — voir section 11. Pas nécessaire pour les Phases 0-3.

Aucun de ces logiciels n'est requis pour lire le code, seulement pour l'exécuter.

## 1. Lancer l'environnement

```bash
cd infra
docker compose up -d
```

Cela démarre :
- **db** (PostgreSQL 17) sur `localhost:5432` — identifiants par défaut `george` / `george`, base `george` (voir `infra/.env.example` pour les surcharger via un fichier `.env` dans `infra/`).
- **redis** sur `localhost:6379`.
- **minio** (stockage compatible S3) sur `localhost:9000` (API) / `localhost:9001` (console web).
- **adminer** (administration web de la base) sur [localhost:8080](http://localhost:8080) — serveur `db`, utilisateur/mot de passe comme ci-dessus.

Pour arrêter : `docker compose down` (ajouter `-v` pour aussi supprimer les volumes de données).

**Raccourci** : une fois l'environnement Python (étape 2) et les dépendances web (étape 10) installés au moins une fois, `scripts\dev-up.ps1` démarre Docker (si besoin), l'infra, l'API et le serveur web en une seule commande, tous en arrière-plan :
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1
```
Idempotent (relançable sans dupliquer ce qui tourne déjà) ; logs dans `.dev-logs/` à la racine du dépôt.

## 2. Installer l'environnement Python

Depuis la racine du dépôt :

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # macOS/Linux

pip install -e ".[dev]"
```

## 3. Appliquer les migrations

Avec l'environnement Docker démarré (étape 1) :

```bash
alembic upgrade head
```

Ceci crée les 9 tables du schéma : `securities`, `prices_ohlcv`, `patterns_detected`, `decisions`, `decision_outcomes` (migration `0001`), `baskets`, `basket_securities`, `pattern_candidates` (migration `0002`, Phase 2), puis `agent_events` (migration `0003`, Phase 3).

Par défaut, la connexion utilisée est `postgresql+psycopg://george:george@localhost:5432/george` (voir `ingestion/db.py`). Pour la surcharger, définir la variable d'environnement `DATABASE_URL` avant d'exécuter `alembic` (ou tout autre script Python du dépôt).

## 4. Charger l'univers de départ (CAC 40 + CAC Mid 60)

```bash
python -m ingestion.seed
```

Charge les 40 valeurs du CAC 40 (voir `ingestion/cac40.py`) et les 62 valeurs du CAC Mid 60 (voir `ingestion/cac_mid60.py` — l'indice actuel le plus proche du "second marché" historique) dans `securities`, avec `theme` distinguant les deux univers. Idempotent : peut être relancé sans créer de doublons.

## 5. Lancer les tests

```bash
pytest
```

Les tests (`tests/test_migrations.py`, `tests/test_seed.py`) utilisent [testcontainers](https://testcontainers.com/) pour démarrer une instance Postgres jetable et vérifier que les migrations s'appliquent (et se retirent) proprement sur une base vide, et que le seed charge bien les 40 valeurs de façon idempotente. **Ils nécessitent un démon Docker actif** (indépendamment de la stack `infra/docker-compose.yml`, qui n'a pas besoin d'être démarrée pour lancer les tests).

## 6. Télécharger l'historique des prix (Phase 1, table repointée vers price_history_long — ad hoc)

Avec l'environnement Docker démarré et l'univers chargé (étapes 1 et 4) :

```bash
python -m ingestion.price_history
```

Télécharge, via [yfinance](https://pypi.org/project/yfinance/), jusqu'à 10 ans d'historique quotidien de chaque titre de `securities` et le charge dans `price_history_long` (upsert, sans danger à relancer). Les échecs (ticker introuvable, erreur réseau — jusqu'à 3 tentatives par titre) sont listés à la fin sans bloquer les autres titres. Nécessite un accès réseau vers Yahoo Finance. **Table dont dépend toute la suite** (détection, propositions, George Index, graphique de l'écran Univers) — voir CLAUDE.md, section "Long-term price history".

`python -m ingestion.ohlcv` existe toujours séparément (alimente `prices_ohlcv`, 2 ans) mais plus aucun code applicatif ne la lit depuis ce changement — gardée pour compatibilité/historique, pas requise pour suivre la suite de ce guide.

Aucune tâche planifiée à fréquence fine n'existe encore (Phase 7) — un rafraîchissement hebdomadaire automatique existe (`weekly_price_history_import.yml`, dimanche), et la même chose est déclenchable manuellement depuis l'écran **Univers** via le bouton **🔄 Mise à jour des prix** sous « Univers » dans la navigation, qui appelle `POST /prices/refresh` (dure jusqu'à 2 minutes pour tout l'univers — 10 ans d'historique par titre).

## 7. Détecter les figures chartistes (Phase 1)

```bash
python -m engine.run_detection
```

Exécute les 13 détecteurs de `engine/patterns/` (Double Bottom, Double Top, Cup & Handle, Bull/Bear Flag, Ascending/Descending Triangle, Falling/Rising Wedge, Head & Shoulders et inverse, Breakout, Breakdown) sur l'historique de chaque titre et insère les figures confirmées dans `patterns_detected`, avec un score de confiance 0-100 (`engine/confidence.py` : géométrie de la figure + confirmation de volume + alignement avec les moyennes mobiles 50/200 — voir la documentation en tête de chaque fichier de `engine/patterns/` pour le détail des tolérances géométriques).

Un notebook de validation visuelle (chandeliers + figure surlignée, via mplfinance) est disponible dans `engine/notebooks/pattern_validation.ipynb` — il retombe sur des données synthétiques si la base n'est pas peuplée. Nécessite l'extra `notebook` : `pip install -e ".[dev,notebook]"`.

Les détecteurs eux-mêmes (`engine/patterns/`, `engine/detect.py`) ne dépendent pas de la base de données et sont testés unitairement sur des séries synthétiques (`tests/test_patterns.py`, indépendant de Docker) — voir `pytest tests/test_patterns.py`.

## 8. Score de confiance appris et George Index (Phase 2)

```bash
python -m engine.build_training_set   # assemble engine/data/training_set.parquet depuis patterns_detected + price_history_long
```

Puis, dans `engine/notebooks/train_confidence_model.ipynb` (offline — nécessite l'extra `notebook`) : entraîne un pipeline scikit-learn (imputation + one-hot) + `XGBClassifier` prédisant le succès d'une figure à horizon 10 séances, et sauvegarde le pipeline entraîné sous `engine/models/confidence_xgb_<date>.joblib` (+ métadonnées `.meta.json`). Si `engine/data/training_set.parquet` n'existe pas encore, le notebook retombe sur un jeu de données synthétique pour rester exécutable sans base peuplée.

`python -m engine.run_detection` utilise automatiquement le modèle le plus récent trouvé dans `engine/models/` pour scorer chaque figure détectée, et ne retombe sur l'heuristique de la Phase 1 (`engine/confidence.py`) que si aucun modèle n'est disponible ou que l'historique du titre est insuffisant — voir `engine/scoring.py`.

```bash
python -m engine.compute_george_index   # affiche le George Index de chaque panier (baskets/basket_securities)
python -m engine.reevaluate_decisions   # met à jour decision_outcomes pour les décisions existantes
```

La formule exacte du George Index est documentée dans `engine/george_index.md` (implémentation : `engine/george_index.py`, sans accès DB, testée sur données synthétiques dans `tests/test_george_index.py`). `pattern_candidates` (même schéma que `patterns_detected`) est un espace de backtesting pour les figures que proposera l'agent de veille méthodologique de la Phase 7 — rien ne l'alimente encore automatiquement.

Comme pour la Phase 1, tout le code testable sans base (`engine/features.py`, `engine/backtest.py`, `engine/george_index.py`, `engine/scoring.py`) l'est : `pytest tests/test_features.py tests/test_backtest.py tests/test_george_index.py tests/test_scoring.py`.

## 9. Lancer l'API (Phase 3)

Avec l'environnement Docker démarré et les migrations appliquées (étapes 1 et 3) :

```bash
uvicorn api.main:app --reload
```

Documentation interactive générée automatiquement par FastAPI : [localhost:8000/docs](http://localhost:8000/docs) (Swagger UI) et `/openapi.json`. Endpoints : `GET /securities` (paginé, filtrable par `basket_id`), `GET /securities/{symbol}/patterns`, `GET /securities/{symbol}/prices` (ajouté au-delà de la liste minimale du prompt — indispensable au graphique en chandeliers du panneau de détail), `GET /baskets`, `GET /baskets/{id}/george-index` (réutilise directement `engine.george_index`, Phase 2), `GET /decisions` (filtrable par `status`/`basket_id`), `GET /agents/activity` (filtrable par `status`/`symbol`). Pas d'authentification à ce stade (Phase 9).

Pour peupler un peu la base au-delà de l'univers CAC 40 et de son historique de prix (paniers, décisions, activité d'agents — sinon l'API renvoie des listes vides, ce qui est un état honnête mais peu démonstratif) :

```bash
python -m ingestion.seed_demo
```

Crée un panier par secteur (équipondéré), et — seulement pour les titres ayant déjà un historique de prix (`ingestion.price_history`) — quelques décisions et événements d'agents **explicitement illustratifs** (`ingestion/seed_demo.py`), en attendant que les Phases 6/7 les génèrent réellement. Idempotent.

Tests d'intégration (`tests/test_api.py`, pytest + `fastapi.testclient`) : la plupart nécessitent Docker (testcontainers), mais `test_db_unreachable_returns_503_with_cors_headers` ne l'exige pas — il couvre spécifiquement un piège Starlette rencontré pendant le développement (voir `api/main.py:database_exception_handler`) où un handler enregistré pour la classe `Exception` nue est redirigé vers `ServerErrorMiddleware`, *au-dessus* de `CORSMiddleware`, produisant une erreur CORS trompeuse côté navigateur au lieu du vrai message d'erreur.

## 10. Interface web (Phase 3)

```bash
cd web
npm install
cp .env.example .env   # optionnel : surcharge VITE_API_BASE_URL (défaut : http://localhost:8000)
npm run dev
```

Branchée sur l'API réelle via [React Query](https://tanstack.com/query) (`web/src/api/`) — plus de données fictives dans les vues Univers/Paniers (voir `CLAUDE.md` pour le détail de l'architecture). Base vide ou API non démarrée : chaque vue affiche un message d'état clair (« Aucun titre en base », « Impossible de contacter l'API »...) plutôt qu'un écran vide ou cassé.

```bash
npm run build   # build de production
npm run lint     # oxlint
npm run test     # Vitest + React Testing Library — aucune dépendance à Docker ni à l'API réelle (hooks mockés)
```

## 11. Couche LLM conversationnelle (Phase 4)

Nécessite une clé API Mistral, exportée avant de lancer `uvicorn` (ou tout script appelant `agents.mistral_client`) :

```bash
export MISTRAL_API_KEY="ta_cle_ici"       # macOS/Linux
$env:MISTRAL_API_KEY = "ta_cle_ici"       # PowerShell
```

Sans clé configurée, les endpoints LLM répondent `503` proprement (pas de crash — voir `api/main.py:mistral_exception_handler`) plutôt que d'échouer silencieusement ; le reste de l'API (Phases 0-3) fonctionne normalement.

```bash
alembic upgrade head   # migration 0004 : active l'extension pgvector + table reports
```

Trois capacités, toutes en `POST` (le CORS de l'API n'autorisait que `GET` jusqu'à la Phase 3) :

- **`POST /decisions/{id}/explanation`** — génère l'explication en français d'une décision existante (figure détectée, confiance, confirmations, risques — voir `agents/explainer.py` et `agents/prompts/explainer_system.txt`), avec `mistral-small-latest`. Body optionnel `{"include_second_opinion": true}` pour appeler d'abord **Jane** (`agents/jane.py`, `mistral-large-latest`, prompt système `agents/prompts/jane_second_opinion_system.txt` — corpus de gestion de portefeuille détaillé dans `Jane_Synthese_Connaissances.md`) : sa note contradictoire est alors passée en contexte à l'explication finale de George, qui l'arbitre. C'est un second appel LLM distinct et explicite, pas un simple paramètre du premier — conformément à la roadmap. Jane ne détecte jamais de pattern et ne décide jamais.
- **`POST /chat`** — question libre (`{"question": "..."}`), routée par RAG SQL simple (`agents/chat.py` : reconnaissance de titres par symbole/nom dans la question, données réelles assemblées en contexte) avant l'appel LLM — pas de recherche vectorielle ici, réservée aux rapports.
- **`POST /reports`** (`{"basket_id": <id ou omis pour un rapport portefeuille>}`) — génère un rapport texte (`agents/reports.py`) résumant l'état d'un panier (George Index réel, décisions actives) ou de l'ensemble du portefeuille, l'indexe via un embedding `mistral-embed` dans `reports` (pgvector). `GET /reports` (paginé, filtrable par `basket_id`) et `GET /reports/search?q=...` (recherche sémantique par similarité cosinus) le relisent ensuite.

Le prompt système de chaque capacité interdit explicitement au LLM d'inventer un chiffre absent du contexte structuré fourni (`agents/prompts/*.txt`) — vérifié dans `tests/test_agents.py` (constructeurs de contexte, sans DB) et `tests/test_api.py` (avec un client Mistral factice qui recopie le contexte reçu, pour vérifier qu'aucune valeur réelle n'est perdue en chemin sans dépendre d'un vrai appel réseau).

## 12. Gestion du risque et cycle de vie des décisions (Phase 6)

Avec l'environnement Docker démarré et les migrations appliquées :

```bash
alembic upgrade head              # migration 0005 : cycle de vie des décisions (status, pattern_id, exit_*)
python -m engine.propose_decisions # scanne les figures actives à forte confiance -> crée des décisions "proposee"
python -m engine.monitor_decisions # job de suivi : décisions "confirmee" ayant franchi TP/SL -> "sortie_proposee"
```

Une décision suit désormais un vrai cycle de vie, `status` en base : `proposee` (créée automatiquement à partir d'une figure réelle détectée, jamais confirmée) → `confirmee` (validée par l'investisseur, niveaux éventuellement ajustés) → `sortie_proposee` (le job de suivi a détecté un franchissement de take-profit/stop-loss et propose un scénario de sortie justifié) → `cloturee` (sortie confirmée). Endpoints, tous en `POST` sauf le premier :

- **`GET /decisions?status=proposee`** (ou `confirmee`/`sortie_proposee`/`cloturee`) — filtre par statut de cycle de vie ; `decision_type` (ex. `Achat`) reste le paramètre pour filtrer par type de décision (renommé depuis `status` pour éviter la collision de noms).
- **`POST /decisions/propose`** — déclenche `engine.propose_decisions` : une proposition par titre qualifiant (figure active, confiance ≥ 50 %, pas de décision déjà ouverte sur ce titre), avec take-profit/stop-loss calculés depuis la géométrie réelle de la figure (`engine/exit_levels.py`).
- **`POST /decisions/{id}/propose-levels`** — recalcule les niveaux sur le prix le plus récent (tant que la décision est encore `"proposee"`).
- **`POST /decisions/{id}/confirm`** (body optionnel `{"take_profit": ..., "stop_loss": ...}` pour ajuster avant validation) — passe la décision à `"confirmee"`.
- **`POST /decisions/monitor`** — déclenche `engine.monitor_decisions` : pour chaque décision confirmée ayant atteint son take-profit ou franchi son stop-loss, propose un scénario de sortie (`sortie_totale`/`sortie_partielle`, avec distinction franchissement confirmé par le volume vs. bruit — `engine/exit_scenarios.py`) et sa justification textuelle (`agents/explainer.py:explain_exit_scenario`, Phase 4). Ne clôture jamais une position lui-même.
- **`POST /decisions/{id}/confirm-exit`** — seule action qui clôture réellement une décision : enregistre le résultat dans `decision_outcomes` (pour un futur réentraînement du modèle, Phase 2) et passe la décision à `"cloturee"`.

Testé de bout en bout contre la base de développement réelle (109 figures détectées sur l'univers CAC 40) : 16 propositions générées avec des niveaux cohérents ; voir `tests/test_exit_levels.py` (les 13 types de figures, sans DB), `tests/test_exit_scenarios.py`, `tests/test_reevaluate_decisions.py`, et `tests/test_api.py` pour le cycle complet propose → confirm → monitor → confirm-exit avec Docker.

## 13. Sous-agents de collecte (Phase 7, MVP volontairement réduit)

```bash
alembic upgrade head              # migration 0008 : collected_info_quarantine
uvicorn api.main:app --reload     # POST /agents/collect, GET /agents/activity
```

La Phase 7 complète (orchestrateur LangGraph, Celery+Redis, Playwright/Scrapy, Airflow, 6 sous-agents, 4 modes d'activation) est décrite par la roadmap elle-même comme "l'étape la plus complexe du projet" — plusieurs semaines de travail. Ce qui est construit ici, avec l'accord explicite de l'utilisateur (mode plan) pour réduire le périmètre plutôt que de tout tenter d'un coup :

- **L'orchestrateur** (`agents/orchestrator/run.py:run_collection_task`) et le **module de validation/quarantaine** (`agents/orchestrator/validation.py`) — recoupement multi-sources, score de fiabilité, mise en quarantaine (`collected_info_quarantine`) en cas de désaccord non résolu.
- **2 sous-agents** sur les 6 prévus, déclenchables manuellement via `POST /agents/collect` (même principe que `POST /prices/refresh`, pas de scheduler) :
  - **`donnees_macro`** (`agents/collectors/macro.py`) — FRED et la BCE, deux API publiques sans clé. Le taux EUR/USD est recoupé sur les deux sources pour de vrai (valeurs proches mais pas identiques en pratique) ; le taux OAT 10 ans reste à une seule source.
  - **`synthese_document`** (`agents/collectors/synthesis.py`) — résume un `Report` déjà généré (Phase 4) en quelques indicateurs via un appel Mistral dédié. **Remplace le sous-agent "fondamentaux d'entreprise" (SEC EDGAR)** prévu par la roadmap : vérifié contre `company_tickers.json` de la SEC, seulement ~5-6 des 102 titres suivis ont un vrai dépôt SEC — une couverture jugée trop faible par l'utilisateur pour la construire telle quelle.
- Différé explicitement : agents de scraping (actualités réglementaires, calendrier résultats, presse sectorielle), veille méthodologique continue de Jane (réservée par la roadmap à une infra de tâches de fond à faible priorité qui n'existe pas encore — sa second-opinion synchrone, elle, est en place depuis la Phase 4), et 3 des 4 modes d'activation (veille continue, batch Airflow, réaction à un manque identifié).

Testé contre l'environnement de dev réel : `POST /agents/collect` avec `donnees_macro` a bien écrit deux `agent_events` validés (OAT 10 ans à 3.68 %, EUR/USD à 1.1385/1.1389 selon la source, écart 0.04 %) ; `synthese_document` contre un vrai rapport a produit une synthèse fidèle aux chiffres réels du rapport, sans rien inventer.

## 14. Portefeuilles nommés (hors roadmap)

Fonctionnalité demandée directement par l'utilisateur, pas dans `George_Prompts_Claude_Code.md` — persistée en base (`portfolios`/`portfolio_decisions`, migration `0006`), pas en localStorage, pour survivre au navigateur qui l'a créée.

- **`POST /portfolios`** (`{"name": "...", "decision_ids": [...]}`) — crée un portefeuille nommé à partir de décisions existantes.
- **`GET /portfolios`** — liste tous les portefeuilles, chacun avec ses décisions complètes.
- **`DELETE /portfolios/{id}`** — supprime un portefeuille entier.
- **`DELETE /portfolios/{id}/decisions/{decision_id}`** — retire une seule décision d'un portefeuille.
- **`POST /portfolios/{id}/allocate`** (`{"budget": 100000}`) — répartit un budget entre les décisions du portefeuille (pondération confiance × ratio gain/risque, calcul déterministe, voir `engine/portfolio_allocation.py`), fixe la quantité (nombre entier d'actions) de chacune, et renvoie un résumé texte de la répartition.

Sur l'écran **Paniers** : une colonne « Portefeuille » (case à cocher) entre Confiance et Créée le. Cocher des lignes ne les envoie pas tout de suite à l'API — un bouton « Créer un portefeuille (N) » apparaît, ouvrant un popup (nom + ❌ Annuler / ✅ Enregistrer) qui appelle `POST /portfolios` seulement à la confirmation.

Le nouvel écran **Mon Portefeuille** (onglet dédié) liste chaque portefeuille sauvegardé avec ses décisions (Ticker, Entrée, **Prix**, Take-profit, Stop-loss, **PnL**, Quantité, **Date**, **Heure**), permet de retirer une décision ou de supprimer un portefeuille entier, et propose un bouton **🎙 Demander à George** par portefeuille — suivi de la date de création du portefeuille (« Créé le … ») : commande vocale (même reconnaissance vocale que sur Univers, voir `web/src/hooks/useVoiceCapture.js`) qui comprend un montant en euros dans la phrase ("répartis un budget de 100 000 euros entre ces actions en fonction du risque et des profits") et appelle `POST /portfolios/{id}/allocate` avec ce montant.

`Prix` (dernier cours connu) et `PnL` (rendement % depuis l'entrée) sont calculés à la volée à chaque requête, pas stockés, avec la même convention de signe directionnelle (Achat/Renforcer haussier, Alléger baissier) que le reste du moteur. Les colonnes **Date**/**Heure** montrent quand ce prix a été mis à jour (`price_updated_at`, la séance du dernier prix ingéré), pas quand la décision a été proposée — les deux sont des événements distincts. En bas de chaque portefeuille, un total **PnL du portefeuille** (somme en € + %) n'apparaît que si au moins une décision a une quantité *et* un PnL calculable — sinon un message invite à renseigner des quantités via « Demander à George ».

Les onglets « Décisions » et « Alertes » (`Placeholder` jamais implémentés depuis la Phase 3) ont été retirés de la navigation à cette occasion.
