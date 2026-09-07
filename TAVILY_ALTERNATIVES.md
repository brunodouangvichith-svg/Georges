# Alternatives à Tavily pour la recherche web d'Ask Jane

Référence — pas encore évaluées/intégrées. `agents/web_search.py` utilise Tavily aujourd'hui (voir CLAUDE.md, section "Web search fallback for Ask Jane"). À consulter si Tavily devient un point de friction (quota, coût, qualité) et qu'un remplacement est envisagé.

- **DuckDuckGo AI Chat / API** — pas d'API de recherche officielle "clés en main", mais des options gratuites et sans traçage intégrables via des bibliothèques open source (ex. `duckduckgo_search` en Python).
- **Exa AI** (anciennement Metaphor) — offre gratuite pour développeurs (quota de requêtes mensuelles), recherche sémantique/par similarité, souvent jugée plus qualitative que Tavily sur des recherches textuelles complexes.
- **Perplexity API** (via OpenRouter ou autres passerelles) — payante à l'usage mais coûts bas pour certains modèles connectés au web ; leur interface en ligne reste utilisable gratuitement de son côté.
- **Google Custom Search JSON API** — quota gratuit de 100 recherches/jour, résultats 100% issus de l'index Google classique.
- **Serper.dev / SerpApi** — spécialisés SERP scraping, plan gratuit chacun (environ 2 500 requêtes gratuites au total pour Serper, 100 requêtes/mois pour SerpApi).
- **Brave Search API** — tier gratuit correct pour développeurs (environ 2 000 requêtes/mois), basé sur l'index indépendant de Brave.
