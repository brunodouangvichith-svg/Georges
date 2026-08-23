# agents

Sous-agents de veille (presse, macro, résultats, réglementaire, géopolitique — pilier 7). MVP en place : `orchestrator/` (dispatch, validation multi-source, quarantaine) + `collectors/{macro,eurostat,tic,synthesis}.py`, plus `jane_knowledge.py`/`jane_veille.py` (base de connaissances de Jane, alimentée en continu). Presse, réglementaire, calendrier résultats et le scraping réel des sources de méthodologie (Investopedia, TradingView...) restent à faire — voir `George_Prompts_Claude_Code.md` et `whitelist_journaux.md`.
