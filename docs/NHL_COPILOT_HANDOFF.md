# NHL implementation handoff for GitHub Copilot

Implemented October 21, 2026: public NHL/MoneyPuck ingestion, pregame rolling
features, cached regulation-goal/OT benchmark, root workflow, saved observations,
explicit Discord formatting and scope-aware grading. The current model is a
team baseline: starting goalies are unconfirmed by default, and individual goalie
quality, PP/PK effects and betting splits are not fitted. Those limitations
suppress betting recommendations where required; no missing metrics are invented.

October 24, 2026 extension: the Stage 2 feature list is now implemented from
published rows only. Power-play goals per 60 (5-on-4) and penalty-kill goals
against per 60 (4-on-5) join by official game, team, orientation, season and
date alongside the 5-on-5 rows; xG share, 5-on-5 exposure minutes, back-to-back
status and games in the prior seven days were added to the fitted contract.
Zero-exposure rows contribute no rate and are neither divided nor imputed, and
partially covered MoneyPuck games are refused rather than filled. Feature and
model versions were bumped and the artifact retrained: 2,657 pregame examples,
537 holdout games, goal deviance 1.0625 vs 1.1006 baseline, winner Brier 0.2375
vs 0.2488 baseline. Individual goalie quality, injuries and betting splits
remain unfitted, and the no-vig market benchmark is recorded as unavailable
because no archived historical NHL quotes exist.

The remaining text records the original specification and its corrections.
The existing MultiSportPredict entrypoint is `msp.py`. There is no `predict/`
directory or `predict/dispatcher.py`. `models/basketball_model.py` explicitly
marks itself deprecated/orphaned. Do not build a new isolated dispatcher or
copy that model's missing-value behavior.

## Open the project and give Copilot the specification

Open Git Bash and paste:

```bash
cd /c/MultiSportPredict
git status --short
code .
```

In VS Code, open the Copilot Chat panel. Select Agent mode, attach this file
with Add Context, and send: "Implement the NHL specification in
docs/NHL_COPILOT_HANDOFF.md. Read the project instructions first. Preserve my
existing uncommitted changes. Implement and test the whole workflow; report
any unavailable data without inventing it."

The root NHL commands below are now implemented. A refresh downloads the
published sources and trains only when the underlying history changes. New
forecasts require a genuinely upcoming fixture; old games cannot be replayed
as fresh picks. Model/feature artifacts are local under data/; original source
downloads and manifests are under data/cache/nhl/.

## Copyable agent specification

### Final decision on Gemini's proposed season-summary fetcher

Use the published MoneyPuck CSV approach, but do not paste the proposal
unchanged. Live verification on October 21, 2026 returned HTTP 200 for:
https://moneypuck.com/moneypuck/playerData/seasonSummary/2026/regular/teams.csv

That file has 107 columns. xGoalsPercentage, corsiPercentage,
highDangerShotsFor/Against, highDangerGoalsAgainst, shotsOnGoalAgainst and
goalsAgainst exist; savePercentage does not. The shown code would raise a
KeyError outside its download try/except. Derive team 5-on-5 save rate as
1 - goalsAgainst / shotsOnGoalAgainst only when the denominator is positive
and inputs pass validation. Leave zero-denominator values unavailable.

High-danger shot share is not high-danger save percentage, and MoneyPuck's
high-danger shot definitions must not be relabeled as another source's HDCF.
Do not derive high-danger save percentage from a shot count unless the source
definition explicitly establishes an on-goal denominator. Missing goalie
features remain unavailable; no median starter identity or invented quality.

Keep percentages as ratios in [0,1] internally and format as percentages only
for display. Match the fitted feature names exactly: xg_pct is not an alias
for goal-rate xg, and xG share alone is not a goal-scoring intensity.

The MoneyPuck URL uses season START year (2026 for 2026–27). Resolve that
explicitly from verified fixture season metadata; do not hard-code 2026 or
silently equate all providers' season IDs.

Use this season summary for current upcoming-event snapshots only, with
retrieval/source-age metadata and a verified cutoff. Never attach today's
season aggregate to an older training game. Reconstruct historical rolling
features from the game-by-game CSV described below.

The original NHLAPIFetcher proposal referenced nonexistent helper interfaces.
The implementation now provides ingest/nhl_api_fetcher.py and build_raw() using
the verified official source adapter and existing paired-odds matcher.

Normalize identities consistently for fixtures, odds and advanced statistics
before any join. Maintain explicit verified provider-to-NHL team-ID mappings
and reject ambiguous/unknown mappings. Enforce unique team/situation records
and validate each advanced-stat join as many-to-one. Keep bookmaker, market,
line, timestamp and side dimensions explicit in quote joins; do not collapse
or mix distinct quote pairs. Missing/empty CSVs must produce a clear partial
data failure, preserve the last valid cache, and disable unsupported EV rather
than a KeyError or success claim. Add regression tests for these exact failures.

Basketball's 73 passing regression tests establish tested behavior, not
predictive accuracy. Do not describe any part of this system as bulletproof
or claim professional betting performance based on passing software tests.

