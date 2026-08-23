# George — Synthèse de connaissances : images de stratégies (`stratégies_images/` + galerie photo personnelle)

Document de référence consolidant l'apport de deux lots d'images pour l'agent George : catalogue de concepts/patterns (candidats pour de futurs détecteurs ou pour enrichir le contexte fourni aux LLM), recoupement avec les détecteurs existants (`engine/patterns/`). Suit le même esprit que `George_AnalyseTechnique_Kabbaj_Synthese.md` : **synthèse de connaissances, pas un résumé d'images**.

- **§0-4 : premier lot**, 16 images de `stratégies_images/` — les 35 concepts candidats identifiés ont depuis été implémentés (voir §4).
- **§5 : second lot**, 22 diagrammes d'une galerie photo personnelle (2026-08-23), analysés directement par un agent multimodal (pas via l'API vision Mistral — voir `agents/jane_veille.py`) et déjà versés dans `jane_knowledge` (RAG de Jane, voir `data/jane_diagrammes/import_2026-08-23.json`) plutôt que documentés seulement ici. Aucun des nouveaux candidats de ce second lot n'est implémenté à ce jour (voir §5.4) — contrairement au premier lot.

---

## 0. Source

Contrairement à `George_AnalyseTechnique_Kabbaj_Synthese.md` (un livre unique, référencé et daté), les 16 images de `stratégies_images/` sont des captures d'écran hétérogènes issues de réseaux sociaux (Instagram/Facebook/TikTok-style), de comptes différents : **MarketSniperR** (notebook manuscrit, image 02), **Before Noise** (images 04-10, 12), **TradingMafia** (image 13), et des comptes non identifiés ou génériques pour les cheat sheets (images 01, 03, 11, 14, 15, 16). Au moins un compte source affiche explicitement le tag **« Contenu IA »** — à traiter comme un signal de prudence : ces images sont du matériel de vulgarisation grand public, pas une source académique ou professionnelle vérifiée comme l'était le livre de Kabbaj. Plusieurs libellés sont visiblement mal transcrits ou incohérents (voir §3) ; ne pas les prendre au pied de la lettre sans validation croisée.

Voir `stratégies_images/README.md` pour la liste complète des 16 fichiers avec description individuelle.

---

## 1. Concepts **absents des 25 détecteurs de George** — candidats pour de futurs détecteurs

### 1.1 Smart Money Concepts / ICT — famille entièrement absente chez George
Le groupe de concepts le plus significatif des images (04-10, 12, 14) appartient à l'école dite « ICT » / Smart Money Concepts, distincte de l'analyse technique classique déjà couverte par George (Kabbaj, `engine/patterns/`). Aucun équivalent actuel dans le code.

| Concept | Description géométrique | Usage |
|---|---|---|
| **Fair Value Gap (FVG)** | Écart de prix laissé par 3 bougies consécutives : le plus bas de la 1ère bougie et le plus haut de la 3ème ne se chevauchent pas, laissant un « vide » dans la 2ème bougie | Le prix revient généralement combler ce vide avant de poursuivre la tendance (image 05) — utilisé comme zone d'entrée sur retracement |
| **Breakaway Gap (BAG)** | Variante du FVG où la 3ème bougie dépasse nettement le plus haut de la 2ème (pas seulement de la 1ère) | Signal de forte conviction directionnelle (image 09) ; distinction FVG/BAG illustrée explicitement (images 07, 10) mais la différence géométrique précise entre les deux n'est pas totalement sans ambiguïté sur les captures — à vérifier contre une source ICT primaire avant implémentation |
| **Order Block (OB)** | Zone de consolidation juste avant un mouvement impulsif fort (dernière bougie/zone avant le déséquilibre) — un OB « demande » précède une hausse, un OB « offre » précède une baisse (image 12) | Zone de retest attendue ; un retour dans l'OB suivi d'un rejet confirme la continuation, un retour qui *dépasse* l'OB signale un échec (« OB Fail », image 12) |
| **BOS (Break of Structure)** | Cassure d'un plus haut/bas significatif confirmant un changement ou une continuation de structure de marché | Sert de point de départ pour identifier la zone de demande/offre qui a produit le mouvement (image 14) |
| **Retest de zone de demande — 3 variantes** | (a) pattern de continuation en canal après le retour sur la zone, (b) consolidation latérale sur la zone, (c) prise de liquidité (« buyside liquidity », balayage d'un PDL — *Previous Day Low*) avant le rebond réel | Trois façons dont un retest peut se comporter avant confirmation (image 14) |

**Recommandation** : ces concepts sont d'une nature différente des 25 détecteurs actuels — ils ne décrivent pas une géométrie de prix fixe (comme un Double Top) mais une **relation entre trois bougies consécutives** (FVG/BAG) ou une **zone dynamique liée à un point de structure** (Order Block). Implémentables en théorie (le FVG en particulier a une définition géométrique simple et objective : `low[t-2] > high[t]` ou l'inverse), mais nécessiteraient une définition de référence plus rigoureuse qu'une capture de réseau social avant de coder quoi que ce soit — voir §3.

