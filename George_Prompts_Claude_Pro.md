# George — Prompts pour Claude (claude.ai / Claude Pro) par étape de développement

Ce document regroupe, dans un seul fichier, un prompt par phase adapté à une utilisation dans **claude.ai (Claude Pro)** plutôt que dans Claude Code. Différence clé : Claude Pro en chat n'a pas d'accès à un système de fichiers ni d'exécution — il rédige le code en réponse, à copier-coller soi-même. Chaque prompt demande donc explicitement le contenu complet de chaque fichier, plus les instructions manuelles pour l'installer et le lancer.

**Mode d'emploi** : pour chaque phase, colle le prompt correspondant dans une conversation claude.ai. Si le projet a déjà avancé, colle aussi en début de message le code des fichiers les plus pertinents de la phase précédente (Claude Pro ne conserve pas de mémoire du code entre conversations, contrairement à Claude Code qui lit le dépôt directement).

---

## Phase 0 — Cadrage & schéma de base de données

```
Je développe "George", un agent d'analyse technique des marchés financiers.
Stack : Python 3.11, PostgreSQL 16 + extension TimescaleDB, Docker Compose.

Objectif : poser les fondations du projet.

Merci de me fournir, avec le contenu complet de chaque fichier (pas de résumé,
le code entier prêt à copier-coller) :
1. Une arborescence de projet claire : /ingestion, /engine, /agents, /api,
   /web, /mobile, /infra, /tests — donne la liste des dossiers et leur rôle.
2. Un fichier docker-compose.yml avec : PostgreSQL+TimescaleDB, Redis, MinIO,
   Adminer pour l'administration DB.
3. Le schéma SQL initial (migrations Alembic) pour :
   - table hypertable `prices_ohlcv` (symbol, ts, open, high, low, close, volume)
   - table `securities` (symbol, name, country, currency, sector, theme)
   - table `patterns_detected` (id, symbol, pattern_type, detected_at, confidence, context jsonb)
   - table `decisions` (id, symbol, decision_type, entry_price, take_profit, stop_loss,
     confidence, rationale text, created_at)
   - table `decision_outcomes` (decision_id, evaluated_at, result, pnl_pct)
4. Un script `seed.py` qui charge un univers de départ : les 40 valeurs du
   CAC 40 (ticker, nom, secteur) dans `securities`.
5. Un README expliquant comment lancer l'environnement avec `docker compose up`,
   étape par étape, en supposant que je n'ai jamais utilisé Alembic.

Contrainte : uniquement des outils gratuits/open source. Ajoute aussi un
petit test pytest que je pourrai lancer moi-même pour vérifier que les
migrations s'appliquent sur une base vide, avec les instructions exactes
pour l'exécuter.
```

---

## Phase 1 — Moteur quantitatif (ingestion + patterns)

```
Voici le schéma de base de données déjà en place [colle ici le schéma SQL de
la Phase 0]. Stack : Python, pandas, pandas-ta, yfinance, TimescaleDB.

Objectif : construire le moteur de détection de patterns techniques.

Merci de me fournir le code complet de chaque fichier pour :
1. Un module d'ingestion qui télécharge l'historique OHLCV quotidien via
   yfinance pour une liste de titres, avec retry et gestion des tickers non
   trouvés, prêt à insérer dans `prices_ohlcv`.
2. Des fonctions de détection pour ces patterns : Double Bottom, Double Top,
   Cup & Handle, Bull Flag, Bear Flag, Ascending Triangle, Descending
   Triangle, Falling Wedge, Rising Wedge, Head & Shoulders (et inverse),
   Breakout, Breakdown — basées sur des règles géométriques sur les extrema
   locaux (scipy.signal.argrelextrema), pas du deep learning à ce stade.
3. Pour chaque pattern détecté, un score de confiance initial simple (0-100)
   basé sur : netteté géométrique, volume de confirmation, position par
   rapport aux moyennes mobiles 50/200.
4. Un script autonome qui exécute la détection sur une liste de titres et
   affiche les résultats.
5. Un exemple de code (mplfinance) pour visualiser un graphique avec un
   pattern détecté surligné, que je puisse exécuter dans un notebook.
6. Des tests unitaires avec des séries de prix synthétiques suivant
   exactement la géométrie de chaque pattern.

Contrainte : code modulaire, un fichier ou une fonction par pattern,
testable indépendamment. Documente les paramètres géométriques (tolérances)
en commentaire en haut de chaque fonction. Donne-moi aussi les commandes
pip install nécessaires.
```

