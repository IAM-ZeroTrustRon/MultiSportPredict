# MultiSportPredict — shared handoff for Gemini, Claude and Codex

Verified takeover snapshot: **October 24, 2026, America/New_York**. Audit evidence
uses October 25 UTC timestamps because the review ran late on October 24 locally.
This file supersedes conflicting operational claims in earlier chats and handoffs.
Recheck the working tree, database and source freshness at the next session.

## 1. Start here

Project: `C:/MultiSportPredict`. Git Bash: `/c/MultiSportPredict`.
Python: `venv/Scripts/python.exe`. Repository:
https://github.com/IAM-ZeroTrustRon/MultiSportPredict

One assistant edits at a time. Freebuff previously changed many files and staged
five archive renames. The takeover preserved that work. Do not reset, clean,
stash away or commit unrelated changes. This session made no GitHub push and sent
no Discord messages. It did not ingest, retrain, delete picks or regrade the live
ledger. Tests use isolated databases; legacy tests also rewrite sample output files.

Read this file, `STATE_OF_MODEL.md`, `INDEX.md`, `HANDOFF_CLINE.md` and applicable
project/skill instructions. There is no root AGENTS.md at this audit snapshot;
check for any added or nested instructions before future edits.

The shared handoff is this document. Agent-specific starting prompts are:
- `docs/GEMINI_START_HERE.md`
- `docs/CLAUDE_START_HERE.md`

The user also has Gemini Notebook and Google Drive command guides. Those are
external copies: reading this local file does not update them. This takeover did
not read or change the notebook or Google Drive documents. If an assistant has no
filesystem tools, attach this handoff and the requested source files; do not assume
that a project path, screenshot or prior chat gives it live access.

## 2. Product and user expectations

MultiSportPredict is a value-handicapping research system: compare a model's
probabilities/distributions with offered bookmaker prices and identify potential
positive expected value. Picking a likely winner alone is not its objective.
No component places wagers. Tests passing is evidence of software behavior, not
predictive accuracy, calibration, profitability or verified execution at a book.

The user wants exact copyable Git Bash commands, complete real examples, readable
Home/Away and Over/Under labels, percentages rather than floating-point trails,
and automated schedules, data, odds and grading. Avoid placeholders and repeated
manual entry. When no source exists, explain the missing coverage specifically;
never invent prices, metrics, player identities or confirmed starting goalies.

Do not hide legitimate PASS/INFO or calibration warnings. Fix their cause where
possible. Keep research observations, model recommendations, delivered messages
and actual wagers distinct. Never send a message or publish solely because a
prediction was run. Give concise progress updates and honest limitations.

## 3. What the takeover verified and repaired

Baseline: **246 tests passed; 14 warnings; 9 subtests**. All 14 warnings come from
legacy tests returning booleans: pytest can report those tests as passed even if
they return False. Do not translate this count into a blanket correctness claim.
The baseline was followed by 103 passing focused regression tests after repairs.
Final full suite: **274 passed, 14 existing warnings, 9 subtests** (28 new regression cases).
Compilation and diff checks passed. Every production table compared equal to the
pre-repair SQLite backup. See `docs/TAKEOVER_AUDIT_2026-10-24.md`.

### A. Power de-vig solver — repaired

`core/market_handicapper.py::devig_power` previously searched only exponents in
[1,10]. An underround +120/+120 pair returned 45.45% + 45.45%, totaling 90.91%.
Some extreme overrounds require exponents above 10 as well.

The solver now validates finite probabilities strictly between 0 and 1, brackets
from exponent zero, expands its upper bound, and raises if convergence fails.
It solves the actual power equation rather than silently normalizing an invalid
answer. The symmetric underround now returns 50% / 50% within solver tolerance.

EV remains based on model probability versus the offered price. De-vigged market
probabilities are a comparison, not automatically the model's true probabilities.
This repair does not rewrite old forecasts, settlements or staking history.

### B. Manual basketball/NCAAF prices through msp — repaired

`msp_workflow.run_command` previously added --odds even when manual --moneyline,
--spread or --total prices were supplied. The runner correctly rejected this
combination, including the user's Knicks–Celtics command.

It now omits implicit --odds for manual score-market inputs and adds it once for
automatic runs. An explicitly conflicting user request remains a runner error.
Both basketball and NCAAF are covered; NHL's existing automatic path is unchanged.
No sport model, probability, threshold or fixture guard was loosened.

### C. Weighted record price provenance — repaired