### 1.2 Figures chartistes classiques non couvertes
La cheat sheet complète (image 03) et le tableau à 12 figures (image 13) recoupent en grande partie les 13 détecteurs déjà en place, mais ajoutent :

| Figure | Statut chez George |
|---|---|
| Triple Top / Triple Bottom | Absent — extension naturelle de Double Top/Bottom (une troisième touche du niveau plutôt que deux) |
| Rounding Top / Rounding Bottom | Absent — proche de Cup & Handle mais sans la « anse » (handle) finale |
| Symmetrical Triangle | Absent — George a Ascending/Descending Triangle mais pas la variante à deux droites convergentes (une baissière, une haussière) |
| Rectangle (Range) | Absent — canal horizontal borné support/résistance, cassure possible dans les deux sens |
| Pennant | Absent — proche d'un petit triangle symétrique après un mouvement impulsif (flagpole), distinct du Bull/Bear Flag (canal parallèle plutôt que convergent) |
| Diamond | Absent — élargissement puis resserrement de la volatilité, rare |

### 1.3 Figures en bougies japonaises non couvertes
George a déjà 12 détecteurs de bougies (§ Kabbaj synthesis). Les images en ajoutent plusieurs, de fiabilité terminologique inégale (voir §3 pour les libellés douteux) :

