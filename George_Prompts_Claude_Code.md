# George — Prompts Claude Code par étape de développement

Ce document contient un prompt prêt à l'emploi pour Claude Code à chaque phase de la roadmap. Chaque prompt suppose que les phases précédentes ont déjà été implémentées et sont disponibles dans le dépôt. Adapter les chemins de fichiers selon la structure réelle du projet.

---

## Phase 0 — Cadrage & schéma de base de données

```
Contexte : je développe "George", un agent d'analyse technique des marchés financiers.
Stack : Python 3.11, PostgreSQL 16 + extension TimescaleDB, Docker Compose.

Objectif de cette étape : poser les fondations du projet.

Tâches :
1. Crée un dépôt avec une structure de projet claire : /ingestion, /engine, /agents,
   /api, /web, /mobile, /infra, /tests.
2. Écris un docker-compose.yml avec : PostgreSQL+TimescaleDB, Redis, MinIO,
   Adminer pour l'administration DB.
3. Conçois le schéma SQL initial (migrations avec Alembic) pour :
   - table hypertable `prices_ohlcv` (symbol, ts, open, high, low, close, volume)
   - table `securities` (symbol, name, country, currency, sector, theme)
   - table `patterns_detected` (id, symbol, pattern_type, detected_at, confidence, context jsonb)
   - table `decisions` (id, symbol, decision_type, entry_price, take_profit, stop_loss,
     confidence, rationale text, created_at)
   - table `decision_outcomes` (decision_id, evaluated_at, result, pnl_pct)
4. Ajoute un script `seed.py` qui charge un univers de départ : les 40 valeurs du CAC 40
   (ticker, nom, secteur) dans `securities`.
5. Fournis un README expliquant comment lancer l'environnement avec `docker compose up`.

Contrainte : uniquement des outils gratuits/open source. Écris des tests basiques
(pytest) vérifiant que les migrations s'appliquent proprement sur une base vide.
```

---

## Phase 1 — Moteur quantitatif (ingestion + patterns)

```
Contexte : le schéma de base de données existe déjà (voir /ingestion/migrations).
Stack : Python, pandas, pandas-ta, yfinance, TimescaleDB.

Objectif : construire le moteur de détection de patterns techniques.

Tâches :
1. Dans /ingestion, écris un module qui télécharge l'historique OHLCV quotidien
   via yfinance pour la liste de titres en base (`securities`), avec retry et
   gestion des tickers non trouvés, et l'insère dans `prices_ohlcv`.
2. Dans /engine, implémente des fonctions de détection pour ces patterns :
   Double Bottom, Double Top, Cup & Handle, Bull Flag, Bear Flag, Ascending Triangle,
   Descending Triangle, Falling Wedge, Rising Wedge, Head & Shoulders (et inverse),
   Breakout, Breakdown. Utilise des règles géométriques sur les extrema locaux
   (scipy.signal.argrelextrema) plutôt que du deep learning à ce stade.
3. Pour chaque pattern détecté, calcule un score de confiance initial simple
   (0-100) basé sur : netteté géométrique de la figure, volume de confirmation,
   position par rapport à la tendance de fond (moyenne mobile 50/200).
4. Écris un script qui exécute la détection sur tout l'univers et insère les
   résultats dans `patterns_detected`.
5. Ajoute un notebook Jupyter de validation visuelle : afficher le graphique
   d'un titre avec le pattern détecté surligné (mplfinance).
6. Tests unitaires : génère des séries de prix synthétiques qui suivent
   exactement la géométrie de chaque pattern et vérifie qu'il est bien détecté.

Contrainte : code modulaire, chaque pattern dans sa propre fonction testable
indépendamment. Documente les paramètres géométriques (tolérances) en haut de fichier.
```

---

## Phase 2 — Mémoire historique & apprentissage continu

