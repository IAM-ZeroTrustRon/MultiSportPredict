# Table tennis — current workflow (October 19, 2026)

Use the root shared interface in `/c/MultiSportPredict`. The active guides are [table-tennis commands](TABLE_TENNIS_COMMANDS.md) and [all-sports commands](COMMANDS.md). The separate engine folder is retained for compatibility.

Hourly all-sport grading is configured locally. Eighteen unresolved historical table-tennis runs were backed up and removed under the approved cleanup. Public recent-result collection currently fails to read its source page; no successful refresh or complete automated point-score coverage is claimed.

## Historical implementation notes

The older notes below describe earlier snapshots; they are not the current command reference or automation status.

Free table-tennis collection — 2026-10-10

- Added ingest_table_tennis_public.py and table_tennis/public_results.py. Existing Playwright/Chromium reads rendered public Sofascore results without keys. Only confirmed finished Czech Liga Pro matches with numeric player profile IDs, explicit UTC starts, consistent final match wins and all legal game point scores enter tt_events in the canonical multisport_history.db. No odds, lines, end times or live points are invented. Raw public DOM snapshots are archived.
- Actual headless runs collected three completed matches: Urbaniec–Saleny 22 Sep 18:00 UTC (3–1, 71 points), Boruvka–Medek 10 Oct 12:00 UTC (3–1), Biolek–Zika 10 Oct 12:00 UTC (3–0). A repeat real-snapshot import returned duplicate=1, inserted=0. Corrected results replace current records and retain DB versions; CSV export has one row per stored completed event.
- Ordinary HTTP returned 403. Headless match capture succeeded, but league access is intermittent and dated schedule navigation could not be verified. --recent uses visible recent league results; --days attempts dated discovery and explicitly falls back without claiming complete backfill. One of three recently discovered match pages failed to return its point table and was excluded. The collector stops on access challenges rather than attempting bypass. --watch retries failures and retains previous data.
- CSV data/table_tennis/results.csv is an inspectable export of the canonical completed history, not another training store. The default watch interval is 1800 seconds. No OS scheduled task, automation, or long-running background process was installed or left running.
- Training remains unfitted: three results provide zero eligible rows under the existing eight-prior-matches/player and 150-eligible-match gates. Source player IDs/full-name linking to MyStake and automatic grading of MyStake event IDs still require verified reconciliation. Free history is distinct from sportsbook odds; current/alternative price capture remains the separate MyStake/API path.

Table tennis key setup — 2026-10-10

- configure_table_tennis.py prompts for a hidden BetsAPI token, verifies recent completed Czech Liga Pro event/view game point scores, then updates only BETSAPI_KEY in .env. --check verifies an existing saved token without changing .env. Existing The Odds API token is explicitly rejected rather than renamed/reused. No production token was supplied or changed during development.
- Existing ODDS_API_KEY was successfully checked against its own provider's /v4/sports?all=true catalogue: HTTP 200, 180 entries, no table-tennis/Czech Liga Pro coverage. This key cannot enable the table-tennis collector. MyStake copied current odds do not replace completed training history.
- Setup does not verify full Bet365 odds entitlement or reconcile MyStake/player IDs. Use BetsAPI provider fixtures/history together for fitted player coverage, or reconcile cross-source IDs explicitly. Historical results backfill can use --no-quotes to avoid requiring sportsbook odds entitlement.

Worked runs — 2026-10-10: both requested fixtures were collected through the accessible in-app MyStake DOM and copied-text fallback, then saved with paired ML and three alternative point totals. Vaclavik–Havrda displays 10:00; Holovatiuk–Briza displays 10:30. Starts use the user's Eastern timezone. The fresh prematch-anchor bug for matches more than one hour away is fixed; historical closing-price filtering and stale-price rejection are preserved. See COMMANDS.md for the exact example commands. Independent browser automation remains unsuccessful. No finished training history or independent fitted model exists. Final results must retain the same stored IDs for grading.

## API-free MyStake collection and win/cover screening (2026-10-10)

`run_table_tennis.py` now supports a public MyStake match browser collector and a copied-page fallback. Playwright/Chromium are installed in this workspace. Independent headed and headless browser captures both failed to load the market DOM; the existing in-app page was readable. No login, betting, cookie export, hidden API calls or authentication bypass is performed.