| Figure | Description | Fiabilité de la source |
|---|---|---|
| Bullish/Bearish Harami | Petite bougie à l'intérieur du corps de la précédente, de couleur opposée | Terme standard, bien identifié (image 01) |
| Three White Soldiers / Three Black Crows | Trois bougies consécutives de même couleur, progressant régulièrement | Termes standards (images 01, 16) |
| Bullish/Bearish Kicker | Gap directionnel fort après une bougie de couleur opposée, sans mèche de chevauchement | Terme standard (images 01, 16) |
| Dragonfly Doji | Doji avec longue mèche basse, quasi pas de mèche haute (le corps est en haut du range) | Variante spécifique du Doji déjà couvert plus génériquement chez George (image 01) |
| Marubozu | Bougie « pleine », sans mèche (ouverture = plus bas, clôture = plus haut ou l'inverse) | Terme standard (image 15) |
| Pin Bar (bullish/bearish) | Petit corps, longue mèche à l'opposé de la direction du signal | Conceptuellement très proche de Hammer/Shooting Star déjà implémentés — probablement une simple synonymie plutôt qu'une figure distincte (image 03, 15) |
| Inside Bar / Outside Bar | Bougie entièrement contenue dans le range de la précédente (Inside) ou l'englobant (Outside) | Termes standards, absents chez George (image 03) |

### 1.4 Indicateurs / signaux non couverts
| Concept | Description |
|---|---|
| Golden Cross / Death Cross | Croisement SMA50/SMA200 — George calcule déjà `position_vs_moving_averages` (`engine/features.py`) mais ne détecte pas le croisement lui-même comme événement (image 03) |
| Volume Breakout / Volume Dry Up / Volume Climax | Patterns basés uniquement sur le volume (accélération, épuisement, pic) — George a `volume_confirmation` comme facteur de confiance mais pas de détecteur dédié au volume seul (image 03) |
| Fibonacci Retracement Levels | Déjà noté comme absent dans `George_AnalyseTechnique_Kabbaj_Synthese.md` §2.3 — confirmé à nouveau ici (image 03), aucun changement de statut |

---

## 2. Concepts qui **se recoupent** avec l'existant — pas de nouveauté

Les images suivantes illustrent des figures déjà entièrement couvertes par les 25 détecteurs de George, sans variante notable : Double Top, Double Bottom, Head & Shoulders, Inverse Head & Shoulders, Ascending/Descending Triangle, Rising/Falling Wedge, Bull/Bear Flag, Bullish/Bearish Engulfing, Morning Star, Hammer, Inverted Hammer, Piercing Line (images 01, 02, 03, 13, 15). Le concept de **retest après breakout** (image 02, notebook MarketSniperR) est une reformulation en langage courant de ce que `engine/propose_decisions.py`/`monitor_decisions.py` gèrent déjà via les niveaux de take-profit/stop-loss — pas un nouveau pattern, mais une bonne illustration pédagogique du raisonnement déjà encodé.

---

## 3. Réserves sur la qualité de la source — à ne pas ignorer avant tout développement

Contrairement au livre de Kabbaj (édité, daté, vérifiable), ces images sont des captures de réseaux sociaux dont plusieurs libellés sont probablement corrompus par une transcription automatique ou par la qualité éditoriale d'origine :

- Image 15 : « AMI CONFIRMATION » et « INVESTED HUNLER CONFIRMATION » ne sont pas des termes reconnus de l'analyse technique — la seconde est presque certainement une déformation de « Inverted Hammer », déjà couvert par George sous son vrai nom.
- Image 16 : « Dock Wave », « TheFich », « Ticksban », « Docking Pattern » ne correspondent à aucune terminologie standard identifiable — à ignorer plutôt qu'à interpréter. Le tableau associe par ailleurs des figures sans lien logique évident (ex. « Wolfe Wave + Hammer = Wolfe ») et note des scores en étoiles sans méthodologie explicite — à traiter comme du contenu de vulgarisation à faible valeur ajoutée, pas comme une source de règles de détection.
- La distinction géométrique exacte FVG vs BAG (images 07, 10) reste floue sur la seule base des captures — les deux diagrammes ne sont pas identiques entre eux dans le tracé du rectangle, ce qui suggère une incohérence entre les deux sources plutôt qu'une nuance intentionnelle.

**Conclusion pratique** : ce lot d'images est utile pour repérer des *catégories* de concepts à explorer (ICT/Smart Money Concepts en particulier, absent à 100% chez George), mais ne doit pas servir de spécification géométrique directe pour un futur détecteur — contrairement à Kabbaj, dont les formules et exemples chiffrés étaient directement exploitables. Toute implémentation future des concepts du §1 nécessiterait une définition de référence plus rigoureuse (ex. documentation ICT primaire pour FVG/Order Block, ou tout simplement la définition mathématique la plus communément admise) avant d'écrire un détecteur.

---

## 4. Statut : implémenté

**Mise à jour** : sur demande explicite de l'utilisateur, les 35 concepts du §1 ont été implémentés — voir CLAUDE.md § « 35 new pattern detectors from George_Strategies_Images_Synthese.md » pour le détail complet. Résumé :

- **§1.1 Smart Money Concepts** : Fair Value Gap, Order Block et Break of Structure implémentés selon leur définition standard/primaire (pas la géométrie ambiguë des captures) — `engine/patterns/smart_money.py`. Breakaway Gap implémenté avec un choix délibéré et documenté (définition classique pré-ICT, distincte du FVG) vu l'incohérence entre les deux captures sources (§3). Les 3 variantes de retest de zone de demande (§1.1, dernière ligne) n'ont **pas** été implémentées comme détecteurs séparés — trop qualitatives pour une géométrie objective sans référence primaire.
- **§1.2 Figures chartistes classiques** : Triple Top/Bottom, Rounding Top/Bottom, Symmetrical Triangle, Rectangle, Pennant implémentés. Diamond implémenté avec une simplification assumée (amplitude barre-à-barre plutôt que structure de swings — voir CLAUDE.md pour le détail).
- **§1.3 Bougies japonaises** : Harami, Three White Soldiers/Three Black Crows, Kicker, Dragonfly Doji, Marubozu, Inside/Outside Bar implémentés. Pin Bar **non** implémenté séparément, confirmé par la revue comme une simple synonymie de Hammer/Shooting Star déjà couverts (comme pressenti au §1.3).
- **§1.4 Indicateurs/signaux** : Golden Cross/Death Cross implémentés (`engine/patterns/crossover.py`, un événement de croisement, architecturalement distinct des détecteurs de géométrie de bougies). Volume Breakout/Dry Up/Climax **non** implémentés — le document ne fournissait aucun critère chiffré exploitable (contrairement à Kabbaj), et aucune définition de référence externe n'a été demandée pour ce lot. Fibonacci reste absent (déjà noté comme hors-scope de ce document au §1.4).
- **§3 réserves sur la qualité de la source** : les libellés reconnus comme bidons ("Dock Wave", "Ticksban", "AMI CONFIRMATION"...) n'ont, sans surprise, donné lieu à aucun développement.

Une vraie erreur de définition géométrique (Three White Soldiers/Three Black Crows ne vérifiaient pas réellement un "long corps", le cœur du nom de la figure) a été trouvée par une revue indépendante avant d'être mergée — voir CLAUDE.md pour le détail. Ce document garde son statut de référence pour comprendre *pourquoi* chaque choix d'implémentation a été fait ; le comportement réel du code fait foi en cas de divergence future.

---

## 5. Second lot — galerie photo personnelle, 22 diagrammes (2026-08-23)

### 5.0 Source

25 images fournies directement par l'utilisateur (galerie photo de son smartphone), lues par un agent multimodal en conversation (pas via l'API vision Mistral, faute de clé disponible dans la session où le lot a été analysé) — 3 doublons/quasi-doublons écartés avant traitement, 22 diagrammes retenus. Origines identifiées quand visibles : repost Facebook d'un compte « Jam Junaid Altaf » relayant une chaîne Telegram, chaîne « Global Pip Follow », comptes « SMC TradeZone », « AnnalyTrader », « ArvindaTrader » (carrousel « Important Indicator »), et plusieurs diagrammes sans attribution visible. Même réserve que pour le premier lot (§3) : matériel de vulgarisation de réseaux sociaux, pas une source académique ou professionnelle vérifiée — voir §5.3.

