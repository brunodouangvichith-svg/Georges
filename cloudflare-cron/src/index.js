// Worker Cron Triggers qui remplace les `schedule:` désactivés dans
// ../../.github/workflows/*.yml (voir CLAUDE.md, section "Cron Cloudflare").
// Un seul Worker, huit Cron Triggers (wrangler.toml) -- le handler
// `scheduled` distingue le job via `event.cron` (la chaîne cron qui a
// déclenché CET appel précis) plutôt que huit Workers séparés à déployer/
// surveiller individuellement.
//
// Chaque route appelée est protégée côté API par `require_cron_secret`
// (api/auth.py) -- PAS une session Supabase (`require_user`), volontaire :
// voir le docstring de cette fonction pour pourquoi. `env.CRON_SECRET` doit
// être strictement identique au `CRON_SECRET` configuré sur le service
// Render george-api (render.yaml), sinon chaque appel échoue en 401.

// Horaires espacés d'au moins 30 min entre deux jobs quelconques (voir
// wrangler.toml pour pourquoi : contention CPU réelle sur le process
// unique de george-api, un problème qui n'existait pas avec un runner
// GitHub Actions isolé par job).
const JOBS = {
  "0 6 * * *": "/cron/energy-prices",
  "0 7 * * *": "/cron/bonds",
  "0 20 * * *": "/cron/fundamentals",
  "0 21 * * *": "/cron/george-veille",
  "30 21 * * 6": "/cron/jane-veille-web",
  "30 21 * * 1,3": "/cron/price-history-and-detection",
  "30 21 * * 0": "/cron/confidence-model-training",
  "30 22 * * 0": "/cron/geopolitical-veille",
};

export default {
  async scheduled(event, env, ctx) {
    const path = JOBS[event.cron];
    if (!path) {
      // Ne devrait jamais arriver (chaque cron de wrangler.toml a sa
      // propre entrée ici) -- gardé comme garde-fou explicite plutôt qu'un
      // `JOBS[event.cron]` silencieusement `undefined` passé à `fetch`.
      console.error(`Cron Trigger sans route associée : "${event.cron}" (voir JOBS dans src/index.js).`);
      return;
    }

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
  },
};
