# TODO

## Évaluer la pertinence de Jane (second avis)

`jane_second_opinions` (migration `0015`) persiste désormais chaque note de
second avis de Jane, liée à `decision_id`. Une fois assez de décisions
`cloturee` accumulées (avec un second avis demandé au moment de leur
proposition/confirmation), écrire un script de corrélation entre le contenu
de `jane_second_opinions` et `decision_outcomes.result`/`pnl_pct` : est-ce
que les notes les plus sceptiques de Jane prédisent réellement de moins
bonnes issues, ou son avis n'a-t-il aucune valeur prédictive mesurable ?

Prérequis avant de s'y attaquer :
- Assez de décisions closes avec un second avis persisté pour que la
  corrélation ait un sens statistique (pas encore le cas juste après
  l'ajout de la persistance).
- Décider comment quantifier "scepticisme" à partir d'un texte libre
  (mots-clés, ou passer le texte à un LLM juge qui note une note de -1 à
  +1 ? Choix à trancher au moment de construire le script, pas avant).

Voir aussi la discussion plus large sur comment tester Jane (garde-fous
anti-hallucination déjà couverts par les tests existants, relecture
manuelle par l'utilisateur en attendant).