---

## Phase 2 — Mémoire historique & apprentissage continu

```
Voici le moteur de détection de patterns déjà écrit [colle ici les fonctions
de détection de la Phase 1]. Stack : Python, scikit-learn, XGBoost, pandas.

Objectif : transformer le score de confiance heuristique en score appris,
et construire les paniers + George Index.

Merci de me fournir le code complet pour :
1. Un script de backtesting qui, pour chaque pattern détecté sur un
   historique donné, calcule le résultat réel après 5, 10, 20 séances
   (rendement %, succès/échec selon un seuil que je pourrai régler).
2. L'entraînement d'un modèle XGBoost qui prédit la probabilité de succès
   d'un pattern à partir de features : type de pattern, volume relatif,
   volatilité (ATR), position vs moyennes mobiles, secteur, tendance de
   l'indice de référence. Explique-moi comment interpréter le résultat.
3. Le remplacement du score heuristique par cette probabilité prédite, avec
   un fallback sur l'heuristique si les données sont insuffisantes.
4. Le schéma SQL et la logique pour la notion de "panier" (table `baskets`
   pays/devise/secteur/thème + table de liaison `basket_securities`).
5. Le calcul du "George Index" par panier (moyenne pondérée des scores de
   confiance, ajustée par momentum et volume agrégé) — donne-moi la formule
   exacte et le code, dans un format que je peux documenter séparément.
6. Un script qui réévalue les anciennes décisions et met à jour leurs
   résultats.
7. Le schéma d'une table `pattern_candidates`, distincte de
   `patterns_detected` : c'est là que j'intégrerai plus tard les nouvelles
   figures identifiées par une veille externe (Investopedia, TradingView,
   ProRealTime, NanoTrader), pour les backtester avant toute promotion.

Contrainte : sépare clairement le code d'entraînement (offline) du code
d'inférence (utilisable en production). Montre-moi comment sauvegarder et
versionner le modèle avec joblib.
```

---

## Phase 3 — Interface web MVP

```
Voici les endpoints de données disponibles [décris ou colle ici le schéma
des tables patterns_detected, decisions, baskets, george_index].
Stack : FastAPI (backend), React + TypeScript + Tailwind (frontend).

Objectif : un dashboard web dense et professionnel, inspiré des plateformes
de trading actives (watchlist dense, graphiques en chandeliers, widgets
tuilés), avec un élément distinctif : un bandeau où George explique ses
décisions en langage naturel.

Merci de me fournir le code complet pour :
1. Une API FastAPI avec ces endpoints minimum : GET /securities,
   GET /securities/{symbol}/patterns, GET /baskets,
   GET /baskets/{id}/george-index, GET /decisions?status=...,
   GET /agents/activity. Ajoute pagination et filtres.
2. Une application React avec une disposition en trois colonnes :
   navigation latérale, zone centrale, panneau de détail à droite.
3. La zone centrale — watchlist : tableau des titres avec ticker, panier,
   mini-graphique (sparkline SVG), pattern détecté, barre de confiance
   colorée, tag de décision (Achat/Renforcer/Surveiller/Alléger), avec
   filtres.
4. Sous la watchlist, une rangée de tuiles : 2-3 jauges circulaires du
   George Index par panier (SVG conic-gradient, pas de librairie externe
   nécessaire) et une tuile de repères macro.
5. Le panneau de détail (au clic sur une ligne) : un graphique en
   chandeliers (vert/rouge, en SVG pur ou avec une lib légère) avec :
   - la superposition du pattern détecté (lignes calculées à partir des
     extrema réels de la série, pas juste décoratives) ;
   - les niveaux de take-profit (ligne verte) et stop-loss (ligne rouge)
     tracés horizontalement avec le prix affiché sur le bord droit, plus
     une ligne de prix courant ;
   - le texte d'explication de George ;
   - deux boutons "Valider les niveaux" / "Ajuster" (jamais d'exécution
     automatique d'ordre).
6. Sous le panneau de détail, un flux d'activité des sous-agents façon
   carnet d'ordres, avec code couleur par statut (validé / en attente /
   quarantaine).
7. Un bandeau bas persistant "George explique" avec un champ de question
   libre et un bouton "commande vocale" (non branché à ce stade).

Contrainte : palette fond marine profond, texte clair, vert/ambre/rouge
pour achat/surveiller/alléger, police mono pour les chiffres. Donne-moi le
code en un minimum de fichiers pour que je puisse le tester facilement en
local (Vite suffit, pas besoin d'un gros build).
```

