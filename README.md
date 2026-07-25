# George

Agent d'analyse technique des marchés financiers. Ce dépôt suit la roadmap détaillée dans `George_Prompts_Claude_Code.md` (8 phases). Ce README couvre les **Phases 0 et 1** : fondations du projet (structure, Docker, schéma de base de données) et moteur quantitatif (ingestion des prix, détection de patterns).

## Structure du dépôt

```
ingestion/   ingestion de données (yfinance) + schéma DB (migrations Alembic) — Phase 0/1
engine/      moteur de détection de patterns + scoring de confiance — Phase 1, déjà en place
agents/      sous-agents de veille (presse, macro, géopolitique...) — Phase 7 (pas encore implémenté)
api/         API FastAPI — Phase 3 (pas encore implémenté)
web/         interface web React (Vite + Tailwind) — Phase 3, déjà en place
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

Ceci crée les 5 tables du schéma initial : `securities`, `prices_ohlcv` (hypertable TimescaleDB), `patterns_detected`, `decisions`, `decision_outcomes`.

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

## Interface web

Le prototype front-end (`web/`) est déjà implémenté — voir `web/README.md` et `CLAUDE.md` à la racine pour le lancer. Il fonctionne aujourd'hui avec des données fictives (`web/src/data.js`) ; le raccordement à l'API réelle (`api/`, Phase 3) reste à faire.
