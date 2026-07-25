# George Index — formule

Le George Index résume, pour un panier (`baskets` / `basket_securities`),
la conviction agrégée de George sur ce panier à un instant donné, sur une
échelle de **0 à 100**. Implémentation : `engine/george_index.py`
(`compute_george_index`) — toute modification de la formule ci-dessous doit
être répercutée dans les deux fichiers à la fois.

## Vue d'ensemble

```
George Index = clip( score_de_base × multiplicateur_momentum × multiplicateur_volume , 0, 100 )
```

## 1. Score de base — moyenne pondérée de confiance

Seuls les titres du panier ayant une **figure active** comptent : une ligne
dans `patterns_detected` dont `detected_at` est dans les
`ACTIVE_WINDOW_SESSIONS` (**5**) dernières séances. Un titre avec plusieurs
figures actives (types différents) ne compte que par sa figure de plus
haute confiance — c'est le signal le plus fort qui représente le titre,
pas leur moyenne.

Soit `A` l'ensemble des titres actifs du panier, `w_i` le poids du titre `i`
dans `basket_securities` (poids égal à `1` si non renseigné) et `c_i` la
confiance (0-100) de sa figure la plus convaincante :

```
score_de_base = Σ(w_i × c_i pour i dans A) / Σ(w_i pour i dans A)
```

**Si `A` est vide (aucune figure active dans le panier), le George Index de
ce panier est indéfini (`None`)** — un panier silencieux n'est ni bon ni
mauvais, il n'y a simplement rien à évaluer. Il ne faut pas renvoyer 0, qui
suggérerait à tort une conviction négative.

## 2. Multiplicateur de momentum

Contrairement au score de base, le momentum se calcule sur **tous les
titres du panier ayant un historique de prix suffisant** (pas seulement les
titres à figure active) : c'est le contexte de fond du panier entier, actif
ou non.

Pour chaque titre `i` avec au moins `MOMENTUM_WINDOW_SESSIONS` (**20**)
séances d'historique :

```
momentum_i = (clôture_aujourd'hui / clôture_il_y_a_20_séances − 1) × 100   (en %)
```

Momentum du panier (moyenne pondérée par les mêmes poids `w_i`, sur
l'ensemble des titres disposant d'un momentum calculable) :

```
momentum_panier = Σ(w_i × momentum_i) / Σ(w_i)

multiplicateur_momentum = 1 + clip(momentum_panier / MOMENTUM_SCALE, −MOMENTUM_CAP, +MOMENTUM_CAP)
```

avec `MOMENTUM_SCALE = 20` et `MOMENTUM_CAP = 0.15` : un momentum de panier
de +20 % (sur 20 séances) déplace l'index de +15 % au maximum ; le
multiplicateur est borné à `[0.85, 1.15]`.

## 3. Multiplicateur de volume

Même principe, sur le volume relatif de chaque titre (volume du jour /
moyenne des `VOLUME_LOOKBACK_SESSIONS` (**20**) séances précédentes) :

```
volume_relatif_panier = Σ(w_i × volume_relatif_i) / Σ(w_i)

multiplicateur_volume = 1 + clip((volume_relatif_panier − 1) / VOLUME_SCALE, −VOLUME_CAP, +VOLUME_CAP)
```

avec `VOLUME_SCALE = 1` et `VOLUME_CAP = 0.10` : un volume de panier deux
fois supérieur à sa moyenne (`volume_relatif_panier = 2`) déplace l'index de
+10 % au maximum ; le multiplicateur est borné à `[0.90, 1.10]`.

## Constantes (résumé)

| Constante | Valeur | Rôle |
|---|---|---|
| `ACTIVE_WINDOW_SESSIONS` | 5 | Fenêtre de fraîcheur d'une figure pour compter dans le score de base |
| `MOMENTUM_WINDOW_SESSIONS` | 20 | Fenêtre de calcul du rendement (momentum) |
| `MOMENTUM_SCALE` | 20 | Normalisation du momentum de panier avant plafonnement |
| `MOMENTUM_CAP` | 0.15 | Effet maximal (±15 %) du momentum sur l'index |
| `VOLUME_LOOKBACK_SESSIONS` | 20 | Fenêtre de référence du volume relatif |
| `VOLUME_SCALE` | 1 | Normalisation du volume relatif de panier avant plafonnement |
| `VOLUME_CAP` | 0.10 | Effet maximal (±10 %) du volume sur l'index |

## Limites connues

- **Pas d'indice de référence dédié** : le "contexte de marché" utilisé
  ailleurs (`engine/backtest.py:compute_market_trend`, feature du modèle
  appris) est un proxy — le rendement moyen de tout l'univers suivi, pas un
  vrai indice (CAC 40, S&P 500...). Le George Index par panier n'utilise pas
  ce proxy : son "momentum" est celui du panier lui-même, ce qui est
  suffisant à ce stade.
- Les poids par défaut (équipondération) sont une simplification ; une
  vraie pondération par capitalisation ou conviction pourra être ajoutée à
  `basket_securities.weight` sans changer la formule.