---

## Phase 4 — Couche LLM conversationnelle

```
Voici la structure des données disponibles (patterns, decisions,
george_index) [décris-la ou colle le schéma]. Stack : Python, API Mistral
(« La Plateforme », gratuite avec quota), pgvector.

Objectif : permettre à George d'expliquer ses décisions en langage naturel.

Merci de me fournir le code complet pour :
1. Une fonction qui, à partir d'une décision (pattern associé + contexte
   macro/micro si disponible), génère une explication en français
   structurée : pattern détecté, niveau de confiance, éléments de
   confirmation, risques identifiés. Donne-moi le prompt système exact à
   utiliser, dans un fichier séparé du code Python.
2. Explique comment garantir que le LLM ne reçoit jamais pour instruction
   de détecter un pattern lui-même : il ne fait que mettre en mots des
   résultats déjà calculés. Montre-moi comment structurer l'appel API pour
   que ce soit impossible à contourner.
3. Un exemple d'endpoint qui reçoit une question libre ("pourquoi as-tu
   choisi Airbus ?") et route la question vers les données structurées
   pertinentes avant de générer la réponse (RAG simple sur des requêtes
   SQL, pas besoin de recherche vectorielle complexe ici).
4. Un exemple d'indexation dans pgvector pour des textes longs (notes,
   résumés), utile en complément des requêtes SQL directes.
5. Un exemple de génération de rapport automatique résumant l'état d'un
   portefeuille ou d'un panier.
6. Une méthode de test simple pour vérifier que les réponses du LLM citent
   bien les chiffres réels fournis, sans en inventer.

Contrainte : les prompts système doivent être dans des fichiers texte
séparés du code Python, pour pouvoir les modifier sans redéployer. Voici un
exemple de client Mistral déjà fonctionnel dont tu peux t'inspirer (backoff
sur le rate limit, prompt système chargé depuis un fichier séparé) :

[colle ici le contenu de mistral_client.py]
```

---

## Phase 5 — Application mobile & alertes

```
Voici les endpoints disponibles (decisions, patterns) et la fonction
d'explication déjà écrite [colle-la]. Stack : React Native (Expo), Firebase
Cloud Messaging, Piper ou Coqui TTS (synthèse vocale open source).

Objectif : une première version mobile avec alertes et synthèse quotidienne.

Merci de me fournir le code complet pour :
1. Une application React Native (Expo) avec les écrans : Accueil (résumé du
   jour), Univers, Paniers, Détail d'une décision.
2. La logique de notification push : quand une nouvelle décision "Achat" ou
   "Alléger" apparaît côté backend, envoyer une notification (explique-moi
   le principe avec Firebase Cloud Messaging, avec un exemple minimal).
3. Un bouton "Écouter" sur l'écran de détail qui appelle un endpoint /tts
   renvoyant un fichier audio généré via Piper/Coqui à partir du texte
   d'explication.
4. Un exemple de cache local simple (pas de données sensibles) pour un
   affichage rapide hors connexion.
5. La logique d'un job planifié qui génère chaque jour à 8h30 (heure de
   Paris) une synthèse quotidienne — résultat de la collecte nocturne,
   patterns actifs, George Index à jour, positions à surveiller — envoyée
   en notification, email et version audio. Donne-moi un exemple avec un
   cron simple, j'automatiserai avec Airflow plus tard si besoin.

Contrainte : respecte les bases d'accessibilité (contraste suffisant,
labels sur les boutons). Explique-moi comment lancer l'app en local avec
Expo, en supposant que je découvre React Native.
```