Build NHL support into the existing MultiSportPredict workflow. Do not use the
nonexistent predict/dispatcher.py or the deprecated basketball model.

Read HANDOFF_CLINE.md, STATE_OF_MODEL.md, ARCHITECTURE.md, msp.py,
msp_workflow.py, core/historical_storage.py, grade_predictions.py, live_odds.py,
score_odds.py and the current basketball readiness/reporting modules.

### Stage 1 — data ingestion and auditable identities

Implement ingest_nhl.py and a source adapter for dated NHL fixtures, completed
results, official team/game IDs, regular-season/playoff status, regulation
scores, overtime/shootout outcome and final official scores. Save source URLs,
retrieval timestamps and event start times with offsets. Preserve existing
data on failure. Verify the actual public NHL endpoints before coding them;
do not assume an endpoint exists from this document.

Use MoneyPuck's downloadable game/team/goalie history for advanced statistics
when available. Record attribution, source definitions and update times.
Confirm each required column actually exists. Expected goals from MoneyPuck
are model estimates, not directly observed goals. Respect the source's stated
non-commercial-use and attribution terms. Never hard-code a starting goalie
or treat the team's aggregate save percentage as confirmed starter quality.

Use the existing configured Odds API integration for icehockey_nhl paired
moneyline, puck-line and total quotes when available. That is an odds source,
not an xG/Corsi/starting-goalie source. No credentials in code, logs or output.

#### Verified free CSV route — October 21, 2026

The published MoneyPuck team game-by-game download is:
https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv

Its header was fetched successfully and contains 111 columns, including:
- identity: team, season, gameId, playerTeam, opposingTeam, home_or_away,
  gameDate and situation;
- advanced statistics: xGoalsFor, xGoalsAgainst, xGoalsPercentage,
  corsiPercentage, shotAttemptsFor, shotAttemptsAgainst and iceTime;
- high-danger shot measures: highDangerShotsFor, highDangerShotsAgainst,
  highDangerxGoalsFor and highDangerxGoalsAgainst.

Use this published download rather than scraping the website. Prefer MoneyPuck
as the initial advanced-stat source; do not require a second scraper unless
verified required coverage is missing. MoneyPuck's shot-level download excludes
blocked shots, so do not reconstruct Corsi from that shot file. The team CSV
already includes Corsi and shot-attempt fields.

Do not label MoneyPuck high-danger shot share as Natural Stat Trick HDCF% unless
the definitions are verified equivalent. Read the published data dictionary
before interpreting iceTime units or percentage scales.

Fetch/cache the team CSV daily through the future NHL refresh adapter. Validate
the expected header, timestamps, completed-game coverage and row identities
before replacing the last good cache atomically. Retain an unchanged raw copy
and retrieval manifest; a download time is not the upstream update time. If the
file is unchanged, avoid needless feature rebuilding/training. A failed refresh
must preserve old data and surface its real age.

Filter a consistent situation such as 5-on-5 when building even-strength inputs.
Join by validated NHL game/team mappings, not a text-only name merge; check
season-ID conventions between providers. Require one team/game/situation row,
reject ambiguous mappings and accidental many-to-many joins. Build a pregame
feature snapshot for each scheduled event from earlier completed games, then
attach the separately timestamped paired sportsbook quotes. Never merge the
target game's postgame advanced-stat row into its own prediction inputs.

Daily historical goalie stats still do not confirm tonight's starting goalie.
Keep starter verification a separate sourced input or explicitly label it
unknown. Natural Stat Trick remains an optional secondary source whose export
access and metric definitions must be verified before integration.

Deliver and verify ingestion before claiming the model is operational.

### Stage 2 — pregame features

Suggested core inputs, with matching home and away fields:
- 5-on-5 xGF/60, xGA/60, exposure minutes and xG share;
- Corsi share if sourced consistently; do not fabricate it from shots on goal;
- high-danger chance share only if its definition and source are available;
- confirmed starter ID/status, goalie workload, save percentage and GSAx/60
  when available, including goalie sample size;
- both teams' PP and PK rates, using a consistent percentage scale;
- home ice, days/hours of rest, back-to-back status, recent workload;
- current-season games played and clearly separated previous-season priors.

Build rolling features using only games completed before the prediction
cutoff. Shift historical rolling features so a game's outcome never enters
that same game's inputs. Do not use final-season averages to predict earlier
games. Separate current-season and historical samples. Do not count preseason
games toward regular-season readiness. Cache feature/model versions.

Exclude public tickets, public money, sharp_score, money_ticket_gap and reverse
line movement from the initial model unless real timestamped data is present
for both training and inference. Opening/current odds must be synchronized
before calculating movement. Missing data is not zero or 50% public support.

Fit optional-feature imputers on training folds only. Entirely absent columns
must be omitted by a documented fitted feature contract or block that model.
Never impute outcomes, game identity, current odds, confirmed goalie identity,
or source timestamps. A baseline without goalie/advanced inputs must be labeled
as such and separately validated; it cannot claim the advanced model's edge.