```
Contexte : le moteur de détection de patterns (/engine) et le stockage
(patterns_detected, decisions, decision_outcomes) existent déjà.
Stack : Python, scikit-learn, XGBoost, pandas.

Objectif : transformer le score de confiance heuristique en score appris,
et construire les paniers + George Index.

Tâches :
1. Écris un script de backtesting qui, pour chaque pattern historique détecté,
   calcule le résultat réel après 5, 10, 20 séances (rendement %, succès/échec
   selon un seuil défini).
2. Entraîne un modèle XGBoost (classification) qui prédit la probabilité de
   succès d'un pattern à partir de features : type de pattern, volume relatif,
   volatilité (ATR), position vs moyennes mobiles, secteur, contexte de marché
   (tendance de l'indice de référence).
3. Remplace le score heuristique de la Phase 1 par la probabilité prédite par
   ce modèle, en gardant la heuristique comme fallback si les données sont
   insuffisantes pour un titre donné.
4. Implémente la notion de "panier" : une table `baskets` (nom, type: pays/devise/
   secteur/thème) et une table de liaison `basket_securities`.
5. Calcule le "George Index" par panier : moyenne pondérée des scores de
   confiance des patterns actifs du panier, ajustée par le momentum et le volume
   agrégé. Documente la formule exacte dans un fichier /engine/george_index.md.
6. Ajoute un job (à lancer manuellement pour l'instant) qui réévalue les
   décisions anciennes et met à jour `decision_outcomes`.

Contrainte : sépare clairement le code d'entraînement (offline, notebook) du
code d'inférence (module Python appelable en production). Sauvegarde le modèle
entraîné avec joblib et versionne-le (nom de fichier avec date). Prévois une
table `pattern_candidates` distincte de `patterns_detected` : c'est là que
les nouvelles figures proposées par Jane, l'agent de veille méthodologique (Phase 7)
seront backtestées avant toute promotion éventuelle vers le catalogue actif.
```

---

## Phase 3 — Interface web MVP

```
Contexte : une API n'existe pas encore ; les données sont accessibles via
PostgreSQL (patterns_detected, decisions, baskets, george_index).
Stack : FastAPI (backend), React + TypeScript + Tailwind (frontend).

Objectif : premier dashboard web fonctionnel, dense et professionnel — inspiré
des plateformes de trading actives (watchlist dense, graphiques en chandeliers,
widgets tuilés), avec un élément distinctif : un bandeau où George explique ses
décisions en langage naturel.

Tâches :
1. Dans /api, crée une API FastAPI avec ces endpoints minimum :
   GET /securities, GET /securities/{symbol}/patterns, GET /baskets,
   GET /baskets/{id}/george-index, GET /decisions?status=..., GET /agents/activity.
2. Ajoute la pagination et le filtrage par panier/décision sur les endpoints
   pertinents. Documente l'API avec OpenAPI (généré automatiquement par FastAPI).
3. Dans /web, crée une application React avec une disposition dense en trois
   colonnes : navigation latérale, zone centrale, panneau de détail à droite.
4. Zone centrale — watchlist : tableau des titres suivis avec, par ligne,
   ticker, panier, mini-graphique (sparkline), pattern détecté, barre de
   confiance colorée, tag de décision (Achat/Renforcer/Surveiller/Alléger).
   Ajoute des filtres par décision.
5. Sous la watchlist, une rangée de tuiles denses : 2-3 jauges circulaires du
   George Index par panier (SVG conic-gradient ou lib de gauges), et une
   tuile de repères macro (taux, indices, devises).
6. Panneau de détail (au clic sur une ligne) : graphique en chandeliers
   (vert/rouge, pas de simple ligne) pour le titre sélectionné, avec :
   - la superposition du pattern détecté tracée sur le graphique (lignes de
     tendance/support/résistance en couleur d'accent, calculées à partir des
     extrema réels de la série) ;
   - les niveaux de take-profit (ligne verte) et stop-loss (ligne rouge)
     tracés horizontalement sur le graphique, avec le prix affiché sur le
     bord droit, plus une ligne de prix courant ;
   - le texte d'explication de George (Phase 4) ;
   - les boutons "Valider les niveaux" / "Ajuster" (jamais d'exécution
     automatique — voir Phase 6).
7. Sous le panneau de détail, un flux d'activité des sous-agents façon
   carnet d'ordres : lignes compactes avec code couleur par statut (validé /
   en attente / quarantaine) — alimenté par l'endpoint /agents/activity
   (Phase 7).
8. Bandeau bas persistant "George explique" (élément signature de
   l'interface) : affiche l'explication de la ligne sélectionnée, avec un
   champ de question libre et un bouton "commande vocale" (branché en
   Phase 8).
9. Utilise React Query pour la gestion des appels API et du cache.
10. Ajoute des tests d'intégration basiques sur l'API (pytest + httpx) et des
    tests de rendu sur les composants clés (Vitest + React Testing Library).

Contrainte : pas d'authentification à ce stade (sera ajoutée en Phase 9),
mais structure le code pour qu'elle puisse être branchée facilement ensuite.
Palette et typographie cohérentes avec l'identité déjà posée (fond marine
profond, texte clair, vert/ambre/rouge pour achat/surveiller/alléger, police
mono pour les chiffres).
```