---

## Phase 6 — Gestion du risque et scénarios de sortie

```
Voici la structure de la table `decisions` (avec entry_price, take_profit,
stop_loss déjà en colonnes) [colle le schéma]. Stack : Python, le moteur de
patterns déjà écrit [colle les fonctions clés].

Objectif : calculer et suivre les niveaux de sortie.

Merci de me fournir le code complet pour :
1. Le calcul, pour chaque pattern détecté, d'un objectif de gain
   (take-profit) dérivé de la mesure géométrique du pattern (hauteur du mât
   pour un flag, amplitude pour un double creux, etc.) et d'un niveau
   d'invalidation (stop-loss) basé sur la cassure du support/résistance.
2. Un exemple d'endpoint qui propose ces niveaux calculés (jamais appliqués
   directement) et un second endpoint qui enregistre les niveaux validés
   (éventuellement ajustés) une fois confirmés par l'utilisateur.
3. La logique d'un job de suivi qui, pour chaque décision ouverte, vérifie
   si le cours a atteint le take-profit ou franchi le stop-loss, et dans ce
   dernier cas :
   - distingue un franchissement confirmé par le volume d'un simple bruit
     (donne-moi un seuil de départ raisonnable, ajustable) ;
   - propose un scénario de sortie (totale / partielle / maintien) avec une
     justification textuelle (réutilise la fonction d'explication de la
     Phase 4).
4. La mise à jour de `decision_outcomes` avec la cause identifiée de
   clôture, pour pouvoir réentraîner le modèle plus tard.

Contrainte importante à respecter dans le code : aucune position ne doit
jamais être clôturée automatiquement sans qu'une "proposition de sortie"
ait été créée et consultable — George propose, l'investisseur valide,
jamais l'inverse.
```

---

## Phase 7 — Sous-agents de collecte autonome