`grade_predictions.py::stake_weighted_breakdown` previously accepted a stored stake
and numeric P/L without verifying recorded-price settlement provenance. It could
count assumed-price returns as quarter-Kelly performance.

Flat and weighted reporting now share `_recorded_price_row` validation, requiring
`_settled_at_recorded_price is True`, valid original settlement odds and finite
P/L. Newest-per-fixture selection happens before filtering, so a newer unverified
row cannot resurrect an older verified one. Weighted reporting separately counts
`excluded_without_stake`, `excluded_unverified_settlement` and `excluded_total`.
The historical flat record remains intact. No retroactive stakes were fabricated.

Regression coverage: `tests/test_takeover_repairs.py` tests both exponent ranges,
invalid input, solver failure, manual/automatic routing and weighted provenance.

## 4. Current architecture and file map

`msp.py` is the supported shell; `msp_workflow.py` orchestrates refresh, run/slate,
immutable saved run review, explicit delivery, grading, records and cleanup.
Subprocesses use the project interpreter and argument arrays rather than a shell.

Main runners:
- `run_nhl.py`: NHL benchmark and observation reporting.
- `run_ncaaf.py`: shared NCAAF and domestic score-runner implementation.
- `run_basketball.py`: basketball routing; also connects international engines.
- `run_nfl.py`, `run_mlb.py` (MLB/KBO), `run_tennis.py`.
- `run_tennis_full.py`: Challenger research path; separate from ordinary bets.
- `universal_runner.py` and `predict_match.py`: still-live soccer/baseball paths.
- `run_table_tennis.py`, `train_table_tennis.py`, `grade_table_tennis.py` and
  `table_tennis/`: point-score research workflow with source/identity guards.

Shared infrastructure:
- `core/historical_storage.py`: one canonical SQLite storage implementation.
- `grade_predictions.py`: final-source matching, settlement and reporting.
- `models/score_ratings.py`: score baseline and market pricing.
- `core/market_handicapper.py`: odds math, de-vig and fractional Kelly utilities.
- `sports_feed.py`: shared source/time/cache helpers.
- `live_odds.py`: configured odds API discovery and event-market extraction.
- `score_odds.py`: paired quotes for score runners; NHL settlement/freshness checks.
- `score_review.py`, `nhl_review.py`, `embed_builder.py`: shared presentation.

Local state: `data/`, `output/`, caches, artifacts, backups and root
`multisport_history.db`. These are mostly ignored, but some legacy sample outputs
are tracked. A Git clone is not a copy of local data, credentials or model files.
Preserve any files needed to reproduce or recover the current run.

## 5. NHL implementation: verified capabilities

Files: `nhl_sources.py`, `ingest_nhl.py`, `ingest/nhl_api_fetcher.py`,
`features/nhl_features.py`, `models/nhl_model.py`, `train_nhl.py`, `run_nhl.py`,
`nhl_review.py`, `nhl_observations.py`, `tests/test_nhl_engine.py`.
Original specification/history: `docs/NHL_COPILOT_HANDOFF.md`.

Sources: official NHL API fixture/result identities and published MoneyPuck CSVs.
MoneyPuck expected goals are model estimates. Preserve attribution/source terms.
No browser scraping is needed for this pipeline. Raw downloads have manifests,
retrieval times and hashes. Bad downloads preserve the previous cache.

MoneyPuck joins require official game ID, team abbreviation, home/away side,
season and date. Each completed joined game requires exactly two team records
for each 5on5, 5on4 and 4on5 situation; partial/duplicated joins fail closed.

Features per side (23 total including one difference):
- 5-on-5 xGF/60, xGA/60, xG share, Corsi share, high-danger shot share,
  team save percentage and exposure minutes.
- Published 5-on-4 goals/60 and 4-on-5 goals-against/60.
- Back-to-back flag, games in the prior seven days, plus rest difference.
- Up to 40 prior advanced-stat games, minimum eight, from the retained history.
- Target-day/future games excluded conservatively; no current full-season
  aggregate is attached to historical training fixtures.

Feature version: `nhl-5v5-st-rolling40-prior8-restcap7-v2`.
Model version: `nhl-team-5v5-st-poisson-ot-v2`.
Poisson regulation goals plus a fitted regular-season OT/SO winner component.
Playoff eventual-winner probabilities are unavailable rather than reusing the
regular-season extra-time model. Standard OT/SO-inclusive full-game scopes only;
regulation three-way and period markets are not silently treated as equivalent.