---

## Phase 4 — Couche LLM conversationnelle

```
Contexte : l'API FastAPI et les données structurées (patterns, decisions,
george_index) existent déjà.
Stack : Python, API Mistral (« La Plateforme », gratuite avec quota — choisie pour
le MVP, sera remplacée par Claude en production pour la qualité d'explication), pgvector.

Objectif : permettre à George d'expliquer ses décisions en langage naturel.

Tâches :
1. Crée un module /agents/explainer qui, à partir d'une décision (row de la
   table `decisions` + le pattern associé + le contexte macro/micro si présent),
   génère une explication en français structurée comme : pattern détecté,
   niveau de confiance, éléments de confirmation, risques identifiés.
2. Le LLM ne doit jamais recevoir pour instruction de détecter un pattern
   lui-même : il reçoit uniquement les résultats déjà calculés par le moteur
   quantitatif (Phase 1-2) et les met en mots. Fais respecter cette séparation
   strictement dans le prompt système.
3. Ajoute un endpoint API POST /chat qui permet de poser une question libre
   ("pourquoi as-tu choisi Airbus ?") et route la question vers les données
   structurées pertinentes avant de generer la réponse (RAG simple sur les
   tables SQL, pas besoin de recherche vectorielle complexe à ce stade).
4. Indexe dans pgvector les rapports/textes longs (notes, résumés) pour
   permettre une recherche sémantique complémentaire aux requêtes SQL directes.
5. Ajoute la génération de rapports automatiques (texte) résumant l'état
   du portefeuille ou d'un panier sur demande.
6. Écris des tests qui vérifient que les réponses du LLM citent bien les
   données réelles fournies (pas d'invention de chiffres) — via des assertions
   sur la présence des valeurs numériques attendues dans la réponse.

Contrainte : prompts système versionnés dans /agents/prompts/ (fichiers texte,
pas hardcodés dans le code Python), pour pouvoir les faire évoluer sans
redéployer. Utilise ce pattern de référence pour le client Mistral (backoff
exponentiel sur le rate limit du tier gratuit, prompt système chargé depuis
un fichier, fonction d'appel isolée pour faciliter une future migration vers
Claude) :

[colle ici le contenu de mistral_client.py]
```

---

## Phase 5 — Application mobile & alertes

```
Contexte : l'API FastAPI expose déjà les décisions et patterns ; le module
explainer (Phase 4) peut générer du texte explicatif.
Stack : React Native, Firebase Cloud Messaging (notifications push, gratuit
jusqu'à un certain volume), Piper ou Coqui TTS (synthèse vocale open source).

Objectif : première version mobile avec alertes.

Tâches :
1. Crée une application React Native (Expo) avec les écrans : Accueil (résumé
   du jour), Univers, Paniers, Détail d'une décision.
2. Intègre les notifications push : lorsqu'une nouvelle décision "Achat" ou
   "Alléger" est créée côté backend, envoie une notification via un webhook
   déclenché par PostgreSQL (LISTEN/NOTIFY) ou un job qui poll les nouvelles
   lignes de `decisions`.
3. Ajoute la synthèse vocale : bouton "Écouter" sur l'écran de détail d'une
   décision qui appelle un endpoint /tts renvoyant un fichier audio généré
   via Piper/Coqui à partir du texte de l'explication (Phase 4).
4. Implémente le cache local (pas de stockage sensible) pour un affichage
   rapide hors connexion des dernières données chargées.
5. Ajoute un job planifié (Airflow ou cron simple à ce stade) qui génère
   chaque jour à 8h30 (heure de Paris) une synthèse quotidienne — résultat de
   la collecte nocturne, patterns actifs, George Index à jour, positions à
   surveiller dans la séance à venir — et l'envoie en notification push et
   en email, avec une version audio générée via TTS.
6. Tests end-to-end basiques avec Detox sur les parcours critiques (ouverture
   app, réception d'une notification simulée, lecture d'une explication).

Contrainte : respecte les guidelines d'accessibilité de base (contraste,
labels sur les boutons) dès cette version.
```

---

## Phase 6 — Gestion du risque et scénarios de sortie

