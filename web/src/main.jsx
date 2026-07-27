import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.jsx'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
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
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