Artifacts: `data/nhl_model.joblib`, `data/nhl_model_metadata.json`.
Data hash, feature version and exact feature schema matched during takeover.
Only load trusted local joblib/pickle artifacts: deserialization is not safe for
untrusted downloaded model files. No comprehensive dependency/security audit or
independent external source revalidation was performed in this takeover.

Cached data snapshot:
- 4,136 fixtures; 2,968 completed results; 2,959 verified advanced joins.
- 2,657 eligible training examples; 2,120 training / 537 chronological holdout.
- Holdout boundary: 2026-03-02.
- Goal deviance 1.062471 versus 1.100603 baseline.
- Winner Brier 0.237525 versus 0.248821 baseline.
- Goal dispersion 0.982838 / 1.000045; operational upper bound 1.5.

Do not repeat the prior handoff's blanket claim that all metrics improved:
previous goal deviance 1.0605 is slightly LOWER/better than 1.0625. The current
fit beats its baseline but that comparison is not evidence of profitable odds.
Current MoneyPuck historical revisions are not archived contemporaneous features.
There is no historical no-vig bookmaker benchmark and no measured historical CLV.

Readiness: both teams need 10 current-season games under a provisional policy;
benchmark/dispersion gates also apply. Missing confirmed goalie context suppresses
EV/picks/staking. Optional --goalies-file validates user-supplied game/team/player
IDs, confirmation, HTTPS sources and timestamps, but DOES NOT independently check
the identity against a roster or fit a goalie-strength effect. Do not describe
this as automated confirmed-starter discovery or goalie-adjusted modeling.

Cached real-fixture smoke: Florida Panthers at Chicago Blackhawks, 2026-10-25,
official game 2026020180. Counts home 10 / away 11; unconfirmed goalies correctly
kept EV and stake null. This was an in-memory forecast from local cached sources,
not a live source refresh or a newly stored bet.

Forward observation report: one unique original pregame fixture scored, winner
Brier 0.224309, log loss 0.641718, regulation team-goal MAE 2.880048. This is FAR
TOO SMALL to establish accuracy. Three NHL market rows represent that one fixture,
not three independent forecasts or wagers. Earliest pregame forecast counts once.

## 6. Staking: what actually is and is not wired

`price_market` returns power de-vig comparison probabilities, model EV, a LEAN
threshold of 5% EV, and quarter-Kelly stakes capped at 5% of bankroll per selection.
Stakes are unavailable for markets with push mass, undefined probabilities,
unpriced/below-threshold selections or observation-only markets. A push-aware
Kelly formulation is not implemented; do not silently apply binary Kelly there.

`predictions.stake_size REAL` exists. `init_db` migrates older schemas; storage
forwards values on insert and overwrite. The live ledger has ZERO non-null stakes
at this snapshot. The screenshot's 0.08 staked / 68.75% ROI was an example/test,
not the live record. Never backfill old rows with present-day suggested stakes.

NHL, NCAAF and score-runner basketball persist stakes via `run_ncaaf.store`.
EuroLeague's shared store path is connected. Tennis computes moneyline pricing
through `price_market` but its main storage path does NOT yet forward stakes.
Soccer, MLB and the standalone basketball path likewise lack complete sizing
integration. A shared helper's existence does not prove end-to-end persistence.

There is no aggregate portfolio exposure cap or correlation-aware allocation
across alternative lines, same-game markets or simultaneous games. Five percent
per selection does not mean five percent maximum combined risk. These are
uncalibrated model suggestions, not an established bankroll-management service.

## 7. Ledger and performance snapshot

Live database quick_check: OK. Total prediction rows: 889.
Sport counts: NFL 219, baseball 208, NCAAF 173, soccer 140, tennis 92,
basketball 54, NHL 3. Workflow runs 26; delivery receipts 0; TT runs 18 / grades 0.
Zero receipts does not prove no historical Discord messages were sent elsewhere.

All-time selected settled ordinary model record:
- 384 selections: 183 wins, 198 losses, 3 pushes; 48.0315% win rate excluding pushes.
- Recorded-price subset: 243; 114 wins, 127 losses, 2 pushes.
- Simulated flat-stake profit +18.2858 units; ROI +7.5250% including pushes in risk.
- 141 settled selections excluded from priced ROI for missing/invalid provenance.
- Weighted Kelly record: 0 eligible selections; ROI unavailable, not zero profit
  proven on an invested bankroll. Historical stakes remain NULL.
- 29 active ordinary selections awaiting results, after relevant exclusions and
  duplicate handling; 18 pending TT runs. Raw NULL-result row counts include
  PASS/INFO and are NOT the actionable pending backlog.

