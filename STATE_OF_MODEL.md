## NBA player-prop research, phase 1 — October 26, 2026

`msp.py run --sport basketball --props` produces player research projections for
NBA only. It writes no team pick, no prediction row and nothing into the value
ledger. It emits no cover probability, no expected value, no stake, no probability
flag and no recommendation: those need real bookmaker prop prices and a
distribution assumption, and this phase has neither.

Source is ESPN public box scores, one request per finished game. That endpoint was
chosen because it is the only permitted source verified to return starter status,
a did-not-play flag with a reason, minutes, PTS/REB/AST and overtime periods
together. A player game log was rejected for this job: it omits non-appearances and
has no starter flag, so a DNP and a 0-point game cannot be told apart. RealGM is
**not** scraped; no verified permission for automated retrieval was established, so
it remains a manual research reference and is never claimed as a row's source.

A DNP, a listed zero-minute appearance and missing data are three different things
and stay different in storage and in the features. Absence from a box-score roster
block is not treated as zero production.

Loaded history at verification: 139 completed games, 3,764 player-games
(3,033 appearances, 731 DNPs), 584 players, 3 overtime games, dates
2026-04-01 to 2026-10-25.

Minutes are projected by one of two paths. The default is a transparent
recent-rotation baseline: the mean of the last 10 appearances, falling back to 5,
then 20, then the season mean. The optional `--minutes-model candidate` fits a
least-squares map from nested 5/10/20 window means, season mean and starter
frequency, using stored history strictly before the forecast date, and prints its
coefficients.

Season identity comes from the feed's `header.season`, never a calendar year: April
2026 games are season `2025-26` and October 2026 games are `2026-27`. A calendar
year merged those two seasons into one and is no longer used. History from a
previous season, or older than the declared `STALE_ROTATION_DAYS = 30`, is flagged
`STALE` and `CROSS-SEASON` in the output rather than silently trusted.

Chronological validation (cutoff 2026-04-12; 10 train dates / 2,188 player-games,
7 test dates / 1,576 player-games). Two different questions are reported
separately and are never merged into one score.

**Played-game accuracy** (conditional on the player appearing, n=935):

| minutes model | MAE | bias | RMSE |
|---|---|---|---|
| recent-rotation baseline | 6.80 | +0.68 | 9.10 |
| fitted candidate | 6.76 | +1.41 | 8.78 |

**Participation**: 1,115 projectable player-games, 935 appeared (including 2 listed
with zero minutes), 179 did not play, 1 unverified and excluded from all error
blocks, 1,114 confirmed for scoring, appearance rate 83.9%.

Postgame rows are classified three ways before any error is computed: a confirmed
appearance (a zero-minute appearance is a real appearance), a confirmed
did-not-play (observed as zero minutes), and unverified. An unverified row is
excluded from every error block rather than zero-filled, because scoring an
unobserved game as 0.0 minutes invents a miss the model never made.

**Participation-inclusive** (a confirmed did-not-play counts as zero minutes; the
harder and less flattering number, n=1,114):

| minutes model | MAE | bias | RMSE |
|---|---|---|---|
| recent-rotation baseline | 8.59 | +3.45 | 11.63 |
| fitted candidate | 8.89 | +4.40 | 11.71 |

Stat misses by variant (n=935), baseline vs candidate: points 5.84 vs 5.86,
rebounds 2.13 vs 2.17, assists 1.69 vs 1.70, PRA 7.90 vs 7.89, PA 6.70 vs 6.70,
RA 3.23 vs 3.26. The candidate matches or loses on every stat except PRA, where it
is 0.01 better while its combo bias is worse (1.55 vs 1.09).

**The candidate does not earn adoption.** Conditional on playing it is 0.04 minutes
better on MAE, but it loses the participation-inclusive comparison outright
(8.89 vs 8.59) and raises bias from +0.68 to +1.41 minutes. Because it is nested
on collinear window means, its practical effect is a systematic overprojection,
not a better rotation estimate. The baseline stays the default and the candidate
is opt-in only. No accuracy improvement is claimed for props in general, and a
conditional MAE is not evidence of useful projections.