```
Contexte : les décisions (table `decisions`) sont créées avec entry_price,
take_profit, stop_loss déjà en colonnes (Phase 0), mais la logique de calcul
et de suivi n'existe pas encore.
Stack : Python, le moteur de patterns existant (/engine).

Objectif : calculer et suivre les niveaux de sortie.

Tâches :
1. Pour chaque pattern détecté, calcule un objectif de gain (take-profit) dérivé
   de la mesure géométrique du pattern (ex : hauteur du mât pour un flag,
   amplitude pour un double creux) et un niveau d'invalidation (stop-loss)
   basé sur la cassure du support/résistance de la figure.
2. Ajoute ces niveaux calculés comme "proposition" dans l'API (endpoint
   POST /decisions/{id}/propose-levels) avant toute confirmation utilisateur.
3. Crée un endpoint POST /decisions/{id}/confirm qui enregistre les niveaux
   validés (éventuellement ajustés par l'utilisateur) comme définitifs.
4. Écris un job de suivi (à exécuter périodiquement) qui, pour chaque
   décision ouverte, vérifie si le cours a atteint le take-profit ou franchi
   le stop-loss, et dans ce dernier cas :
   - distingue franchissement confirmé par le volume vs. bruit normal
   (seuil configurable) ;
   - propose un scénario de sortie (totale/partielle/maintien) avec
   justification textuelle générée via le module explainer (Phase 4).
5. Enregistre chaque clôture de position dans `decision_outcomes` avec la
   cause identifiée, pour alimenter le réentraînement du modèle (Phase 2).

Contrainte : le job de suivi ne doit jamais clôturer une position
automatiquement sans qu'une "proposition de sortie" ait été créée et
consultable via l'API — cohérent avec le principe "George propose,
l'investisseur valide".
```

---

## Phase 7 — Sous-agents de collecte autonome

