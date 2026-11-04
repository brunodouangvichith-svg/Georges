import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.jsx'
import AuthGate from './components/AuthGate.jsx'

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