Availability gates a projection and is read only from the exact fixture's own
payload (`basketball_availability.py`). The league-wide injuries feed is no longer
used at all: its `timestamp` answered whether an unrelated page was current, not
whether this game's availability data was, so it could stamp a stale fixture block
as fresh. Freshness now comes from the event's own data — the snapshot's retrieval
stamp, re-checked on every read so a saved snapshot expires after
`MAX_SNAPSHOT_AGE_HOURS = 6`, plus each designation's own `date`.

Event identity is verified before any designation is trusted: the requested event
id must appear on the payload, both competing teams must be named, and each
designation's team must be one of those two. A designation dated in the future is
corrupt and is rejected. An old designation (a player ruled out in September) is
**disclosed, not deleted** — deleting it would silently turn a known absence into
unknown. Every rejected designation is listed with its reason. A network failure or
unverifiable identity yields **no** designations, never "available"; a player absent
from a fresh report stays UNKNOWN, because not being listed is not proof of fitness.

Availability is a closed set. Only `AVAILABLE`, `ACTIVE` or `CLEARED` are ever
actionable; an unrecognised string — including prose such as `REPORT NOT SUBMITTED`
— stays UNKNOWN and non-actionable. OUT, DOUBTFUL and suspension designations are
refused outright and a refused player displays `--` for every projection.
`DAY-TO-DAY` is treated as uncertain, not available. A verified minutes restriction
may cap a projection and the cap is disclosed. Missing values render as `--`, never
as `0.0`. Minutes include overtime and are not adjusted for it.

Before projecting, the fixture must pass a date, kickoff and status check: only a
scheduled game whose Eastern kickoff matches the requested date and has not yet
started can be projected.

Combos (PRA, PA, RA) are sums of component means. That is exact for means and says
nothing about spread; no independence between components is assumed and no combo
uncertainty is reported.

Separately, `--dry-run` through `msp.py run` no longer records a failed run. A dry
run saves nothing by design, so it is now stamped `preview`; only a nonzero exit or
a missing artifact on a real run is a failure.

## Basketball resolution and explicit hybrid fallback — October 26, 2026

`msp.py run --sport basketball` now normalizes competition names and routes
Australian `NBL` separately from New Zealand `NZNBL`. Australian history comes
from the verified ESPN `/basketball/nbl` registry/schedule endpoint (10 teams,
504 fixtures, 382 finals ingested during verification). `mens-australian-nbl`
is not a working endpoint. The New Zealand Breakers belong to Australian NBL.

For named basketball matches: use competition-scoped local history; when the
fixture/team history is missing, insufficient or stale, attempt one supported
public refresh and reload the persisted cache. Supported adapters are ESPN
NBA/WNBA/NCAAB/NCAAW/NBL and official KBL/NZNBL/BBL. Unknown competitions have no
invented adapter. EuroLeague's existing normal CLI remains available.

Add `--exploratory` to authorize hybrid observations when a verified forecast
remains unavailable. This flag is permission for fallback, not a command to
replace an eligible normal forecast. Preserve pre-cutoff current-season scoring
averages and usable measured pace/ORtg/DRtg; substitute only absent inputs.
Undated templates and other competitions' namesakes cannot supply measured rates.
Each substituted input, source, fixture status and venue assumption is displayed.
Unknown fixtures use the user-supplied first team as assumed home, explicitly
unverified. Completed, in-play, postponed and canceled known fixtures remain refused.

Exploratory distributions use assumed uncertainty. Any displayed prices/EV are
SCENARIOS, not calibrated betting recommendations; stakes stay NULL and rows are
INFO observations. HIGH MODEL PROBABILITY (75%+) is separately labeled as an
exploratory scenario. No new calibration, Kelly formula or betting threshold.
`cohort=EXPLORATORY` and `is_exploratory=1` quarantine these observations, including
storage identity and grading dedup. Ordinary price/weighted reports exclude them
before dedup. `msp.py record --cohort exploratory` reports them separately.
Schema migration is additive on the next normal storage init; no historical
results were changed during implementation. Review/backup/handoff evidence is
local under `output/basketball_resolution/`. Soccer cascade/props are future work.

## Odds capture unblocked, audit handoff — October 26, 2026