```
Voici l'architecture existante (API, base de données, fonction
d'explication) [décris-la brièvement]. C'est l'étape la plus complexe du
projet — n'hésite pas à me la découper en plusieurs sous-réponses si le
code est long. Stack : LangGraph ou CrewAI, Playwright/Scrapy, pgvector.

Objectif : un orchestrateur et des sous-agents spécialisés, avec quatre
modes d'activation et une validation systématique.

Merci de me fournir le code complet, ou de le découper clairement, pour :
1. Un orchestrateur (LangGraph) qui reçoit une tâche de collecte typée
   (actualités réglementaires, calendrier résultats, presse sectorielle,
   données macro, fondamentaux d'entreprise, veille méthodologique,
   synthèse de document), sélectionne le sous-agent adapté, et transmet le
   résultat structuré (texte + source + date + type) au module de
   validation.
2. Une explication claire des quatre modes d'activation à implémenter :
   veille continue autonome (sur tout l'univers, même les valeurs non
   détenues), batch nocturne planifié, collecte d'urgence à la demande,
   réaction à un manque identifié — avec un exemple de code pour chacun.
3. Le code de chaque sous-agent comme module indépendant, avec un périmètre
   d'écriture limité en base (chacun n'écrit que ce qui le concerne) :
   - agent actualités réglementaires (scraping de sources publiques
     whitelistées uniquement) ;
   - agent calendrier résultats ;
   - agent presse sectorielle et sentiment — précise-moi comment ce
     sous-agent peut aussi déclencher une alerte de sa propre initiative
     dès qu'il détecte un événement significatif, sans attendre un pattern
     technique ;
   - agent données macro (FRED, TIC du Trésor US, INSEE/Eurostat) ;
   - agent fondamentaux d'entreprise (SEC EDGAR, en respectant la limite de
     10 requêtes/seconde et le User-Agent obligatoire) ;
   - agent veille méthodologique, baptisé Jane (Investopedia et BabyPips pour les
     définitions, TradingView pour les indicateurs communautaires,
     ProRealTime et NanoTrader pour les méthodologies de backtesting) —
     précise bien que les candidats identifiés par Jane doivent être backtestés
     avant toute utilisation réelle, et que cette partie de son rôle tourne
     uniquement en tâche de fond à faible priorité, sans jamais retarder les
     collectes réactives (urgence, manque identifié). Utilise l'API Mistral
     (même principe que la Phase 4) avec le modèle mistral-large-latest
     plutôt que le modèle rapide utilisé ailleurs, car la qualité
     d'extraction prime ici sur la vitesse. Jane a aussi un second rôle,
     synchrone : avant que George publie une décision, elle relit le dossier
     complet et produit une note d'analyse contradictoire (cohérence des
     signaux macro/micro/techniques, éléments manquants, scénarios
     alternatifs) — donne-moi un exemple de fonction séparée pour ce second
     appel LLM, appelé juste avant la génération de l'explication finale.
     Jane ne détecte aucun pattern et ne décide jamais : c'est George qui
     arbitre entre sa propre analyse et celle de Jane. Pour ce second avis,
     inclus dans son prompt système un corpus de gestion de portefeuille et
     finance de marché (Markowitz/MEDAF/APT, mesures de performance
     Sharpe/Treynor/Jensen, efficience des marchés, assurance de
     portefeuille CPPI/OBPI/Stop-Loss — je te fournirai le contenu de
     Jane_Synthese_Connaissances.md à coller si besoin) ainsi que la méthode
     Fujimoto (règle mécanique de pyramidage/prise de profit par paliers)
     comme référence alternative pour les niveaux de sortie ;
   - agent synthèse (résumé de documents longs via un LLM).
4. Le module de validation : recoupement d'au moins 2 sources indépendantes,
   score de fiabilité, mise en quarantaine en cas de contradiction non
   résolue.
5. Le principe pour tracer, sur chaque donnée intégrée, quel sous-agent l'a
   produite (en plus de la source externe).
6. Un exemple de tests qui vérifient que des sources contradictoires
   aboutissent bien à une mise en quarantaine plutôt qu'à une intégration.

Contrainte forte à respecter dans tout le code généré : le scraping ne
cible que des sources publiques explicitement whitelistées — jamais de
scraping de flux de marché propriétaires (cours, carnets d'ordres).
```

---

## Phase 8 — Pilotage vocal complet

```
Voici l'API existante et l'orchestrateur de sous-agents [décris-les
brièvement]. Stack : Whisper (auto-hébergé), FastAPI.

Objectif : un dialogue vocal bidirectionnel complet.

Merci de me fournir le code complet pour :
1. Un endpoint qui reçoit un flux audio et renvoie le texte transcrit via
   Whisper.
2. Un routeur de commandes vocales qui interprète le texte transcrit et le
   dirige vers l'action appropriée : question informative, déclenchement
   de collecte d'urgence, ou validation/ajustement d'un niveau de
   take-profit/stop-loss.
3. Un mécanisme de confirmation explicite obligatoire avant toute action à
   conséquence financière déclenchée à la voix : la commande génère une
   proposition affichée/lue, qui doit être confirmée par une seconde
   commande explicite ("je confirme") avant toute exécution. Insiste sur ce
   point dans le code, c'est la contrainte la plus importante de cette
   phase.
4. Un exemple d'intégration côté app mobile : bouton micro, affichage du
   texte transcrit avant envoi (pour correction manuelle), lecture vocale
   de la réponse.
5. Un exemple de test qui vérifie qu'une commande ambiguë ou mal transcrite
   ne déclenche jamais une action financière sans passer par la
   confirmation.

Contrainte : chaque commande vocale (texte transcrit + action décidée) doit
être loguée pour permettre un audit en cas d'erreur de reconnaissance —
montre-moi comment structurer ce log.
```

