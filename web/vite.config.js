import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
// PWA (vite-plugin-pwa) : manifeste + service worker qui met en cache
// l'interface (HTML/JS/CSS/icônes) pour qu'elle s'ouvre comme une appli
// installée. Les appels à l'API ne sont PAS mis en cache : George affiche des
// cours et des décisions, une donnée périmée servie hors ligne serait trompeuse.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      // Enregistrement géré à la main dans main.jsx (virtual:pwa-register)
      // pour ajouter un contrôle périodique — sans ça, le script
      // auto-injecté par défaut n'enregistre le service worker qu'une fois
      // au chargement et ne revérifie jamais tant que l'app reste ouverte
      // (le propre comportement du navigateur pour la vérif native est en
      // plus throttle à ~1x/24h). C'est ce qui obligeait à fermer/rouvrir
      // l'app installée deux fois pour voir une mise à jour.
      injectRegister: false,
      includeAssets: ['apple-touch-icon.png'],
      manifest: {
        name: "George — Terminal d'analyse",
        short_name: 'George',
        description: "Analyse technique des marchés : détection de figures, décisions et rapport stratégique.",
        lang: 'fr',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        theme_color: '#0F1626',
        background_color: '#0F1626',
        icons: [
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          { src: 'maskable-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,png,svg,ico,woff2}'],
        navigateFallback: '/index.html',
        // Le retour OAuth Supabase arrive avec #access_token=… : rien à exclure
        // côté chemin, mais on n'intercepte jamais les URL de l'API.
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
      },
    }),
  ],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    globals: true,
  },
})