Two bounded live tests were run on real NHL fixtures. Prediction capture is now
proven live: six rows across games 2026020183 and 2026020184, both FanDuel, both
observed prematch, each carrying the provider event ID, official fixture ID, run
ID and the bookmaker's own quote timestamp. Collection was refused both times:
the provider mirrored kickoff exactly 600s late (measured on 2026020184 as
02:10:00Z against the league's 02:00:00Z), and the earlier strict-equality guard
turned that mirror into a hard block on every NHL close.

The guard was relaxed in one direction only. A provider kickoff later than the
league's is tolerated up to 15 minutes, the storage deadline becomes
min(official, provider) so the league time still binds, and a provider kickoff
EARLIER than the league's is always refused. No capture can now land later than
the league's own kickoff. Quota spend for the two tests: 6 credits (388 -> 394
used, 106 remaining).

No closing row exists yet, so closing-line value remains unavailable rather than
zero. A live close on the next eligible fixture is the outstanding proof. No
scheduler, no hand-inserted snapshot, no model or Kelly change. Full contract and
status: docs/ODDS_CLV_HANDOFF.md.

## Task 2 odds audit repairs — October 25, 2026

The existing Freebuff snapshot pipeline has been tightened locally. Closing
collection now gates on tracked predictions, original bookmaker and a fresh
official scheduled fixture before a paid request. Defaults are 30-to-1 minutes
before kickoff and a five-minute provider quote age. Closing rows require a
bookmaker update timestamp; repeats of the same publication are idempotent.
Prediction payloads retain run/official ID, period, selections and odds format.
No new live schema change or history rewrite was needed in this repair.

CLV now matches event, teams, bookmaker, league, market, period and settlement
scope, and reports kickoff changes as unavailable. It uses the latest eligible
reference rather than an older matching line; line movement stays separate.
Each run remains an observation, not an independent wager. Fair-price CLV uses
the same bookmaker's de-vigged reference, not a claimed market consensus.
Quota headers are available for collector requests without exposing credentials.

No scheduler, paid odds request, live capture, Git commit or push was performed
by the repair audit. A direct Freebuff live-test prompt and identical Gemini/
Claude update are local under output/task2_codex_review/. Soccer/MLB/KBO/NFL/
tennis/TT capture remains unsupported; EuroLeague may lack required provenance.
See docs/ODDS_CLV_SCHEDULER_PROPOSAL.md for the actual operational contract.

> Task 1 review follow-up: CLI UTF-8 output and missing-date usage are fixed;
> 46 soccer/CLI regressions and 320 total tests pass (14 existing warnings).
> The October 30 Elversberg–Mainz card is Bundesliga, confirmed by the club.
> Task 1 passed final external review and is approved for local integration.

## Soccer fixture guard repair — October 25, 2026

Dated soccer verification now queries the explicit ESPN competition/date, checks
actual timezone-aware kickoff against America/New_York, matches normalized exact
published names or explicit Bundesliga aliases, and uses homeAway fields rather
than competitor order. Unknown/missing leagues, malformed dates/identities,
postponed cards, ambiguous aliases and multiple matching cards fail closed.
The existing (valid, message, orientation) interface is retained.

universal_runner.run_soccer consumes reversed orientation before stats or odds:
team ML and handicap prices swap, the signed handicap reverses, and totals/draw
prices remain unchanged. The verified home/away, date, kickoff and event ID print
before prediction. msp.py already supplies game_date and needs no change.
Legacy undated direct calls keep their prior behavior; this check verifies fixture
identity, not a new prematch/readiness policy. Model equations, Kelly and betting
thresholds are untouched. No odds-snapshot scheduler or BTTS change is included.

Recorded ESPN regression fixtures include Stuttgart–Gladbach on October 23 and
the October 25 Bundesliga board, with capture URL/time/hash. A live October 30
SV Elversberg–Mainz card verified both orientations and rejected an invented
opponent. tests/test_soccer_fixture_guard.py covers the guard and caller mapping.
No live prediction or grade was stored; backups and the local review diff are
under output/soccer_fixture_repair/. These changes passed final external diff review.
Local integration is approved; GitHub publication remains a separate action.

## Verified takeover corrections — October 24, 2026

