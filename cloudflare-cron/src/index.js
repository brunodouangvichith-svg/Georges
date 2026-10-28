// Worker Cron Trigger qui remplace les `schedule:` désactivés dans
// ../../.github/workflows/*.yml (voir CLAUDE.md, section "Cron
// Cloudflare"). Un SEUL Cron Trigger ("0,30 * * * *", wrangler.toml --
// toutes les 30 min), pas un par job : Cloudflare limite les Cron Triggers
// à 5 par COMPTE sur le plan Workers Free (pas par Worker), dépassé au
// premier essai avec 8 crons déclarés (voir wrangler.toml pour le détail).
// `scheduled` reçoit donc TOUS les ticks de 30 min et décide lui-même,
// via `JOBS` (heure/minute UTC + jours de semaine optionnels), lequel (s'il
// y en a un) appeler à ce tick précis -- aucune limite de compte Cloudflare
// ne revient jamais en jeu, quel que soit le nombre de jobs ajoutés
// ensuite.
//
// Chaque route appelée est protégée côté API par `require_cron_secret`
// (api/auth.py) -- PAS une session Supabase (`require_user`), volontaire :
// voir le docstring de cette fonction pour pourquoi. `env.CRON_SECRET` doit
// être strictement identique au `CRON_SECRET` configuré sur le service
// Render george-api (render.yaml), sinon chaque appel échoue en 401.
//
// `days` : `undefined`/absent = tous les jours ; sinon un tableau de
// `Date.getUTCDay()` (0 = dimanche ... 6 = samedi). Horaires espacés d'au
// moins 30 min entre deux jobs quelconques (voir wrangler.toml) : contention
// CPU réelle sur le process unique de george-api, un problème qui n'existait
// pas avec un runner GitHub Actions isolé par job.
const JOBS = [
  { hour: 6, minute: 0, path: "/cron/energy-prices" },
  { hour: 7, minute: 0, path: "/cron/bonds" },
  { hour: 20, minute: 0, path: "/cron/fundamentals" },
  { hour: 21, minute: 0, path: "/cron/george-veille" },
  { hour: 21, minute: 30, days: [6], path: "/cron/jane-veille-web" }, // samedi
  { hour: 21, minute: 30, days: [1, 3], path: "/cron/price-history-and-detection" }, // lundi/mercredi
  { hour: 21, minute: 30, days: [0], path: "/cron/confidence-model-training" }, // dimanche
  { hour: 22, minute: 30, days: [0], path: "/cron/geopolitical-veille" }, // dimanche
];

function jobsDueAt(date) {
  const hour = date.getUTCHours();
  const minute = date.getUTCMinutes();
  const day = date.getUTCDay();
  return JOBS.filter((job) => job.hour === hour && job.minute === minute && (!job.days || job.days.includes(day)));
}

async function triggerJob(path, env) {
  const url = `${env.API_BASE_URL}${path}`;
  let response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "X-Cron-Secret": env.CRON_SECRET },
    });
  } catch (err) {
    // Erreur réseau/transport (API Render endormie plus longtemps que le
    // délai par défaut de `fetch`, DNS, etc.) -- distincte d'une réponse
    // HTTP d'erreur, loguée séparément pour que les deux cas restent
    // faciles à distinguer dans `wrangler tail`/le dashboard Cloudflare.
    console.error(`${path} : erreur réseau -- ${err}`);
    return;
  }

  if (!response.ok) {
    const body = await response.text();
    console.error(`${path} a répondu HTTP ${response.status} : ${body}`);
    return;
  }
  console.log(`${path} déclenché avec succès (HTTP ${response.status}).`);
}

export default {
  async scheduled(event, env, ctx) {
    // `event.scheduledTime` (epoch ms) plutôt que `Date.now()` : l'heure à
    // laquelle CE tick était programmé, pas celle à laquelle le code
    // s'exécute réellement (peut dériver de quelques secondes).
    const now = new Date(event.scheduledTime);
    const due = jobsDueAt(now);
    if (due.length === 0) {
      return; // tick de routine (toutes les 30 min), rien à faire la plupart du temps.
    }
    // `scheduled` reste actif tant que la promesse qu'il renvoie n'est pas
    // résolue (comportement standard des Workers) -- pas besoin de
    // `ctx.waitUntil` ici, ce `await` suffit à garder le Worker vivant le
    // temps que tous les `fetch` de ce tick soient partis, même si
    // plusieurs jobs tombent au même quart d'heure (pas le cas aujourd'hui,
    // mais robuste si un futur ajout en recrée un).
    await Promise.all(due.map((job) => triggerJob(job.path, env)));
  },
};