Contrairement au premier lot, ces 22 descriptions ont été versées directement dans `jane_knowledge` (RAG de Jane, `agents/jane_knowledge.py`) via `data/jane_diagrammes/import_2026-08-23.json` plutôt que de rester une documentation seule — ce document en est la synthèse narrative, ce fichier JSON la version machine-lisible réellement ingérée (les deux doivent rester cohérents entre eux).

### 5.1 Concepts confirmant la couverture existante — aucune nouveauté

La majorité des diagrammes illustrent des figures déjà couvertes par le catalogue actuel (60 détecteurs après le premier lot, pas seulement les 25 d'origine) : Support/Résistance et retournement de rôle après cassure, Double Top (3 points d'entrée), Hammer, Head & Shoulders + inverse, **Triangle Symétrique** (haussier/baissier — implémenté depuis le §1.2 du premier lot), Shooting Star, une grille croisant 8 figures (dont **Triple Top/Bottom**, également implémentés depuis le premier lot), un biseau ascendant cassé (Rising Wedge), et un critère de bougie d'achat proche du Bullish Engulfing. Aucun de ces diagrammes n'apporte de géométrie nouvelle — confirmation de définitions déjà câblées, pas des candidats.

*Note de correction* : la première version de `data/jane_diagrammes/import_2026-08-23.json` (analysée sans avoir relu ce document) affirmait à tort que Triangle Symétrique et Triple Top/Bottom n'étaient pas couverts par George — erreur corrigée après ce recoupement. Exactement le type d'incohérence que consolider les deux lots dans un seul document doit éviter à l'avenir.

