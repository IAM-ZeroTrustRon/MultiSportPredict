## Verified takeover and shared agent handoff — October 24, 2026

- `docs/AI_HANDOFF.md` — authoritative shared Gemini/Claude/Codex takeover context,
  verified NHL implementation, ledger snapshot, limitations, commands and backlog.
- `docs/GEMINI_START_HERE.md`, `docs/CLAUDE_START_HERE.md` — copyable starting prompts.
- `docs/TAKEOVER_AUDIT_2026-10-24.md` — findings, targeted repairs and verification.
- `tests/test_takeover_repairs.py` — power solver, score-runner manual pricing and
  weighted settlement provenance regressions.

## Agent handoff and repository state — October 24, 2026

- `docs/HANDOFF_2026-10-24.md` — current architecture, folder map, NHL special-teams
  feature work, archive cleanup, verification results and open items. Start here.
- Root clutter was moved (never deleted) into `archive/backups/`,
  `archive/db-snapshots/`, `archive/scratch/`, `archive/scratch-data/` and
  `archive/misc/`; the root now holds live entry points only.

## NHL — October 21, 2026

- `ingest_nhl.py`, `nhl_sources.py`, `ingest/nhl_api_fetcher.py` — official fixture/result identities and published MoneyPuck CSVs, atomic cache/manifests, verified 5-on-5 and special-teams joins.
- `features/nhl_features.py`, `models/nhl_model.py`, `train_nhl.py` — prior-game rolling 5-on-5, special-teams and workload feature schema, cached regulation Poisson and fitted regular-season OT/SO winner benchmark, chronological validation.
- `run_nhl.py`, `nhl_review.py` — guarded forecasts/observations, market scope, original odds, source provenance and explicit readiness limitations.
- `nhl_observations.py` / `run_nhl.py --observations` — read-only forward winner/goal error metrics, earliest prematch forecast per event; separate from bet ROI.
- `tests/test_nhl_engine.py` — source identity, leakage, probability mass, settlement, price freshness, record exclusion, canonical routing and persistence checks.
- `docs/NHL_COPILOT_HANDOFF.md` — implemented workflow and original specification, including baseline limits.

## Basketball readiness — October 21, 2026

- `models/basketball_readiness.py` — NBA/NCAAB current-season sample policy, per-team counters, immutable observation-market masking.
- `tests/test_basketball_readiness.py` — thresholds, season boundaries, leakage exclusion, ingestion, terminal/Discord and INFO-only persistence.

## Recorded-price report — October 21, 2026

- `grade_predictions.py` / `msp_workflow.py` — shared recorded-price sport breakdown for terminal, summary JSON and explicit Discord delivery.
- `tests/test_recorded_price_report.py` — price provenance, dedup ordering, push denominators, invalid inputs and reporting consistency.

## NBA review additions — October 20, 2026

- score_review.py — shared score-runner terminal/Discord presentation and precise Home/Away/Over/Under labels.
- models/basketball_periods.py — explicit provisional NBA 1H/1Q means, without invented variance or EV.
- tests/test_score_review.py — formatting, side identity, immutability, period arithmetic and no phantom bets.
- docs/NBA_REVIEW.md — command examples, raw JSON mode, assumptions and quote/coverage limits.

## Shared workflow additions — October 19, 2026

- msp.py / msp_workflow.py — supported daily refresh, sport/mixed-slate runs, saved review/delivery, grading, records and backed-up exceptional cleanup.
- mlb_player_source.py — validated official player-ID joins, measured wOBA and consistent MLB player schema.
- kbo_results.py — dated completed KBO scores; ambiguous doubleheaders remain unresolved.
- slate_workflow.json — filled-in mixed-sport command example; edit to actual fixtures.
- docs/PERFORMANCE_2026-10-19.md / performance_snapshot_2026-10-19.json — retained model record, price coverage and cleanup disclosure.
- docs/REPOSITORY_REVIEW_2026-10-19.md — implemented highlights, evidence and remaining priorities.
- tests/test_msp_workflow.py / tests/test_mlb_player_source.py — cleanup protections, fixture handling, saved delivery and official-source validation.
- COMMANDS.md / TABLE_TENNIS_COMMANDS.md — active Git Bash references. Engine-folder guides are compatibility references.

## Table-tennis workflow additions (2026-10-11)

- `data/table_tennis/current_match_config.json` — match identity, URL, confirmed start and format for no-argument copied-page runs.
- `tests/test_table_tennis_paste_grading.py` — clipboard and manual-grading acceptance tests.
- `TABLE_TENNIS_COMMANDS.md` — simple forecast and confirmed-final grading commands.

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