Recorded-price sport breakdown:
- Basketball: 3 selections, -1.1667 units, -38.89% ROI.
- NCAAF: 135, -3.1793 units, -2.3550% ROI.
- NFL: 74, +7.0946 units, +9.5873% ROI.
- Tennis: 31, +15.5372 units, +50.12% ROI.

These are model-ledger returns based on stored settlement metadata, not audited
sportsbook execution. Prior cleanup deleted unresolved historical records after
backup; selection bias remains. Do not describe the retained record as a complete
unbiased live betting history. Gemini's 240 selections/+8.11% was an older snapshot.
Recompute with `msp.py record --all-time` before publishing new performance claims.

Earlier October 19 cleanup and exact manifests remain under output/backups and
workflow-upgrade folders. Do not repeat deletion against the 18 TT runs currently
present just because an older chat authorized a prior historical cleanup.

## 8. Other confirmed work and unresolved issues

### NBA / NCAAB
Home/Away labels, named teams, original prices, signed two-decimal EV percentages,
one-decimal probabilities and readable RMSE are implemented. NBA needs 10 and
NCAAB 8 valid current-season completed games for betting eligibility; prior-year
results do not qualify a new roster's count. Observation rows persist as INFO.
NBA 1H share .495 and 1Q share .245 produce provisional score MEANS only. They are
not period variance models, probabilities, EV or recommended period bets. Merely
fetching 1H/1Q quotes does not establish calibrated period distributions.

### Soccer
The confirmed fixture checker defects in fixture_guard.py remain open: no requested
date parameter, fragile substring/accent matching, positional competitor handling,
and unknown-league fallback to eng.1. The Oct 23 Stuttgart–Gladbach failure was
not proof that the match was absent. Repair verification, never bypass it.
BTTS exists in some model/odds/presentation components, but the active soccer path
needs an end-to-end audit and consistent Yes/No probability/price/EV output.
An unpriced BTTS probability must not produce a fabricated edge.

Belgium, Sweden, Norway and Estonia are only partially configured. Old FBref
importer entries/model presets are not complete operational coverage. Active
soccer refresh uses ESPN plus Football Data for England/Germany/Spain/France/Italy.
Football Data lists Belgium/Sweden/Norway results; Estonia needs a verified source.
Full integration also requires aliases, fixtures, odds, grading and readiness.
Keep domestic and UEFA records separate and goal-derived data distinct from xG.
Champions League/Nations samples were thin; Europa/Conference had no records in
an earlier audit. Recheck coverage rather than repeating old counts as current.

### Tennis
Automatic odds are attempted through live_odds.py/The Odds API, with tournament
key discovery, paired event markets and a cache. Why Osaka Li–Tagger returned
unpriced PASS was not conclusively diagnosed. Check API entitlement, tournament
availability, date/timezone, names, freshness and actual returned markets.
Do not assume a public sportsbook page is present in the configured API feed.
Add source-specific permitted fallback only after verifying availability.

The user supplied manual ML, game/set spreads and alternate full-game totals.
Flags support --p1-ml, --p2-ml and repeated --games-spread/--sets-spread/
--games-total/--sets-total, each latter flag with MATCH_NUMBER LINE PRICE_A PRICE_B.
Spreads apply to the first supplied player; totals use over/under. No checked
first-set winner/first-set-total flags. Do not invent them.
Debru/Rybakov were missing from the registry in the prior inspection. The user
withdrew the import request: no player import/registry tampering was performed.
A name-only registry entry cannot establish player history or forecast quality.

### Table tennis, MLB and legacy paths
TT full point-score collection and cross-provider identity remain fragile.
Do not grade totals/handicaps from only a match winner. No recurring deletion.
MLB official-player/Savant integration exists; do not lose ID-based joins.
Legacy defaults, synthetic soccer shots-prop training, unsafe untrusted artifact
loading and old boolean-return tests remain limitations. No malicious-code-free
certification or exhaustive source/dependency review is claimed.

### Cleanup and documentation
Freebuff moved 227 files locally; five tracked archive renames remain staged.
The archive holds ignored backups too: Git history alone cannot restore all of it.
Do not run cleanup_repo.py --apply: its entrypoint keep-set omits live runners.
A 43 MB untracked methodology audio file remains at root and was not published.
Old ARCHITECTURE and handoff sections contain stale claims. Use this current
handoff first; preserve the old files as dated history, not fresh instructions.
One inaccurate old claim is "nothing deletes history": explicit backed-up cleanup
exists. Another is "all stored timestamps are aware UTC": legacy storage uses
naive local datetime.now(), while newer NHL source times are timezone-aware.