### Stage 3 — coherent hockey probabilities

Implement models/nhl_model.py plus a feature builder and train_nhl.py. Do not
train from scratch on every prediction. Store model artifacts, training cutoff,
feature schema and validation metrics; refuse inference with a mismatched schema.

Use a count-based regulation-goal benchmark (for example, two team scoring-rate
models with Poisson distributions) and validate its dispersion and calibration.
Choose a more flexible distribution only if chronological validation supports
it. A predicted home margin above zero is not a moneyline probability and is
not enough to price a puck line. Goal means alone do not establish EV.

Separate regulation probabilities from eventual winner probabilities. Handle
the tied-regulation mass with an explicitly fitted/validated OT/SO component.
Keep regular-season and playoff rules distinct. Never silently assume 50/50
OT/SO conversion as if trained. Projection-only output is acceptable when a
required probability component cannot be validated.

Derive probabilities, pushes and fair prices for ML, signed puck lines and
totals from the defined outcome distribution. Truncate with explicit tail
error, not silent renormalization. Benchmark against a simple historical model
and no-vig market probabilities where matching historical quotes exist.

### Stage 4 — real workflow integration

Add nhl to msp_workflow.SPORTS, refresh_plan and run_command. Implement
run_nhl.py with verified upcoming fixture selection, date/identity/freshness
checks, paired odds matching, saved reviews, --dry-run and explicit delivery.
Do not route NHL through the NBA scoring model just because its CLI is similar.

Write predictions only through core/historical_storage.py into the canonical
multisport_history.db. Use sport=nhl, league=NHL, stable event keys and saved
market scope/settlement rules. Output JSON is an artifact, not a second ledger.
Names-only calls must resolve a unique real fixture; never select the last old
historical row containing those names as the upcoming prediction.

Introduce a clearly labeled NHL readiness policy only after chronological
testing. Prior seasons can train the model without being relabeled as new-season
games. Missing training coverage/goalie information must produce projection-only
or unavailable output rather than invented certainty. All projection-only rows
must be INFO and excluded from the ordinary betting record.

Add NHL results to grade_predictions.AUTO_SOURCES. Store regulation, OT/SO and
official final outcomes separately. Grade against each stored market's explicit
bookmaker rules: two-way ML, regulation three-way, puck line, totals and pushes
must not be conflated. Ambiguous market scope remains unresolved. Include NHL
in pending, ordinary records, recorded-price-only records and workflow snapshots.

Keep Discord delivery explicit through saved runs. Add a clean review with
named selections, original quote prices/times, probability, estimated EV and
data/goalie/readiness limitations. Missing prices mean no EV. No wagers placed.

### Stage 5 — required validation

Test chronological leakage, season rollover, renamed teams/IDs, duplicate feeds,
unknown players/goalies, stale prices, reversed home/away handicaps, integer-line
pushes, overtime versus regulation, regular-season shootouts versus playoff OT,
unavailable data, model-schema mismatch, preservation on source failure,
projection-only record exclusion, exact saved-run replay and mocked Discord.

Use small independent settlement fixtures with known outcomes. Back up before
touching production data. Do not grade or overwrite existing predictions as a
side effect of installation. Show counts of actual ingested games/teams and
one real upcoming fixture forecast, with source provenance and all limitations.
Run focused regressions for the existing basketball and grading workflows.

### Supported CLI — Git Bash

Git Bash, from /c/MultiSportPredict:

```bash
venv/Scripts/python.exe -u msp.py refresh --sport nhl
venv/Scripts/python.exe -u msp.py slate --sport nhl
venv/Scripts/python.exe -u msp.py show --latest
venv/Scripts/python.exe -u run_nhl.py --observations
venv/Scripts/python.exe -u msp.py push --latest
venv/Scripts/python.exe -u grade_predictions.py --auto --report --sport nhl
venv/Scripts/python.exe -u grade_predictions.py --report --sport nhl --push-discord
```

The push commands send externally: preview locally during implementation and do
not execute them merely to test. Verify the latest run is NHL before a user
chooses to push it. Update the existing master Google command reference if its
editor is available, otherwise report that it still needs updating. Do not
create another command-reference Google Doc.

`run_nhl.py --observations` reads the latest ingested official finals and scores
the earliest saved pregame forecast per event. Refresh NHL first to collect new
finals. Winner Brier/log loss and regulation-goal MAE are separate from betting
records and have no profit/ROI claim. The initial Boston–Nashville observation
awaits its October 22, 2026 game; it is not a settled bet.

## Source references

- MoneyPuck downloads and use terms: https://www.moneypuck.com/data.htm
- MoneyPuck model/goalie methodology: https://www.moneypuck.com/about.htm
- NHL odds API and market catalogue: https://the-odds-api.com/sports/nhl-odds.html
- NHL official rules, including overtime: https://media.nhl.com/site/asset/public/ext/2025-26/2025-26Rules.pdf

Verify current-season rules before implementing settlement; the linked rulebook
is a source reference, not an assertion that its edition is the latest.