The takeover preserved
Freebuff's NHL/sizing work and staged archive moves. Power de-vig now brackets
underround and extreme overround markets correctly; the shared NBA/NCAAF wrapper
no longer adds automatic odds to manually priced requests. Weighted Kelly returns
now require the same recorded-price settlement provenance as the flat report.
No live predictions, grades, historical stakes or source models were rewritten.

Verified database snapshot: 889 predictions, integrity OK. Selected all-time record
384 (183W/198L/3P); recorded-price subset 243 (114W/127L/2P), +18.2858 simulated
flat units, +7.5250% ROI. 141 unknown-price settlements excluded. No non-null Kelly
stakes exist yet; weighted ROI is unavailable. 29 ordinary selections and 18 TT
runs await results; 0 TT grades. These are ledger records, not verified wagers,
and historical unresolved-record deletions introduce selection bias.

NHL cached feature/artifact hashes and schema agree; 537-game holdout beats its
baseline but does not establish betting calibration. One prospective event was
scored, which is insufficient for accuracy claims. A cached real-fixture forecast
correctly suppressed EV/staking for unconfirmed goalies despite sufficient game
counts. Tennis computes shared moneyline sizing but does not persist its stake;
soccer/MLB/standalone basketball likewise remain incomplete. No GitHub push or
Discord send occurred; no external Notebook/Drive guide was updated.

## Dynamic position sizing — October 24, 2026

`models/score_ratings.price_market` now returns three additional fields per
market: `fair_prob_a`/`fair_prob_b` (the bookmaker price pair de-vigged with the
power method) and `stake_size` (a quarter-Kelly fraction of bankroll, capped at
5%). The fair probabilities are a market benchmark only. EV and the 5% LEAN gate
still use the model probability against the offered price: pricing the market
against its own de-vigged probability returns roughly minus the book's margin
and would never recommend anything, so it is not used for EV or sizing.

`stake_size` is the recommended side's fraction, computed with
`core.market_handicapper.kelly_stake_fraction` on the model probability and the
offered decimal price. It is `None` — never an invented number — when there is
no +5% EV pick, a price is missing, the line carries push mass (an integer line
is not a binary settlement), or the row is projection-only. The value persists
in `predictions.stake_size`, added by `core.historical_storage.init_db`
migration; `store_prediction` accepts it as a keyword and `run_ncaaf.store`
forwards it for NHL, NCAAF and every basketball path.

`msp.py record` adds `quarter_kelly_decisions`, which weights each saved one-unit
P/L by its stored stake against a fixed notional bankroll and reports total
staked units and ROI. Rows saved before this change store no stake and are
counted as excluded rather than defaulted to one unit; the flat
`recorded_price_model_decisions` block is unchanged for continuity. This is not
compounding and not a confirmed wager.

## NHL team benchmark and workflow — October 21, 2026

NHL is routed through msp.py refresh/run/slate/show/push and the canonical
database, not a separate dispatcher or ledger. Official NHL game IDs, season IDs,
finishing phases and final scores join published MoneyPuck 5-on-5 rows by exact
game, team abbreviation, home/away orientation, season and date. Raw CSVs and
retrieval/hash manifests are retained; failed downloads do not replace good
caches. Zero-exposure rows are excluded rather than divided or imputed.

Pregame features use the last 40 earlier completed advanced-stat games, with
at least eight historical games and explicit current-season counts. Same-day
and future games are excluded; prior seasons are legitimate training history.
The 5-on-5 inputs are xGF/60, xGA/60, xG share, Corsi share, high-danger shot
share, exposure minutes and team save rate; special teams add power-play goals
per 60 from published 5-on-4 rows and penalty-kill goals against per 60 from
4-on-5 rows; rest includes days between starts, back-to-back status and games
played in the prior seven days. Zero-exposure rows contribute no rate and are
never divided or imputed. The team model fits regulation Poisson scoring rates
and a separate regular-season OT/SO winner model on regulation ties. Playoff OT does not reuse that
component. Official final distributions preserve truncated tail error and handle
integer-line pushes. Regulation three-way prices are not treated as two-way ML.

Initial verified import: 4,136 fixtures, 2,945 finals, 2,942 advanced joins. Initial
fit: 2,634 pregame examples, 533 chronological holdout games; goal deviance
1.0605 vs 1.0944 baseline, winner Brier 0.2399 vs 0.2489 baseline. These are
historical reconstructed results, not forward-tested betting profitability.