MyStake's current match DOM exposes paired moneyline and alternative match point totals. `Game Handicap` lacks verified settlement units and `{!gamenr}` lacks the specific game number, so both are excluded with explicit notes. Do not infer those meanings from prices. All engine reference markets still print without fabricated sportsbook prices. Properly labeled Point Handicap, Total Games/Sets, Set Handicap and explicit 1st-game markets are supported when displayed. A Bet365 betting login is not a BetsAPI API token; direct Bet365 browser collection is not installed or verified.

Only supply a genuinely upcoming match. You must confirm its start with a timezone offset and that the format is best of five. The rendered MyStake date omits timezone/year/format. The `--start-utc` value must correspond to the displayed fixture, not a fabricated future date to bypass a guard. Player order is read from the page even if your command reverses it. Browser identities are normalized full-name hashes and are not automatically merged with other providers' player IDs. DOM observation timestamps do not prove upstream price freshness.

Git Bash, automatic browser attempt (a separate browser opens and closes):

```bash
cd /c/MultiSportPredict
read -r -p "Full match names (First Player vs Second Player): " TT_MATCH
read -r -p "MyStake match URL: " TT_URL
read -r -p "Confirmed start, ISO timestamp with timezone offset: " TT_START
venv/Scripts/python.exe run_table_tennis.py --match "$TT_MATCH" --mystake-url "$TT_URL" --start-utc "$TT_START" --best-of 5
```

Exact fallback if the automated browser cannot load:

1. Open the actual match in your ordinary MyStake browser. Click neutral page text, then Ctrl+A/Ctrl+C inside the sportsbook iframe (do not select a price).
2. Paste that text into Notepad and save as UTF-8 at `C:/MultiSportPredict/data/table_tennis/mystake_match.txt`. It must include both players, the displayed date, league and every desired market with both prices. Use a fresh copy saved within five minutes; saving old prices again does not make them fresh.
3. Run this Git Bash command using the values above, or rerun the three `read` commands:

```bash
mkdir -p data/table_tennis
venv/Scripts/python.exe run_table_tennis.py --match "$TT_MATCH" --mystake-url "$TT_URL" --mystake-text-file "data/table_tennis/mystake_match.txt" --start-utc "$TT_START" --best-of 5
# Discord: copy the saved run ID printed by the runner
venv/Scripts/python.exe run_table_tennis.py --push "Saved Run ID"
```

The copied text must be saved after creating its parent folder. This fallback needs no API or additional browser. A paired ML allows a market-anchored research report even before training; it is not an independent edge against that ML. This collector does not backfill results, so training still requires verified completed-match point scores from imports or a results feed.

`core/historical_storage.py:table_tennis_win_cover_gap(records, min_matches=20, gap_pp=15)` computes percentages on the SAME non-push matches. Records contain `match_won` (Boolean), integer `point_margin`, and signed `point_handicap`. Cover means `point_margin + point_handicap > 0`. Defaults flag an absolute gap of at least 15 percentage points after at least 20 settled matches. Thresholds are configurable descriptive screening choices, not statistically established edge criteria. A favorite can win and fail to cover; unequal rates alone do not imply mispricing.

`TableTennisStore.player_point_cover_gap(player_id, point_handicap, bookmaker, as_of=None)` selects one latest observed prematch point-spread quote within an hour of start, at that exact player line/bookmaker. It ignores in-play quotes, pushes in both percentage denominators, unfinished results, repeated captures, unrelated alternative lines and results unavailable at the cutoff. Defaults use up to 100 eligible matches. Player B signs are reversed. With missing history it returns null percentages and INSUFFICIENT MATCHED HISTORY, not invented zero-percent rates. Normal forecasts automatically include these checks for every verified priced match point spread.

Standalone historical check, Git Bash:

```bash
venv/Scripts/python.exe run_table_tennis.py --win-cover-player-id "Stored Player ID" --point-handicap "Signed Point Handicap" --bookmaker "Bookmaker"
```

The diagnostic alone does not create a prediction or Discord message. To share a prediction containing the diagnostic use its saved-run `--push` command above.

# Czech Liga Pro — collect, train, handicap

This engine accepts **Czech Liga Pro table tennis only**. It is installed locally. It does not use Gemini's archived example prices, unknown-player ratings, or sample results to train.

## What you need to supply once

Put a supported provider credential in `C:/MultiSportPredict/.env`:

```dotenv
BETSAPI_KEY=
```

Fill the value with your actual BetsAPI token. The account must include Events results and, for the complete automatic sportsbook markets, Bet365 prematch access. An alternative adapter uses `ODDS_API_IO_KEY` with table-tennis/Czech league entitlement; `TABLE_TENNIS_BOOKMAKERS` selects entitled books. These keys are **not** the existing `ODDS_API_KEY` used by other sports. Credentials were absent during this implementation, so authenticated league coverage and prices remain unverified. Do not paste credentials into chat.