```
Contexte : l'architecture existante (API, base de données, explainer) est en
place. C'est l'étape la plus complexe du projet.
Stack : LangGraph ou CrewAI, Celery + Redis, Playwright/Scrapy, Apache Airflow,
pgvector, MinIO.

Objectif : construire l'orchestrateur et les sous-agents spécialisés, avec
quatre modes d'activation distincts et une validation systématique.

Tâches :
1. Dans /agents/orchestrator, implémente un orchestrateur (LangGraph) qui :
   - reçoit une "tâche de collecte" avec un type (actualités réglementaires,
     calendrier résultats, presse sectorielle, données macro, fondamentaux
     d'entreprise, veille méthodologique, synthèse de document) et un
     périmètre (symbol ou panier) ;
   - sélectionne et invoque le sous-agent correspondant ;
   - collecte le résultat structuré (texte + métadonnées : source, date,
     type) et le transmet au module de validation.
2. Implémente quatre modes d'activation distincts :
   - veille continue autonome : un scheduler qui fait tourner en permanence
     les sous-agents sur l'ensemble de l'univers suivi, y compris des valeurs
     non détenues ;
   - batch nocturne planifié (DAG Airflow) qui traite la file des
     informations manquantes identifiées pendant la journée
     (`missing_info_queue`) ;
   - collecte d'urgence déclenchable à la demande (API ou commande vocale,
     Phase 8), sans attendre le prochain batch ;
   - réaction à un manque identifié : une décision précise bloquée déclenche
     une collecte ciblée.
3. Implémente chaque sous-agent comme un module indépendant avec un périmètre
   d'écriture limité en base (chacun n'écrit que dans les colonnes/tables
   qui le concernent — voir modèle de responsabilité par sous-agent) :
   - agent actualités réglementaires (scraping de communiqués publics via
     Playwright, sources whitelistées uniquement) ;
   - agent calendrier résultats (scraping de calendriers publics d'annonces) ;
   - agent presse sectorielle et sentiment (scraping RSS/pages publiques de
     presse spécialisée) — ce sous-agent peut aussi déclencher une alerte de
     sa propre initiative dès qu'il détecte un événement significatif
     (profit warning, rupture d'approvisionnement, tension géopolitique),
     sans attendre un pattern technique ou une question posée ;
   - agent données macro (API publiques : FRED, TIC du Trésor US, banques
     centrales, INSEE/Eurostat) ;
   - agent fondamentaux d'entreprise (API SEC EDGAR, taxonomie US-GAAP,
     rate limit 10 req/s) ;
   - agent veille méthodologique, baptisé Jane (Investopedia, BabyPips et sources de
     référence pour les définitions ; TradingView pour les indicateurs et
     idées de trading communautaires ; ProRealTime et NanoTrader pour les
     méthodologies d'analyse technique active et de backtesting) — les
     candidats identifiés ici alimentent une file de "nouveaux patterns à
     évaluer", jamais ajoutés directement à la détection en production (voir
     contrainte ci-dessous). Pour cette partie de son rôle, Jane ne fonctionne
     que sur le mode veille continue autonome, en tâche de fond à faible
     priorité (queue/worker séparé, priorité basse) : elle ne doit jamais
     retarder les modes réactifs (urgence, manque identifié) ni consommer des
     ressources prioritaires. Utilise l'API Mistral (même client que la
     Phase 4) mais avec le modèle mistral-large-latest plutôt que
     mistral-small-latest : la qualité d'extraction prime ici sur la latence.
     En plus de cette veille, Jane a un second rôle, synchrone celui-là :
     avant que George publie une décision (achat/renforcer/surveiller/
     alléger), Jane relit le dossier complet (pattern, contexte macro,
     données des sous-agents) et produit une note d'analyse contradictoire
     (cohérence des signaux, éléments manquants, scénarios alternatifs) —
     implémente ça comme un second appel LLM distinct, appelé juste avant la
     génération de l'explication finale par George (Phase 4/6). Jane ne
     détecte aucun pattern et ne décide jamais : c'est George qui arbitre
     entre sa propre analyse et celle de Jane. Pour son second avis, charge
     aussi dans son prompt système un corpus de gestion de portefeuille et
     finance de marché (théorie de Markowitz/MEDAF/APT, mesures de
     performance Sharpe/Treynor/Jensen, efficience des marchés, assurance
     de portefeuille CPPI/OBPI/Stop-Loss — voir Jane_Synthese_Connaissances.md
     fourni séparément) et la méthode Fujimoto (règle mécanique de
     pyramidage à la baisse / prise de profit par paliers) comme référence
     alternative pour les niveaux de sortie du pilier 8 ;
   - agent synthèse (appelle un LLM pour résumer un document long en
     indicateurs exploitables).
4. Implémente le module de validation : recoupement multi-sources (au moins
   2 sources indépendantes concordantes avant intégration), calcul d'un score
   de fiabilité, mise en quarantaine (table `collected_info_quarantine`) en
   cas de contradiction non résolue.
5. Chaque enregistrement validé et intégré porte l'identifiant du sous-agent
   qui l'a produit (colonne `produced_by_agent`) en plus de la source externe.
6. Ajoute un tableau de bord (endpoint /agents/activity + écran web, voir
   Phase 3) listant, par sous-agent : le nombre de collectes, le taux de
   validation, le taux de mise en quarantaine — base du futur score de
   performance par sous-agent.
7. Tests : simule des sources contradictoires et vérifie que l'information est
   bien mise en quarantaine plutôt qu'intégrée ; vérifie qu'un candidat de
   Jane (l'agent "veille méthodologique") n'est jamais utilisé en détection sans
   passer par le pipeline de backtesting de la Phase 2.

Contrainte forte : le scraping ne cible que des sources publiques
explicitement whitelistées dans un fichier de configuration — jamais de
scraping de flux de marché propriétaires (cours, carnets d'ordres). Un
nouveau pattern candidat identifié par Jane doit
être backtesté sur l'historique de George (Phase 2) et n'intègre le catalogue
actif que si sa performance mesurée le justifie.
```

---

## Phase 8 — Pilotage vocal complet

```
Contexte : l'application mobile (Phase 5) a déjà la synthèse vocale en
sortie ; il manque la reconnaissance vocale en entrée et le routage des
commandes.
Stack : Whisper (auto-hébergé), FastAPI, l'orchestrateur de sous-agents
(Phase 7).

Objectif : permettre un dialogue vocal bidirectionnel complet.

Tâches :
1. Ajoute un endpoint POST /voice/transcribe qui reçoit un flux audio et
   renvoie le texte transcrit via Whisper.
2. Crée un routeur de commandes vocales qui interprète le texte transcrit et
   le dirige vers l'action appropriée : question informative (routée vers le
   module explainer/RAG), déclenchement de collecte d'urgence (routé vers
   l'orchestrateur de sous-agents), validation/ajustement d'un niveau de
   take-profit ou stop-loss (routé vers l'endpoint de confirmation de la
   Phase 6).
3. Implémente un mécanisme de confirmation explicite obligatoire avant toute
   action à conséquence financière déclenchée à la voix : la commande vocale
   génère une proposition affichée/lue à l'utilisateur, qui doit confirmer
   par une seconde commande explicite ("je confirme") avant exécution.
4. Intègre le tout dans l'app mobile : bouton micro, affichage du texte
   transcrit avant envoi (pour permettre une correction manuelle), lecture
   vocale de la réponse.
5. Tests : vérifie qu'une commande ambiguë ou mal transcrite ne déclenche
   jamais une action financière sans passer par l'étape de confirmation.

Contrainte : logue chaque commande vocale (texte transcrit + action décidée)
pour permettre un audit ultérieur en cas d'erreur de reconnaissance.
```

