# Jane — Synthèse des connaissances

Document de référence consolidant l'ensemble des sources sur lesquelles Jane s'appuie, pour ses deux rôles : veille méthodologique (catalogue de patterns) et second avis analytique (décisions d'achat/vente).

---

## 1. Analyse technique — sources externes

| Source | Nature | Apport pour Jane |
|---|---|---|
| **Investopedia** | Référence, anglophone | Définitions et critères de validation des patterns |
| **BabyPips** (School of Pipsology) | Pédagogique, progression par niveaux | Valider qu'une explication de George reste accessible à un non-expert |
| **TradingView** | Communautaire | Indicateurs et idées de trading partagées par des traders — variantes de patterns réellement utilisées en pratique |
| **ProRealTime** | Logiciel professionnel | Référence pour l'analyse technique active |
| **NanoTrader** | Logiciel professionnel | Référence pour les méthodologies de backtesting de stratégies |

**Règle d'intégration** : un candidat de pattern identifié via ces sources n'est jamais ajouté directement à la détection en production — il passe par le pipeline de backtesting sur l'historique de George (pilier 5) et n'intègre le catalogue actif que si sa performance mesurée le justifie.

---

## 2. Gestion de portefeuille & finance de marché — corpus académique

Six sources : *Gérer le portefeuille de valeurs mobilières* (Introduction, Notions de base, Repérer et utiliser l'information), *Gestion de Portefeuilles* (I. Kharroubi, Paris-Dauphine), *Gestion de Portefeuille* (D. Poincelot), *Finance de Marché Appliquée* (E. Laffort).

### 2.1 Notions de base du placement
- **Trois types de placements** : garantis (obligations d'État), productifs indexés à l'inflation (actions à dividendes, immobilier locatif), spéculatifs (actions de croissance, options).
- **Quatre critères d'évaluation** : rendement (R = Y + G), sécurité du capital, liquidité, exigence de gestion.
- **Six risques** : financier/d'affaires, taux d'intérêt, marché, inflation, négociabilité, fiscal.
- **Mesure du risque par l'écart-type** : coefficient de variation V = σ/R̄ — barème : <24 % risque faible, 25-60 % moyen, >60 % élevé.
- **Continuum rendement-risque** : comptes bancaires → CPG → obligations d'État → obligations de compagnies → actions privilégiées → immeubles à revenus → actions ordinaires → métaux précieux → options.

### 2.2 Sources d'information (approche descendante / top-down)
Quatre niveaux emboîtés : économie générale (PIB, inflation, taux directeur) → industrie (Porter) → entreprise (rapports financiers, initiés) → prix des valeurs (cotes, le prix synthétiserait toute l'information disponible — lien direct avec l'analyse technique).

### 2.3 Théorie moderne du portefeuille
- **Rendement et risque** : E(Rp) = Σ xi E(Ri) ; Var(Rp) = Σi Σj xi xj Cov(Ri, Rj).
- **Diversification** : à ρ = -1, le risque peut s'annuler théoriquement ; en pratique, les titres covarient plutôt positivement.
- **Risque systématique / spécifique** : β = Cov(Ri, RM) / Var(RM) ; une trentaine de titres suffit à éliminer l'essentiel du risque spécifique.
- **Frontière efficiente** : ensemble des portefeuilles non dominés au sens moyenne-variance. Avec actif sans risque → droite de marché des capitaux (CML), théorème des deux fonds (fonde la gestion indicielle).
- **MEDAF/CAPM** : E(Ri) = Rf + βi × [E(RM) - Rf]. Validation empirique imparfaite (Fama-French 1992 : le bêta seul n'explique pas tout — taille, book-to-market interviennent aussi).
- **APT** : généralise le MEDAF via un modèle factoriel + absence d'arbitrage, sans hypothèse d'équilibre général : E(Ri) = λ0 + λ1·bi,1 + ... + λK·bi,K.

### 2.4 Gestion active et passive
- **Passive** : réplique un indice large, s'appuie sur l'efficience des marchés.
- **Active — sélectivité** : modèle de Gordon-Shapiro (P0 = D1/(k-g)), comparaison à la Security Market Line pour juger sous/sur-évaluation.
- **Active — market timing** : ajustement du bêta du portefeuille selon l'anticipation de marché.
- **Analyse technique** : figures (triangles, tête-épaules), moyennes mobiles (signal au croisement), RSI (0-100, seuils 20/80, divergences).
- **Limite documentée** : un portefeuille à bêta cible correctement atteint peut conserver jusqu'à 89 % de risque spécifique s'il contient trop peu de titres.

### 2.5 Mesures de performance
- **Sharpe** : S = (Rp - Rf)/σ(Rp) — portefeuille non diversifié.
- **Treynor** : T = (Rp - Rf)/βp — portefeuille diversifié.
- **Alpha de Jensen** : α = Rp - [Rf + βp×(RM-Rf)] — capacité de sélectivité, ne se classe pas entre fonds de risques différents.
- **Décomposition sélectivité / market timing** en trois étapes (bêta constant vs bêta effectif vs réalisé).

### 2.6 Efficience des marchés — point de vigilance central pour Jane
- **Forme faible** : l'historique des cours ne permet pas de battre systématiquement le marché → **l'analyse technique serait inutile** selon cette hypothèse.
- **Forme semi-forte** : toute l'information publique est intégrée → l'analyse fondamentale publique serait également inutile.
- **Forme forte** : même l'information privée est intégrée.
- **Anomalies documentées** : effet janvier, effet taille, sur-réaction/sous-réaction (Thaler-DeBondt 1985) — nourrissent la finance comportementale et relativisent l'efficience stricte.

*Jane doit pouvoir restituer cette critique académique si elle est interrogée — elle ne l'occulte pas, mais elle ne l'utilise pas non plus pour invalider systématiquement le travail de George : les anomalies documentées sont justement ce que George cherche à exploiter.*

### 2.7 Assurance de portefeuille (lien direct avec le pilier 8 de George)
- **OBPI** (Option Based) : portefeuille + put, valeur terminale max(ST, K), K = plancher garanti.
- **Stop-Loss** : bascule totale actif risqué ↔ actif sans risque selon leur valeur relative — coûts de transaction élevés si oscillation fréquente.
- **CPPI** : coussin Ct = Vt - P·S⁰t, montant alloué au risqué = m·Ct — le multiple m contrôle l'agressivité (effet de levier sur le coussin, risque de franchissement du plancher si chute brutale entre deux révisions).

*Ces trois cadres formalisent académiquement ce que le pilier 8 de George (take-profit/stop-loss, sortie totale/partielle/maintien) fait déjà de façon heuristique — une base théorique pour affiner ces niveaux.*

### 2.8 Politique de placement
Formalisation écrite systématique : objectifs (rendement + risque combinés, jamais l'un sans l'autre), contraintes réglementaires, fiscales, de liquidité.

### 2.9 Fonctionnement des 5 grands marchés (infrastructure concrète)
- **Monétaire** : JJ à 1 an, calculs linéaires (Exact/360), taux directeur vs taux JJ.
- **Changes** : cotation au certain/à l'incertain, swap cambiste, points de swap.
- **Obligataire** : calculs actuariels, duration (D), sensibilité (S = (1/P)·dP/dr), convexité (correction au 2nd ordre) — risque de sous-estimer l'impact d'une variation de taux si la convexité est négligée.
- **Actions** : hiérarchie des financements (pecking order), multiples (PER, PEG), modèles d'actualisation (Fisher, Gordon-Shapiro, Molodovski, Bates).
- **Options** : delta, gamma, thêta, véga, rhô ; stratégies straddle/strangle/condor/butterfly.

---

## 3. Méthode Fujimoto — référence complémentaire (hors corpus académique)

Règle mécanique de gestion active par paliers, fournie directement (pas une source de cours) :

| Variation vs prix de référence | Action |
|---|---|
| -5 % | Ne rien faire |
| -15 % | Acheter 10 % supplémentaires |
| -25 % | Acheter 25 % supplémentaires |
| +5 % à +15 % | Conserver |
| +25 % | Vendre 10 % |
| +35 % | Vendre 20 % |
| +60 % | Vendre 40 % |
| +100 % | Vendre la totalité |

Asymétrie : les seuils de vente sont plus élevés et plus étagés que les seuils d'achat — on laisse courir les gains plus longtemps qu'on ne tolère les pertes non compensées. À mettre en regard (pas à substituer) de la logique de niveaux dérivés de la géométrie du pattern déjà utilisée par George.

---

## 4. Comment Jane utilise ces connaissances

| Connaissance | Utilisée pour |
|---|---|
| Sources TA (Investopedia, TradingView...) | Veille méthodologique — nouveaux candidats de patterns |
| Théorie de portefeuille (Markowitz, MEDAF) | Second avis — cohérence de diversification globale |
| Mesures de performance (Sharpe, Treynor, Jensen) | Second avis — évaluer une décision au-delà du rendement brut |
| Assurance de portefeuille (CPPI, OBPI, Stop-Loss) | Second avis — affiner les niveaux de sortie du pilier 8 |
| Efficience des marchés | Second avis — point de vigilance restituable, pas un veto |
| Méthode Fujimoto | Second avis — référence alternative pour les scénarios de sortie |

**Rappel des garde-fous** : Jane ne détecte aucun pattern, ne décide jamais, et n'intègre aucun candidat sans backtesting validé. Son avis reste consultatif — c'est George qui arbitre et communique la décision finale à l'investisseur.