The organizer's public HTTP pages returned an HTML shell with 403 errors for tournament data. No access workaround is installed. Actual results/prices need the supported feed or a verified exported JSON file.

## Start collecting and training

All commands below are **Git Bash**, from the project folder:

```bash
cd /c/MultiSportPredict

# Initial history: results and fixtures, no per-match odds requests
venv/Scripts/python.exe ingest_table_tennis.py --days 30 --no-quotes

# Capture current prices for upcoming/live events
venv/Scripts/python.exe ingest_table_tennis.py --days 0

# Fit player strength/H2H and evaluate a chronological holdout
venv/Scripts/python.exe train_table_tennis.py
```

Training requires **150 eligible completed matches**, after each player's first eight prior results. Before that, collection still works. The trainer explains the actual shortage. No thin-data guard is bypassed.

For continuous collection with automatic retraining as completed history changes, run this in a separate terminal and leave it open:

```bash
venv/Scripts/python.exe ingest_table_tennis.py --days 1 --watch --interval 60 --auto-train
```

Ctrl+C stops collection; committed history remains. This is polling, not a verified low-latency WebSocket feed. API quotas apply; all upcoming fixtures and entitled books can consume requests. History backfills do not fetch every finished match's closing odds. Market/H2H fitting becomes available after sufficient pre-match quotes accumulate.

## Run the complete handicap

Replace the two quoted player labels with full actual names:

```bash
venv/Scripts/python.exe run_table_tennis.py --match "First Player vs Second Player"
```

The runner refreshes real fixtures, resolves the exact pair, fetches its prices, builds forecasts and saves a permanent report. Provider player order is printed explicitly. If the pair plays more than once, the output lists the event IDs and UTC starts; choose the desired fixture:

```bash
venv/Scripts/python.exe run_table_tennis.py --match "First Player vs Second Player" --event-id "Provider Event ID"
```

Every run shows match winner, game totals/spreads, point totals/spreads, first-game winner/point totals/spreads, expected points/games, exact match scores, H2H sample and residual, player history, workload and known rest. All supported **available** bookmaker lines are evaluated, including alternatives and integer pushes. Both selections are displayed with decimal price, probability and EV. Unpriced model reference lines are clearly separated. A bookmaker can omit or suspend markets; unsupported or ambiguous settlement units remain unavailable.

An event ID includes the provider prefix, e.g. the literal prefix `betsapi:` followed by the actual feed ID. A run ID is the separate `tt_...` value printed after prediction. They are not interchangeable.

## Discord: send the exact saved run

Copy the run ID printed by the prediction command:

```bash
# Preview without sending
venv/Scripts/python.exe run_table_tennis.py --push "Saved Run ID" --dry-run

# Send to your configured Discord destinations
venv/Scripts/python.exe run_table_tennis.py --push "Saved Run ID"
```

Push uses the existing repository Discord broadcaster. It sends the saved research card, including all supported market families and the top priced research selections; it does not recompute probabilities or refresh prices. Full line-by-line details remain in `output/table_tennis/`. Prices are labeled with the saved capture time. Repeated pushes for the same exact event update its card. No real Discord message was sent during implementation.

## Live and offline options

```bash
# Requires an actual collected live point state, not guessed scores
venv/Scripts/python.exe run_table_tennis.py --match "First Player vs Second Player" --live

# Local verified store only
venv/Scripts/python.exe run_table_tennis.py --match "First Player vs Second Player" --no-refresh

# Explicit reference bookmaker, if its paired moneyline is present
venv/Scripts/python.exe run_table_tennis.py --match "First Player vs Second Player" --reference-book "Bookmaker"

# Discord for any of those runs
venv/Scripts/python.exe run_table_tennis.py --push "Saved Run ID"
```

Live point snapshots must be recent and legal. Live EV requires quotes carrying the same score snapshot; the generic BetsAPI odds summary does not establish point-level synchronization, so those quotes are excluded from live EV. A pre-match market anchor is conditioned on live points once. An in-play moneyline is never treated as pre-match strength and conditioned a second time. This remains live research until feed delay and point-market calibration are measured.

## Monitor, export and grade

```bash
venv/Scripts/python.exe ingest_table_tennis.py --stats
venv/Scripts/python.exe train_table_tennis.py --export "output/table_tennis/training_rows.json"
venv/Scripts/python.exe train_table_tennis.py --diagnostic
venv/Scripts/python.exe grade_table_tennis.py
venv/Scripts/python.exe -m unittest -v tests.test_table_tennis_engine
```