---

## Phase 9 — Conformité, sécurité & authentification (transverse)

```
Contexte : l'application (web + mobile + API) est fonctionnelle en interne
sans authentification.
Stack : FastAPI-Users ou Authlib, JWT, Vault (ou solution équivalente
gratuite pour la gestion de secrets en dev), PostgreSQL row-level security.

Objectif : sécuriser l'application avant toute bêta externe.

Tâches :
1. Ajoute l'authentification (email/mot de passe + MFA optionnelle) sur
   l'API avec FastAPI-Users, et protège tous les endpoints existants.
2. Ajoute la gestion des rôles (investisseur particulier, conseiller,
   administrateur) avec des permissions différenciées sur les endpoints
   sensibles (ex. déclenchement manuel d'une collecte d'urgence réservé
   à certains rôles).
3. Chiffre les données sensibles at-rest (colonnes contenant des informations
   personnelles) et impose TLS partout (Let's Encrypt).
4. Ajoute les mentions légales obligatoires dans l'app et l'API : avertissement
   "ne constitue pas un conseil en investissement personnalisé", conditions
   d'utilisation, politique de confidentialité RGPD.
5. Documente dans /docs/compliance.md le statut réglementaire visé et les
   zones grises à faire trancher par un juriste avant lancement commercial
   (ex. statut de conseiller en investissement financier en France).
6. Ajoute des tests de sécurité basiques (tentative d'accès sans token,
   tentative d'accès à un rôle non autorisé) dans la suite de tests.
7. Mets en place la gestion des logs techniques, distincte des logs d'audit
   métier déjà en base (decisions, patterns_detected, produced_by_agent,
   quarantaine — qui ne sont jamais purgés automatiquement) :
   - format structuré JSON avec un trace_id par décision ou tâche de
     sous-agent (OpenTelemetry) ;
   - agrégation via Grafana Loki + Promtail ;
   - rétention différenciée : logs techniques courants 30-90 jours, logs de
     sécurité (authentification, accès refusés) conservés plus longtemps ;
   - vérifie qu'aucun secret (mot de passe, token, clé API) n'apparaît en
     clair dans les logs, y compris dans les logs de commandes vocales
     (Phase 8).

Contrainte : ne jamais logger de mot de passe ou de token en clair ; utilise
des variables d'environnement / secrets manager, jamais de clé en dur dans
le code.
```

---

## Phase 10 — Bêta fermée & bascule vers la production

```
Contexte : toutes les briques fonctionnelles existent (Phases 0-9) en
environnement de développement avec des sources gratuites/limitées.
Stack : Kubernetes, Prometheus/Grafana, GitHub Actions, fournisseur de
données de marché sous licence (à choisir selon budget).

Objectif : préparer et exécuter la bascule vers un environnement de
production réel.

Tâches :
1. Remplace les sources de données gratuites (yfinance, API à quota) par un
   fournisseur sous licence adapté au volume cible (nombre de titres, latence
   requise). Isole ce changement derrière une interface commune
   (/ingestion/providers/) pour ne pas casser le reste du système.
2. Écris les manifests Kubernetes (ou Helm charts) pour déployer l'ensemble
   des services (API, workers Celery, Airflow, PostgreSQL/TimescaleDB géré
   ou auto-hébergé, Redis, MinIO).
3. Mets en place l'observabilité complète : dashboards Grafana pour le volume
   de sous-agents actifs, le taux de validation des collectes, la latence
   des alertes, les erreurs API.
4. Configure une pipeline CI/CD (GitHub Actions) : tests automatiques sur
   chaque pull request, déploiement automatique en environnement de
   recette, déploiement manuel validé en production.
5. Prépare un plan de bêta fermée : liste de critères de sortie (taux
   d'erreur acceptable, temps de réponse, nombre d'utilisateurs cibles),
   formulaire de retour utilisateur intégré à l'app.
6. Documente un plan de montée en charge : à partir de quel nombre de titres
   suivis et de sous-agents actifs faut-il revoir le dimensionnement de
   l'infrastructure (base de données, workers, quotas API).

Contrainte : la bascule doit être réversible (feature flag permettant de
revenir aux sources de données de la phase précédente en cas de problème).
```