The October 24 special-teams extension refetched the published MoneyPuck rows and
rejoined 5-on-4/4-on-5 situations by official game, team, orientation, season and
date: 4,136 fixtures, 2,968 finals, 2,959 verified joins, 2,657 pregame examples,
537 holdout games; goal deviance 1.0625 vs 1.1006 baseline, winner Brier 0.2375
vs 0.2488 baseline, goal dispersion 0.98/1.00. Feature and model versions were
bumped, so older artifacts are refused rather than silently reused. The
no-vig market benchmark remains absent: no archived historical NHL quotes exist,
and that field records the reason instead of a fabricated number.

The fitted model is a 5-on-5 TEAM benchmark with team-level special-teams goal
rates. Published goalie snapshots are downloaded, but starting goalies are not
inferred/confirmed and individual goalie skill, injuries and public betting
splits are not fitted. Missing
starter confirmation, insufficient current-season sample (provisional policy
10 games), failed baseline/dispersion checks or unsupported OT scope suppress
EV and recommendations and persist INFO observations outside the betting
record. Optional user-verified goalie context does not invent a numeric goalie
effect. Existing historical selections and grades are not rewritten.

Grading verifies official event IDs and requires explicit full-game OT/SO scope;
ambiguous regulation markets remain ungraded. Saved original quotes and
workflow snapshots can be shown/pushed without rerunning the model. No Discord
messages are sent as part of implementation tests.

The first root-workflow example, Boston–Nashville on October 22, saved three
INFO rows and real paired DraftKings prices in immutable run
msp_86841beb280b48e3b0cc5a6fed75e75e. Current-season counts were Boston 10 and
Nashville 8; starters were unconfirmed, so EV/picks remained disabled. The
read-only `run_nhl.py --observations` report measures original pregame winner
Brier/log loss and regulation-goal MAE once refreshed official finals arrive,
without adding observations to the betting record or claiming simulated ROI.

## Basketball current-season readiness — October 21, 2026

NBA requires 10 and men's NCAAB 8 valid completed current-season games per team
before a new score-runner forecast can expose EV or betting recommendations.
Prior-season history remains in score training unchanged; it does not qualify
a new season's readiness count. Verified fixture season IDs handle 2026–27
across calendar years. Ingestion stores per-season team counters (including
zero-game registry teams); prediction recomputes from distinct eligible finals
before its cutoff, excluding preseason, same-day and future results. Missing
fixture season IDs produce an unknown, projection-only readiness state.

Insufficient samples retain score/probability observations and captured odds,
but null EV/picks in saved payloads and store INFO selections with null edge,
excluded from ordinary grading/records. Terminal and Discord share counts and
the projection-only label and defensively suppress stale recommendations.
Historical saved forecasts are not rewritten. Other leagues and NCAAF keep
their existing behavior; NBA/NCAAB thresholds are observation policies, not
validated accuracy guarantees. NCAA 1H modeling is still a separate task.

## Recorded-price reporting — October 21, 2026

`grade_predictions.py --report` now includes a sport-by-sport recorded-price-only
W-L-P, win rate, units and ROI table. Its Discord formatter adds a separate embed
when explicitly requested with --push-discord. `msp.py record --all-time` shares
the calculation and exposes recorded_price_model_decisions_by_sport. Filtering
occurs after newest-per-fixture deduplication and excludes PASS/INFO/VOID, missing
or malformed settlement provenance, absent/nonfinite odds and missing/nonfinite
P/L. Saved settlement rounding is retained. ROI risks one unit per selection,
including pushes; win rate excludes pushes. This is a model record, not proof of
wagers or independently verified sportsbook prices. Legacy reports retain their
assumed-price sections, labeled separately in Discord. No grades were changed.

## NBA review polish — October 20, 2026

Score-runner terminal, saved review and Discord formatting now share named Home/Away or Over/Under labels, original American prices, one-decimal probabilities and signed two-decimal EV percentages. Raw full-game values and grading remain unchanged. NBA-only provisional 1H (49.5%) and 1Q (24.5%) score means include totals and model fair spreads derived from displayed team points. They have no period variance, probabilities, EV, betting recommendations or additional graded selections. Existing saved runs are displayed without rewriting their immutable snapshots; --json retains the original numeric payload.