Statistics, training, export and grading commands do not send Discord messages. To share an associated prediction, use the saved-run `--push` command above. Grading reports hypothetical one-unit results for captured priced selections. It does not claim actual betting profits, independent bets, or a strategy ROI from correlated alternatives and reruns.

## How the model works

**Elo** measures relative player strength from verified prior results. It starts at an explicitly labeled 1500 prior and updates after observed completed matches. It does not supply injury, motivation, travel or venue effects. Those missing observations are reported as unknown.

The fitted point-strength model learns coefficients for Elo difference, shrunk H2H residual, recent-form residual and observed same-day game workload. No post-tournament organizer rating is used as a pre-match feature. Actual end times are required for numerical rest observations; rest effects are not fitted yet. Without an observed end time, a result becomes eligible on the next UTC day, avoiding an invented match duration or same-session leakage.

**Top-down** uses paired prices from one bookmaker, removes their proportional margin and retains bookmaker/source/timestamp provenance. When enough historical pre-match prices exist, a separate model learns their contribution alongside strength/H2H. Without trained coverage, the runner can show market-implied scoring references or an explicit untrained Elo reference, but labels those experimental. Market-implied forecasts are not independent evidence of an edge against that same market.

The scoring engine models legal games to 11, win by two, and best-of-five matches. It builds point/game totals and handicap distributions from legal terminal outcomes. It exposes tiny omitted deuce-tail probability rather than normalizing it away. Constant independent point skill is a model assumption; serve-specific skills and point dependence are not validated.

**Poisson** is included as an auxiliary losing-point dispersion diagnostic. Independent Poisson scores are not used to generate table-tennis results: they would assign probability to impossible final scores.

**EV** is expected return per unit staked: `P(win) * (decimal_price - 1) - P(loss)`. Push probability is handled separately. Positive EV is still a research estimate, not a strong bet. Model versions, chronological holdout Brier/log loss and saved forecast results support subsequent validation. Until prospective calibration exists, all selections remain research.

## Verified exports as an alternative source

```bash
venv/Scripts/python.exe ingest_table_tennis.py --import-file "Verified Export JSON Path"
venv/Scripts/python.exe run_table_tennis.py --match "First Player vs Second Player" --no-refresh --quotes-file "Verified Quotes JSON Path"
venv/Scripts/python.exe run_table_tennis.py --push "Saved Run ID"
```

Normalized imports contain `events` and `quotes` arrays. Event fields: `event_id`, full `player_a`/`player_b`, stable `player_a_id`/`player_b_id`, `league: Czech Liga Pro`, `country: CZ`, `best_of: 5`, `start_utc`, `retrieved_utc`, `source_url`, `status`, completed `game_scores` and actual `current_points`. Optional observed `end_utc` enables same-session history and rest. All timestamps require timezone offsets. Finished matches need every legal game's point score; examples are refused.

Quote fields: exact `event_id`, `market`, `line`, `price_a`, `price_b`, `bookmaker`, `quoted_utc`, `retrieved_utc`, `source_url`, and explicit Boolean `is_live`. Prices are **decimal**, unlike the American-odds flags in other sport runners. For totals A=Over and B=Under. For spreads the signed line is added to the stored first player's margin; the second player's line is its negative. Supported market tokens are printed in the source module and CLI reports. Quarter lines and one-sided prices are rejected.

Collection and saved training data use `tt_*` tables inside **multisport_history.db**. Existing sport predictions are preserved. JSON raw archives, immutable model versions, and reports are supplementary audit artifacts, not another database.

## Validation status

Independent checks cover legal exact scores, deuce, live played-point preservation, expected totals, reversal, pushes, stale prices, event ambiguity, Sr/Jr identity, restart/corrections, chronological fitting, Discord transport and immutable runs. Authenticated provider requests were tested with mocked transports; real-account collection could not run without a supported token. The actual vendor's public table-tennis response example was checked as parser evidence, never imported into production training.

Primary specifications: [BetsAPI event view](https://betsapi.com/docs/events/view.html), [completed events](https://betsapi.com/docs/events/ended.html), [event odds](https://betsapi.com/docs/events/odds.html), [full Bet365 prematch](https://betsapi.com/docs/bet365/prematch.html), [Odds-API.io OpenAPI](https://docs.odds-api.io/api-reference/openapi.json).
