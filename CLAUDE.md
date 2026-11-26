# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. It holds only what applies to most changes. The full design history (decisions, real bugs, verification notes) lives in `docs/claude/` — **read the relevant section before changing that area** (see "Detailed documentation" below).

## What this repository is

"George" is an agent for technical analysis of financial markets: pattern detection on daily OHLCV data (CAC 40 + CAC Mid 60), per-basket "George Index" scoring, natural-language rationale for trade decisions. FastAPI backend, React web app, Flutter app (**decommissioned for now** — don't port features to it or run its build workflow without asking), Supabase (Postgres + auth), Render hosting, Mistral LLM (DeepSeek fallback), Tavily web search. No order is ever sent to a broker.

Layout: `ingestion/` (models, migrations, data collection) → `engine/` (detection, scoring, decisions) → `agents/` (LLM layer) → `api/` (FastAPI) → `web/`, `mobile/`. Also `notifications/` (email), `cloudflare-cron/` (scheduler), `infra/` (local Docker), `tests/`. Pending follow-ups are in `TODO.md`. The 8-phase roadmap is `George_Prompts_Claude_Code.md`.

## Commands

From the repo root (Python):
```
cd infra && docker compose up -d      # local Postgres 17 + pgvector, Redis, MinIO, Adminer
pip install -e ".[dev]"               # add ,notebook for Jupyter
alembic upgrade head
python -m ingestion.seed
python -m ingestion.price_history     # price_history_long, the price source of the whole analysis
python -m engine.run_detection        # then: python -m engine.propose_decisions
uvicorn api.main:app --reload
pytest                                # DB tests need a running Docker daemon (testcontainers)
```

From `web/`: `npm run dev`, `npm run build`, `npm run lint`, `npm run test`. Local web dev needs `CORS_EXTRA_ORIGINS=http://localhost:5173` on the API.

From `mobile/`: `flutter analyze`, `flutter test`; release APK only through `scripts/build-mobile-release.ps1` (a bare `flutter build apk --release` bakes in empty Supabase settings).

Production: API `https://george-api-mmut.onrender.com`, web `https://george-web-43l7.onrender.com` (`VITE_*` variables are read at build time).

## Rules that apply across the code base

- **Schema:** `ingestion/models.py` is the source of truth; write each Alembic migration by hand.
- **Secrets and external services:** read environment variables at call time, never at import. Each service raises its own `RuntimeError` subclass with a dedicated handler in `api/main.py` — never register a handler on bare `Exception` (the response loses its CORS headers).
- **Patchable references:** `from api import deps` then `deps.engine`; `from agents import mistral_client` then `mistral_client.complete(...)`. Never `from x import y` for these.
- **Prices:** go through `engine.run_detection.load_prices` (`price_history_long`). Closes can be `NaN` (Postgres `Numeric` accepts it, JSONB rejects it): filter them. `prices_ohlcv` is no longer used.
- **Database pool:** small on purpose (2 + 2, Supabase Session pooler). No per-symbol request fan-out; long background jobs use their own engine.
- **LLM output:** numbers are computed in Python; prompts forbid citing anything absent from the supplied context. Optional enrichments degrade instead of failing the request.
- **Human gate:** George proposes, never executes. No automatic closing of a decision, no automatic promotion of a retrained model.
- **Auth:** every router requires `require_user`, except `/cron/*` (`X-Cron-Secret`); `/health` and `/docs` are public.
- **New pattern detector:** register it in `engine/patterns/__init__.py:DETECTORS`, add its direction and level function in `engine/exit_levels.py`, add its case in `tests/test_exit_levels.py`.
- **Contracts kept in sync:** `engine/george_index.py` with `engine/george_index.md`; model features in `engine/features.py:FEATURE_COLUMNS` (also the synthetic dataset in `engine/train_confidence_model.py`).
- **Fictive data** (`seed_demo.py`) stays labelled as such.
- **Scheduling** runs through the `schedule:` triggers in `.github/workflows/` (restored 2026-11; `cloudflare-cron/` is disabled with `crons = []`, never enable both). GitHub may fire them hours late (the 10-minute keep-warm ping was observed on 2026-11-26 to fire far less often).
- **Quotas:** check the Tavily budget before raising any veille volume.
- The repository is **public**: never commit secrets or machine-specific settings.

## Quality conventions (standing instruction, applies to every change)

Before considering any non-trivial change finished (new endpoint, new detector, new mobile screen, anything touching auth/money/external services) — not for a one-line fix or a docs-only edit:

- Run `/code-review` on the diff. This project's own history includes real bugs caught this way (see e.g. the stale-`engine`-reference bug in `api/routers/baskets.py`/`agents/reports.py`, or the `ponderations` bug caught while adding MACD/Bollinger/Stochastic) — treat that as the expected value of this step, not an optional extra.
- Run `/security-review` on anything touching `api/auth.py`, Supabase/Mistral/Resend credentials, the OAuth flows (`login_screen.dart`), or financial calculations (`engine/exit_levels.py`, `engine/propose_decisions.py`, `api/routers/portfolios.py`) — this app proposes real buy/sell decisions and now holds real user accounts, so an auth or a money-math bug is not a cosmetic one.
- For `web/` changes touching a page real users see (not an internal/admin view): run `/accessibility-review`.

Skipping these is a deliberate choice to make under time pressure, not a silent default — if skipped, say so explicitly rather than letting "done" imply "reviewed."

## Detailed documentation

Verbatim history, one file per area. Open the matching file (or `graphify section "<heading>"`) before working there. Code comments that say "see CLAUDE.md, section X" now point to these files.

- `docs/claude/overview.md` — Project overview and phase history: What this repository is
- `docs/claude/foundations.md` — Database, detection engine, scoring, decision lifecycle: Python backend · Quant engine · Learned scoring, baskets & George Index · Risk management & decision lifecycle · Long-term price history
- `docs/claude/detection.md` — Indicators, detectors and model retraining: RSI, Fibonacci et bougies japonaises · Auto-learn: automated confidence-model retraining · MACD, Bollinger Bands & Stochastic · 35 new pattern detectors from George_Strategies_Images_Synthese.md
- `docs/claude/api-auth.md` — API, authentication, portfolios: API · Auth · Named portfolios · Panier Carry Trade
- `docs/claude/hosting-scheduling.md` — Hosting and scheduled jobs: Hosting (Supabase Postgres + Render) · Cron Cloudflare (remplace les workflows GitHub Actions planifiés)
- `docs/claude/agents.md` — LLM layer, chat and Jane: LLM layer · Confidence sub-scores in George's explanation · George explique: formal reformulation by Jane · DeepSeek fallback · Web search fallback for Ask Jane · `/chat` web search fallback for securities outside the tracked universe · Live technical analysis for any company mentioned in `/chat` · "Teach George on the go" via `/chat` · Ask Jane (mobile)
- `docs/claude/collectors-veille.md` — Data collectors and continuous watch: Collection sub-agents · Fondamentaux, dividendes et informations entreprise · Energy Market · Continuous web-based methodology watch for Jane · Continuous company-news watch for George · Geopolitical/economic veille by country, "pilier 7"
- `docs/claude/reports-sharing.md` — Strategic report, email sharing: Share by email · Rapport stratégique hebdomadaire
- `docs/claude/web.md` — Web app: `web/`
- `docs/claude/mobile.md` — Mobile app (Flutter): Mobile Univers screen tweaks (in-app news links, macro button removed) · Mobile login fixes and additions · Mobile app (Flutter)

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. When the answer is under a Markdown heading, `graphify section "<heading>"` prints that section's text, so the .md need not be opened. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
