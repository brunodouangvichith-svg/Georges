# Cron Cloudflare — remplace les workflows GitHub Actions planifiés

Contexte : la limite de dépenses GitHub Actions du dépôt est bloquée
depuis le 13 octobre 2026 (voir CLAUDE.md), ce qui a arrêté tous les jobs
planifiés (`daily_bond_yields.yml`, `daily_energy_import.yml`,
`daily_fundamentals_import.yml`, `daily_george_veille.yml`,
`weekly_geopolitical_veille.yml`, `weekly_confidence_model_training.yml`,
`weekly_jane_veille_web.yml`, `price_history_and_detection.yml`). Ce
Worker Cloudflare (Cron Triggers, **gratuit**, pas de carte bancaire
requise pour ce niveau d'usage) les remplace en appelant les nouveaux
endpoints `POST /cron/*` de l'API (`api/routers/cron.py`), à des horaires
proches de l'original mais espacés d'au moins 30 min entre deux jobs
(voir `wrangler.toml` pour le détail et le pourquoi — un deuxième passage
`/code-review` a trouvé que copier le calendrier GitHub Actions tel quel
recréait des collisions inoffensives sous GitHub Actions mais réelles une
fois tous les jobs exécutés sur le même process Render gratuit). Les
workflows GitHub restent en place, déclenchables à la main
(`workflow_dispatch`) en secours.

**Un seul Cron Trigger pour les 8 jobs**, pas un par job : Cloudflare
limite les Cron Triggers à **5 par compte** sur le plan Workers Free (pas
par Worker — facile à dépasser dès qu'un compte héberge plusieurs
Workers). `src/index.js` reçoit un tick toutes les 30 min et décide
lui-même, en code, lequel des 8 jobs (s'il y en a un) appeler à cet
instant précis — voir `JOBS` dans ce fichier.

## Prérequis

- Un compte Cloudflare gratuit (`dash.cloudflare.com`, inscription par
  email, aucune carte bancaire nécessaire pour les Workers/Cron Triggers à
  ce volume).
- Node.js installé sur ta machine (pour lancer `npx wrangler`, le CLI
  Cloudflare — pas besoin de l'installer globalement).

## Étapes

### 1. Générer le secret partagé (`CRON_SECRET`)

Ce secret doit être **strictement identique** des deux côtés (Render et le
Worker) — c'est lui qui prouve au Worker qu'il a le droit d'appeler les
routes `/cron/*` sans passer par une vraie session utilisateur Supabase.

```bash
openssl rand -hex 32
```

Copie la valeur générée, elle sert dans les deux étapes suivantes.

### 2. Configurer `CRON_SECRET` côté Render (API)

1. `dashboard.render.com` → service **george-api** → onglet **Environment**.
2. Ajoute une variable **`CRON_SECRET`** avec la valeur générée à l'étape 1.
3. **Save Changes** — Render redéploie automatiquement le service.

(`render.yaml` déclare déjà cette variable comme `sync: false` : si le
service est reprovisionné depuis le blueprint, Render te la redemandera à
ce moment-là.)

### 3. Installer wrangler et te connecter

Depuis ce dossier (`cloudflare-cron/`) :

```bash
cd cloudflare-cron
npx wrangler login
```

Ça ouvre une page de connexion Cloudflare dans ton navigateur — autorise
l'accès, puis reviens au terminal.

### 4. Déployer le Worker

```bash
npx wrangler deploy
```

Ça lit `wrangler.toml` (nom du Worker, l'unique Cron Trigger "`0,30 * * * *`",
l'URL de l'API) et publie `src/index.js`. La commande affiche l'URL du
Worker à la fin (pas vraiment utile ici — les Cron Triggers n'ont pas
besoin qu'on visite cette URL, ils s'exécutent tout seuls).

**Si `wrangler deploy` échoue au tout premier essai avec une erreur du
genre `invalid cron string`** sur l'un des crons : vérifie que tu es bien
dans `cloudflare-cron/` (`pwd`) et pas à la racine du dépôt — lancée
depuis la racine, la commande détecte le site web (`web/`) et tente de le
déployer comme Worker à la place, ce qui échoue sur un tout autre quota
(nombre de fichiers statiques) sans rapport avec ce Worker.

### 5. Configurer `CRON_SECRET` côté Worker (même valeur qu'à l'étape 1)

```bash
npx wrangler secret put CRON_SECRET
```

Colle la **même valeur exacte** qu'à l'étape 2 quand c'est demandé. Ce
secret n'est jamais écrit dans `wrangler.toml` ni commité — stocké
chiffré côté Cloudflare.

### 6. Vérifier que le Cron Trigger est bien enregistré

`dash.cloudflare.com` → **Workers & Pages** → **george-cron** → onglet
**Triggers** → tu dois voir **une seule** expression (`0,30 * * * *`,
section **Cron Triggers**) — normal, c'est le seul trigger Cloudflare pour
les 8 jobs, voir plus haut.

### 7. Tester manuellement avant d'attendre le premier déclenchement réel

Deux façons de vérifier que tout est branché correctement :

**a. Depuis le dashboard** : onglet **Logs** du Worker → bouton **Begin log
stream** → dans un autre onglet, **Triggers** → bouton **Trigger** (ou
équivalent "Test cron trigger") pour forcer un déclenchement immédiat sans
attendre l'heure programmée. Attention : comme `src/index.js` décide
lui-même quel job appeler selon l'heure/minute/jour **réels** au moment du
test (voir plus haut), ce test n'appellera un vrai job que si l'heure
UTC courante tombe pile sur l'une des 8 entrées de `JOBS` — la plupart du
temps, tu ne verras rien dans les logs (comportement normal, pas une
panne : c'est l'équivalent d'un tick de routine sans job à ce moment-là).
Pour un vrai test immédiat, utilise plutôt (b) ci-dessous.

**b. Côté API directement**, sans passer par le Worker, pour isoler un
problème éventuel :

```bash
curl -X POST https://george-api-mmut.onrender.com/cron/energy-prices \
  -H "X-Cron-Secret: <la-meme-valeur-qu-aux-etapes-1-2-5>"
```

Une réponse `{"status":"started","job":"energy-prices"}` confirme que
l'API accepte le secret et a bien lancé le job en tâche de fond (vérifie
ensuite les logs Render pour confirmer que la collecte a réellement
abouti — la route répond immédiatement, avant la fin du job).

## En cas de problème

- **401 sur `/cron/*`** : `CRON_SECRET` ne correspond pas entre Render et
  le Worker — regénère-le et redéfinis-le aux deux endroits (étapes 2 et
  5), en copiant-collant bien la même valeur sans espace parasite.
- **500 sur `/cron/*`** : `CRON_SECRET` n'est pas défini côté Render
  (variable manquante sur le service, voir étape 2).
- **Le Worker ne se déclenche jamais** : vérifie l'onglet **Triggers**
  (étape 6) — si la liste est vide, relance `npx wrangler deploy` depuis
  ce dossier.
- **Un seul job échoue régulièrement, pas les autres** : regarde les logs
  Render du service **george-api** pour l'erreur réelle (le Worker ne voit
  qu'un code HTTP, pas la cause) — chaque route `/cron/*` logue un résumé
  de son job (`engine/bond_alerts.py`, `ingestion.fundamentals`, etc., voir
  `api/routers/cron.py`).

## Pour mettre à jour le Worker après un changement de `src/index.js`

```bash
cd cloudflare-cron
npx wrangler deploy
```

Pas besoin de refaire les étapes 1, 3 et 5 (login et secret restent en
place) — seulement si tu changes `wrangler.toml` (ex. ajouter un cron).
