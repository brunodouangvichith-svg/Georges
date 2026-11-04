import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { registerSW } from 'virtual:pwa-register'
import './index.css'
import App from './App.jsx'
import AuthGate from './components/AuthGate.jsx'

// Vérifie périodiquement (pas seulement au lancement) qu'une nouvelle
// version de l'app est disponible, et l'applique sans invite (registerType
// "autoUpdate" dans vite.config.js) — sinon une PWA installée qui reste
// ouverte toute la journée sur un téléphone ne revoit jamais le nouveau
// service worker tant qu'elle n'est pas fermée/relancée (et le navigateur
// lui-même ne revérifie nativement qu'environ une fois par 24h). Fetch
// explicite de sw.js avant registration.update() : recommandation officielle
// vite-plugin-pwa pour éviter de déclencher une vérification alors que
// l'appareil est hors-ligne ou qu'un téléchargement du SW est déjà en cours.
const SW_CHECK_INTERVAL_MS = 5 * 60_000

registerSW({
  immediate: true,
  onRegisteredSW(swUrl, registration) {
    if (!registration) return
    setInterval(async () => {
      if (registration.installing || !navigator.onLine) return
      const resp = await fetch(swUrl, { cache: 'no-store' })
      if (resp.status === 200) await registration.update()
    }, SW_CHECK_INTERVAL_MS)
  },
})

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Contrôle le délai avant qu'un retour sur l'app (changement d'onglet,
      // remontage d'écran) redemande les données à l'API plutôt que de
      // servir le cache — refetchOnWindowFocus (par défaut TanStack Query)
      // fait le reste. Abaissé de 30s à 10s à la demande de l'utilisateur
      // (affichage perçu comme pas assez réactif) ; pas de refetchInterval
      // (polling en continu) ajouté volontairement — le pool DB de l'API
      // Render gratuit est limité (2+2, voir CLAUDE.md « Second production
      // failure: QueuePool limit »), un polling global pourrait le saturer
      // si plusieurs écrans restent ouverts simultanément.
      staleTime: 10_000,
      // Sans base de données joignable, chaque tentative peut déjà prendre
      // plusieurs secondes côté serveur (voir ingestion/db.py) — une
      // nouvelle tentative React Query par-dessus doublerait l'attente
      // avant d'afficher un message d'erreur clair.
      retry: 0,
    },
  },
})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthGate>
        <App />
      </AuthGate>
    </QueryClientProvider>
  </StrictMode>,
)
