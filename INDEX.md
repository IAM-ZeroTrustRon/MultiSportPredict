- `tests/test_table_tennis_report.py` — output value/sign preservation, all-alternative Discord pagination and read-only saved-report CLI checks.
- `run_table_tennis.py --show/--list-runs` — display saved predictions directly in the terminal.

- `TABLE_TENNIS_COMMANDS.md` — step-by-step Git Bash setup, free collection, progress troubleshooting, training, reports, grading and Discord commands.

- `ingest_table_tennis_public.py`, `table_tennis/public_results.py`, `tests/test_table_tennis_public.py` — API-free public browser results, strict per-game validation, raw capture audit, canonical ingestion, CSV export and optional 30-minute watch.

- `configure_table_tennis.py`, `tests/test_table_tennis_setup.py` — hidden token setup, verified Czech completed-point access, preservation of other keys and failure checks.

- `table_tennis/browser_source.py`, `requirements-table-tennis.txt` — MyStake public browser capture and copied-text fallback, explicit market identity and event confirmation.
- `tests/test_table_tennis_browser.py` — real-page label regression, paired alternatives, identity/price rejection and independent win/cover checks.
- `core/historical_storage.py:table_tennis_win_cover_gap`, `TableTennisStore.player_point_cover_gap` — paired historical descriptive point-cover screening.

- `ingest_table_tennis.py`, `train_table_tennis.py`, `run_table_tennis.py`, `grade_table_tennis.py` — Czech-only collection, training, full handicap reports and prospective grading.
- `table_tennis/` — strict contracts, documented feed adapters, legal scoring, market settlement, point-strength/H2H fitting, Poisson diagnostic and Discord report.
- `core/historical_storage.py:TableTennisStore` — persistent `tt_*` tables in the canonical database.
- `tests/test_table_tennis_engine.py`, `README_CZECH_LIGA_PRO.md` — independent acceptance tests and exact operating instructions.

# Repository index

- `run_tennis_full.py`, `tennis_package_source.py` — names-only Challenger research package, sourced observations, all alternative markets and captured-report Discord push.
- `tests/test_tennis_package.py` — current quote parsing, reverse handicaps, unsupported settlement rejection and pre-fixture result filtering.

- `live_odds.py` — automatic tennis moneyline, game lines and available alternative/set lines; paired sportsbook prices and 15-minute cache.

- `ingest_basketball_official.py` — working public KBL/NZ NBL/BBL source adapters, score histories and metrics.
- `ingest_basketball_espn.py` — NBA/WNBA/men's and women's college score histories.
- `run_basketball.py`, `run_ncaaf.py` — verified fixtures, custom priced markets, saved review and Discord.
- `ingest_ncaaf_model.py`, `models/score_ratings.py` — FBS data, opponent-adjusted score model and chronological holdout.
- `score_odds.py`, `sports_feed.py` — bookmaker matching and sourced fixture normalization.
- `tennis_sources.py`, `tennis_context.py` — official WTA/recent ATP and sourced context/serve-return profiles.
- `tennis_context_template.json` — player observations and explicit scenario template.
- `tests/test_score_engine.py` — leakage, spread signs, pushes, storage identity, context, source and rendering checks.
- `COMMANDS.md` — Git Bash commands, including separate Discord commands.

- `models/tennis_markets.py` — Elo-anchored custom tennis line estimates, pushes and price-based EV.
- `tests/test_tennis_markets.py` — distribution normalization, win-probability consistency, symmetry, pushes and invalid inputs.

- `tests/test_tennis_ingest.py` — tennis source mapping, walkovers and seed exclusion.

- `STATE_OF_MODEL.md` — architecture, data status and known issues.
- `HANDOFF_CLINE.md` — repository working agreement.
- `soccer_store.py` — competition/season storage and scoped soccer views.
- `ingest_soccer_espn.py` — ESPN standings and fixtures, including Nations League.
- `ingest_soccer_fd.py`, `ingest_soccer_global.py` — alternative soccer ingestion.
- `team_stats_provider.py` — prediction input lookup.
- `run_soccer_batch.py` — soccer slate runner.
- `data_guard.py` — data audit and prediction guards.
- `tests/test_soccer_competition_store.py` — competition storage regressions.

- `output/research/run_2026_10_09_soccer.py` — reproducible captured soccer research for three fixtures; reports, JSON calculations and Discord research cards, no database writes or live refresh.
- `tests/test_soccer_live_market_route.py` — shared provider routing, missing-market refusal and Ligue 1 aliases.