## 9. Working commands — Git Bash

```bash
cd /c/MultiSportPredict
git status --short
venv/Scripts/python.exe -u msp.py record --all-time
venv/Scripts/python.exe -u msp.py pending
venv/Scripts/python.exe -u run_nhl.py --observations
venv/Scripts/python.exe -m pytest tests/test_nhl_engine.py tests/test_takeover_repairs.py -q
```

Refresh and grade (these perform network/data/database work; take backups first):
```bash
venv/Scripts/python.exe -u msp.py refresh --sport nhl
venv/Scripts/python.exe -u msp.py refresh --all
venv/Scripts/python.exe -u msp.py grade --all
venv/Scripts/python.exe -u msp.py daily --all
```
A refresh stage failure is not a successful complete refresh. Read stage logs.
`daily` may train/cache models and consume provider API allowance. No refresh was
performed in this audit. Historical hourly grading automation was configured in
an earlier session; its present scheduler state was NOT reverified here.

Dated cached fixture example; not a perpetual current slate:
```bash
venv/Scripts/python.exe -u run_nhl.py --date 2026-10-25 --match "Chicago Blackhawks vs Florida Panthers" --odds --dry-run
```
This needs fresh local data/model and a still-upcoming fixture. --dry-run avoids
prediction ledger writes but odds lookup can use cache/API credits. Do not backdate
a completed game as a fresh pick. The user-facing matchup is home first for this
NHL example. Actual soccer home/away must always be verified by event fields.

The previously failing basketball manual-price structure now routes correctly:
```bash
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --match "Boston Celtics vs New York Knicks" --date 2026-10-23 --moneyline -142 120 --spread -2.5 -110 -110 --total 221.5 -110 -110 --total 223.5 -110 -110
```
That is a HISTORICAL syntax example. Do not run it after October 23 as a new bet.
Use actual upcoming fixtures/current paired quotes; do not change an old game's
date just to pass validation. Existing msp guards refuse historical forecasts.

Saved review:
```bash
venv/Scripts/python.exe -u msp.py show --latest
venv/Scripts/python.exe -u msp.py show --latest --json
```
Check the saved sport, fixture and run ID before any explicit delivery. Nothing
in this handoff authorizes an automatic push. Use --run-id when precision matters.

## 10. Recovery and verification evidence

Takeover backup/snapshot folder:
`output/takeover_audit/20261025T035246Z/`
- `history_before.sqlite`: SQLite-consistent backup of the canonical database.
- `before/`: exact pre-repair versions of affected existing code/documents.
- `working_tree_before.txt`: pre-existing changes and staged archive moves.
- `audit_snapshot.json`: machine-readable counts, record, NHL metrics and pending IDs.
- Additional verification results are written beside these files.

Only one canonical active database: multisport_history.db. Backup snapshots and
temporary test databases are not alternative production stores. Preserve secrets
in local configuration; never copy .env values into a handoff, notebook or commit.

At takeover HEAD: `18a5cab3ec8bcbc960e5467785d2bd068f8a15c5`. Earlier chat commit
IDs differed; this is the observed local checkout, not proof of remote alignment.
No commit or push was made. Verify branch/remotes/logs before publishing.

## 11. Next work, with honest boundaries

1. Repair soccer fixture dates/identity/unknown-league behavior, with recorded
   source payload tests; then connect consistent priced BTTS review.
2. Diagnose actual tennis missing-odds traces and build specific failure messages.
3. Complete Belgium/Sweden/Norway/Estonia ingestion-to-grading integration.
4. Unify staking only after each market's selection probability, price, push rules,
   recommendation and persistence path are proved. Include tennis's missing store
   forwarding and portfolio/correlation limits. Never backfill historical stakes.
5. Improve NHL automatic confirmed-starter verification and separately validate
   goalie-strength inputs; archive prospective quotes/calibration/market benchmarks.
   Review the current <24-hour back-to-back definition against calendar-day hockey
   semantics, missing partial PP/PK history handling, source-cache schema validation,
   historical team relocations and seasonal schedule coverage before broadening use.
6. Add calibrated basketball period models and period odds only as a separate,
   validated feature; fixed full-game fractions are not enough.
7. Replace boolean-return legacy tests with assertions and isolate their outputs.
8. Update stale architecture docs/cleanup keep-set and external command guides.

These are open tasks, not work completed in this takeover. Prioritize one bounded
change at a time, follow required plan approval, add tests that catch the actual
failure, and update this file with verified outcomes before handing off again.