The odds adapter recognizes period quotes when present in the matched bookmaker payload, but does not fetch extra period markets or treat quotes as a calibrated distribution. Full-game market requests remain unchanged. Tested against the exact saved Knicks–Sixers forecast and real NBA training history; full-game projections and market calculations are identical. See docs/NBA_REVIEW.md. No Discord messages were sent.

## Current workflow and record — October 19, 2026

The supported entrypoint is msp.py (see COMMANDS.md). Refresh, run/slate, immutable saved review, explicit delivery, grading and period/all-time records share the canonical database. The local hourly automation now grades all sports and sends no Discord messages; it never deletes records.

Verified result recovery added 31 grades. An integrity-checked backup and exact deletion manifest preceded removal of 47 unresolved historical ordinary rows and 18 table-tennis runs. Two active selections and two excluded reruns for tonight's in-progress SF–Washington event were preserved. A new reporting period begins 2026-10-20; historical settled records remain queryable.

Retained historical model record: 181W–195L–3P, 48.14% excluding pushes. Recorded-price subset: 112W–124L–2P, +20.2397 simulated units, +8.50% simulated ROI on 238 one-unit stakes including pushes. Another 141 historical grades lack confirmed recorded-price settlement. These are model records, not confirmed wagers; unresolved deletions introduce selection bias. See docs/PERFORMANCE_2026-10-19.md rather than presenting these as audited profitability.

MLB player imports share one official MLB Stats API + Baseball Savant schema (649 pitchers, 532 hitters; ambiguous Max Muncy names omitted). France soccer recovered 36 teams with bounded transient retries. Other refresh stages completed. Public table-tennis collection currently reports no readable recent-results page; no complete point-score coverage is claimed.

Review findings and remaining model/security/testing limitations: docs/REPOSITORY_REVIEW_2026-10-19.md. README now describes value handicapping, pricing discrepancies and estimated EV. The update includes curated screenshots under docs/evidence; publication details are in the repository commit history. Earlier notes below describe historical snapshots.

## Table-tennis paste and manual grading repair — 2026-10-11

MyStake clipboard parsing no longer requires the omitted Table Tennis navigation
label when the explicit Czechia/Czech Liga Pro header is present. Full-name tokens
identify participants independently of exact line positions; reordered names and
accents remain supported without fuzzy substitution of different players. Odds
pairing, competition, format, start and price-freshness checks remain enforced.
`run_table_tennis.py` loads optional `current_match_config.json` for the simple
no-argument paste workflow and emits a standalone `RUN_ID=tt_...` after saving.
`grade_table_tennis.py` adds --pending, confirmed --run-id/--scores/--source-url
registration and --import-file. It retains the saved provider IDs, validates legal
points before event updates, backs up SQLite, and grades immutable forecasts.
At diagnosis, all 11 saved runs had scheduled MyStake events; the 3 finished
public events were different IDs, explaining zero grades. No finals were invented.
Regression: tests/test_table_tennis_paste_grading.py, including no-argument CLI,
price mapping, invalid finals, original identity and idempotent grading.

Full sports audit - 2026-10-11

Tennis ESPN result insertion was unreachable beneath the unresolved-name continue; corrected and regression-tested. Final full regrade: 295 graded decisions, including 27 tennis (22 newly settled). All-sport ingestion/audit logs: output/full_audit_20261011/. Public table tennis results unavailable on retry; 10 runs and 80 research selections remain unresolved. Table tennis hourly collection/training/grading heartbeat is active; saved research selections remain separate from placed bets.

Google Docs table-tennis guide — 2026-10-10

Indexed operating guide: https://docs.google.com/document/d/1GFDeYLVTDHfpc4v5dgBB3f7gLOoCBm5mA1fJvG-yBtE/edit
TABLE_TENNIS_COMMANDS.md is its local content copy. Discord Model Notes section removed; terminal observations/warnings and the brief price/model basis remain. Reference lines have no assumed sportsbook price or EV. Manual final-result preparation validates actual complete game scores and retains the exact stored event/player IDs before canonical import/grading; it requires the operator to verify fixture identity from a real source. No Discord sent and no final result was invented/imported.