---

## Phase 9 — Conformité, sécurité, authentification & logs (transverse)

```
Voici l'application existante (web + mobile + API), fonctionnelle en
interne sans authentification [décris-la]. Stack : FastAPI-Users ou
Authlib, JWT.

Objectif : sécuriser l'application avant toute bêta externe.

Merci de me fournir le code complet et les explications pour :
1. L'authentification (email/mot de passe + MFA optionnelle) sur l'API,
   protégeant tous les endpoints existants.
2. La gestion des rôles (investisseur particulier, conseiller,
   administrateur) avec des permissions différenciées sur les endpoints
   sensibles.
3. Le chiffrement des données sensibles at-rest et l'usage de TLS partout.
4. Les mentions légales à intégrer dans l'app et l'API (avertissement "ne
   constitue pas un conseil en investissement personnalisé", RGPD) — donne
   des exemples de formulation en français.
5. Une liste des zones grises réglementaires à faire trancher par un
   juriste avant tout lancement commercial (ex. statut de conseiller en
   investissement financier en France) — je m'en servirai comme check-list,
   pas comme avis juridique définitif.
6. Des exemples de tests de sécurité basiques (accès sans token, accès à un
   rôle non autorisé).
7. La distinction et la mise en place de deux types de logs :
   - logs d'audit métier (décisions, patterns, quel sous-agent a produit
     quelle donnée, quarantaine) — à garder en base, jamais purgés
     automatiquement ;
   - logs techniques (format JSON structuré avec un identifiant de trace,
     agrégés via Grafana Loki + Promtail, rétention 30-90 jours sauf les
     logs de sécurité conservés plus longtemps).
   Vérifie explicitement dans tes exemples qu'aucun secret (mot de passe,
   token, clé API) n'apparaît jamais en clair dans un log.

Contrainte : utilise des variables d'environnement / un secrets manager,
jamais de clé en dur dans le code que tu me fournis.
```

---

## Phase 10 — Bêta fermée & bascule vers la production

```
Toutes les briques fonctionnelles existent en développement, avec des
sources de données gratuites/limitées [décris rapidement l'état du
projet]. Stack cible : Kubernetes, Prometheus/Grafana, GitHub Actions, un
fournisseur de données de marché sous licence.

Objectif : préparer la bascule vers un environnement de production réel.

Merci de m'aider avec :
1. Comment isoler le changement de fournisseur de données (passer de
   yfinance à un fournisseur sous licence) derrière une interface commune,
   pour ne pas casser le reste du système — donne-moi un exemple de code.
2. Un exemple de manifests Kubernetes (ou Helm chart) pour déployer les
   services principaux (API, workers, base de données, cache, stockage
   objet).
3. Une liste des métriques à suivre dans Grafana pour ce projet
   spécifiquement (volume de sous-agents actifs, taux de validation des
   collectes, latence des alertes, erreurs API).
4. Un exemple de pipeline CI/CD GitHub Actions : tests automatiques sur
   chaque pull request, déploiement en recette, déploiement manuel validé
   en production.
5. Une check-list pour préparer une bêta fermée : critères de sortie (taux
   d'erreur acceptable, temps de réponse, nombre d'utilisateurs cibles),
   et un exemple de formulaire de retour utilisateur simple à intégrer.
6. Des repères pour savoir, en fonction du nombre de titres suivis et de
   sous-agents actifs, quand il devient nécessaire de revoir le
   dimensionnement de l'infrastructure.

Contrainte : la bascule doit rester réversible — explique-moi comment
prévoir un feature flag qui permette de revenir aux sources de données
précédentes en cas de problème.
```