### 5.2 Nouveaux candidats — indicateurs continus, pas des figures géométriques ponctuelles

Contrairement au §1 du premier lot (des géométries de prix ou des relations entre bougies), ces candidats sont des **indicateurs calculés en continu sur toute la série de prix** — plus proches de `engine/features.py` (qui calcule déjà RSI, MACD, Bollinger, et `position_vs_moving_averages` en SMA 50/200) que de `engine/patterns/` :

| Indicateur | Description | Statut chez George |
|---|---|---|
| **EMA 9 / 21** | Moyennes mobiles exponentielles courtes, présentées comme repères de tendance court/moyen terme (points d'entrée/sortie au contact) | Absent — George utilise des SMA 50/200 (`position_vs_moving_averages`), pas d'EMA ni d'horizons courts |
| **EMA 50 / 200** | Mêmes rôles que les SMA 50/200 déjà utilisées (stop-loss sous la 50, tendance long terme sous la 200) | Horizon déjà utilisé par George, mais en SMA — l'EMA elle-même (calcul différent, plus réactif) reste absente |
| **ADX + DMI** | Force de la tendance (ADX) indépendamment de sa direction (+DMI/-DMI) | Absent — aucun calcul de force de tendance dans le moteur actuel |
| **Points Pivots** | Niveaux de support/résistance (S1-S3/R1-R3) calculés depuis le plus haut/bas/clôture de la session précédente | Absent |
| **Volume Profile (VPVR)** | Volume par niveau de prix (HVN/LVN/POC) plutôt que par unité de temps | Absent |
| **Point d'épuisement (divergence prix/oscillateur)** | Signal de fin de mouvement quand un pic/creux de prix ne confirme pas un pic/creux d'oscillateur | Absent, et l'oscillateur exact n'est pas nommé dans la source — pas exploitable tel quel |

Recommandation : comme pour le §1.1 du premier lot, ces indicateurs ont des définitions mathématiques standard et objectives (Pivot Points et ADX en particulier), mais nécessiteraient une source de référence primaire avant implémentation plutôt que la seule géométrie visible sur une capture d'écran.

### 5.3 Réserves sur la qualité de la source

- Une grille de la chaîne « Global Pip Follow » associe des combinaisons de figures à une notation en étoiles sans méthodologie explicite (même défaut que « Dock Wave »/« Ticksban » au §3 du premier lot) — non exploitable comme source de fiabilité.
- Un diagramme présente une zone d'entrée comme une « 100% Profitable Entry Zone » — affirmation promotionnelle non étayée, jamais à restituer comme un fait par Jane (voir la consigne correspondante dans `data/jane_diagrammes/import_2026-08-23.json`).
- Le repost Facebook/Telegram (Double Top, 3 types d'entrée) et les captures « ArvindaTrader » n'ont pas d'attribution vérifiable au-delà du pseudo affiché.

### 5.4 Statut : non implémenté

Contrairement au premier lot (§4), aucun concept du §5.2 n'a été implémenté — ce second lot vient d'être versé dans `jane_knowledge` (RAG de Jane) pour enrichir son second avis, pas encore évalué pour une extension du catalogue de détecteurs. Voir `TODO.md` pour le suivi plus général de l'évaluation de la pertinence de Jane.
