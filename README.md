# George

Agent d'analyse technique des marchés financiers. Ce dépôt suit la roadmap détaillée dans `George_Prompts_Claude_Code.md` (8 phases). Ce README couvre les **Phases 0 à 3** : fondations du projet (structure, Docker, schéma de base de données), moteur quantitatif (ingestion des prix, détection de patterns), mémoire historique/apprentissage continu (backtesting, score de confiance appris, paniers, George Index), et l'API + l'interface web MVP branchée sur des données réelles.

## Structure du dépôt

```
ingestion/   ingestion de données (yfinance) + schéma DB (migrations Alembic) — Phase 0/1
engine/      moteur de détection de patterns + scoring de confiance — Phase 1/2, déjà en place
agents/      sous-agents de veille (presse, macro, géopolitique...) — Phase 7 (pas encore implémenté)
api/         API FastAPI — Phase 3, déjà en place
web/         interface web React (Vite + Tailwind), branchée sur l'API — Phase 3, déjà en place
mobile/      application mobile (pas encore planifié)
infra/       docker-compose.yml et configuration d'infrastructure
tests/       tests pytest
```

## Prérequis

- [Docker](https://www.docker.com/) (avec Docker Compose v2) — pour lancer PostgreSQL/TimescaleDB, Redis, MinIO, Adminer.
- Python 3.11+.

Aucun de ces deux logiciels n'est requis pour lire le code, seulement pour l'exécuter.

## 1. Lancer l'environnement

```bash
cd infra
docker compose up -d
```

Cela démarre :
- **db** (PostgreSQL 16 + TimescaleDB) sur `localhost:5432` — identifiants par défaut `george` / `george`, base `george` (voir `infra/.env.example` pour les surcharger via un fichier `.env` dans `infra/`).
- **redis** sur `localhost:6379`.
- **minio** (stockage compatible S3) sur `localhost:9000` (API) / `localhost:9001` (console web).
- **adminer** (administration web de la base) sur [localhost:8080](http://localhost:8080) — serveur `db`, utilisateur/mot de passe comme ci-dessus.

Pour arrêter : `docker compose down` (ajouter `-v` pour aussi supprimer les volumes de données).

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

Ceci crée les 9 tables du schéma : `securities`, `prices_ohlcv` (hypertable TimescaleDB), `patterns_detected`, `decisions`, `decision_outcomes` (migration `0001`), `baskets`, `basket_securities`, `pattern_candidates` (migration `0002`, Phase 2), puis `agent_events` (migration `0003`, Phase 3).

Par défaut, la connexion utilisée est `postgresql+psycopg://george:george@localhost:5432/george` (voir `ingestion/db.py`). Pour la surcharger, définir la variable d'environnement `DATABASE_URL` avant d'exécuter `alembic` (ou tout autre script Python du dépôt).

## 4. Charger l'univers de départ (CAC 40)

```bash
python -m ingestion.seed
```

Charge les 40 valeurs du CAC 40 (ticker, nom, secteur — voir `ingestion/cac40.py`) dans `securities`. Idempotent : peut être relancé sans créer de doublons.

## 5. Lancer les tests

```bash
pytest
```

Les tests (`tests/test_migrations.py`, `tests/test_seed.py`) utilisent [testcontainers](https://testcontainers.com/) pour démarrer une instance TimescaleDB jetable et vérifier que les migrations s'appliquent (et se retirent) proprement sur une base vide, et que le seed charge bien les 40 valeurs de façon idempotente. **Ils nécessitent un démon Docker actif** (indépendamment de la stack `infra/docker-compose.yml`, qui n'a pas besoin d'être démarrée pour lancer les tests).

## 6. Télécharger l'historique des prix (Phase 1)

Avec l'environnement Docker démarré et l'univers chargé (étapes 1 et 4) :

```bash
python -m ingestion.ohlcv
```

Télécharge, via [yfinance](https://pypi.org/project/yfinance/), l'historique quotidien (2 ans par défaut) de chaque titre de `securities` et le charge dans `prices_ohlcv` (upsert, sans danger à relancer). Les échecs (ticker introuvable, erreur réseau — jusqu'à 3 tentatives par titre) sont listés à la fin sans bloquer les autres titres. Nécessite un accès réseau vers Yahoo Finance.

## 7. Détecter les figures chartistes (Phase 1)

```bash
python -m engine.run_detection
```

Exécute les 13 détecteurs de `engine/patterns/` (Double Bottom, Double Top, Cup & Handle, Bull/Bear Flag, Ascending/Descending Triangle, Falling/Rising Wedge, Head & Shoulders et inverse, Breakout, Breakdown) sur l'historique de chaque titre et insère les figures confirmées dans `patterns_detected`, avec un score de confiance 0-100 (`engine/confidence.py` : géométrie de la figure + confirmation de volume + alignement avec les moyennes mobiles 50/200 — voir la documentation en tête de chaque fichier de `engine/patterns/` pour le détail des tolérances géométriques).

Un notebook de validation visuelle (chandeliers + figure surlignée, via mplfinance) est disponible dans `engine/notebooks/pattern_validation.ipynb` — il retombe sur des données synthétiques si la base n'est pas peuplée. Nécessite l'extra `notebook` : `pip install -e ".[dev,notebook]"`.

Les détecteurs eux-mêmes (`engine/patterns/`, `engine/detect.py`) ne dépendent pas de la base de données et sont testés unitairement sur des séries synthétiques (`tests/test_patterns.py`, indépendant de Docker) — voir `pytest tests/test_patterns.py`.

## 8. Score de confiance appris et George Index (Phase 2)

```bash
python -m engine.build_training_set   # assemble engine/data/training_set.parquet depuis patterns_detected + prices_ohlcv
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

Crée un panier par secteur (équipondéré), et — seulement pour les titres ayant déjà un historique de prix (`ingestion.ohlcv`) — quelques décisions et événements d'agents **explicitement illustratifs** (`ingestion/seed_demo.py`), en attendant que les Phases 6/7 les génèrent réellement. Idempotent.

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
