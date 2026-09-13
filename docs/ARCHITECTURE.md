# MultiSportPredict — Architecture Reference

**Read this file before writing any new code in this repo — Claude, Gemini,
Cline, Blackbox, Copilot, or human.** Its purpose is narrow: say what
already exists, what's canonical, and what's dead, so nobody re-solves a
problem that's already solved (or worse, half-solved twice, differently).

This doc is a byproduct of a real, repeated failure pattern in this repo:
multiple agents, across multiple sessions, built parallel implementations
of the same thing because nobody checked what was already there first.
`prediction_store.py` was built because `core/historical_storage.py`
wasn't known about. A standalone `tennis_elo.py` was built because
`models/tennis_elo.py` wasn't known about. That pattern is the actual
problem this file exists to stop.

**Rule for every agent, every session:** before creating a new file, grep
the repo for what you're about to build. If something adjacent exists,
extend or fix it — don't add a parallel version "to be safe." If you're
not sure whether something exists, that uncertainty is the signal to
search, not to build.

Last verified: this session, against files the repo owner uploaded directly.
Sections marked **UNVERIFIED** are inferred, not confirmed — check before
trusting them.

---

## 1. Canonical entry point

`predict_match.py` is the real CLI and the actual routing logic for every
sport. It is not legacy — despite the README calling it that, it's the
most functional file in the repo right now.

`universal_runner.py` is the higher-level hub that `run_match.py` and
`auto_mlb_scraper.py` already shell out to (with `--markets`,
`--home-sp-era`, `--store-to-db`, `--push-discord`) — and it **now exists**
(see §5). Both callers' previously broken invocations now resolve; the hub
routes every sport through the canonical predictors and logs to
`core.historical_storage`.

---

## 2. One canonical module per concern — do not build a second one

**Verified via repo-wide import grep this session — not guessed.** For each
concern, exactly one implementation is actually reachable from
`predict_match.py`. The others exist in the repo but have **zero effect**
on real predictions until something wires them in.

| Concern | Canonical (LIVE) file | Confirmed orphaned alternates — do not extend expecting real effect |
|---|---|---|
| Prediction storage + outcome tracking | `core/historical_storage.py` | `prediction_store.py` (built this session, deprecated — see §4) |
| Confidence scoring / bet recommendation | `core/confidence_engine.py` | — |
| Output schema definitions | `core/schemas.py` | **Also orphaned** — nothing imports it. Either wire it in or delete it. |
| Soccer prediction + league calibration | `models/soccer_predictor.py` (`SoccerPredictor`, its own inline `LEAGUE_CONFIGS`) | `MultiSportModel.py`'s `LEAGUE_CONFIGS`; `models/soccer_model.py` (sklearn RF) + `models/soccer_league_config.py` (`LeagueConfig` dataclass) — confirmed orphaned as a pair, since `soccer_league_config.py`'s only importer is the orphaned `soccer_model.py` |
| Basketball prediction | `models/basketball_predictor.py` (`BasketballPredictor`, `fiba_build_full_game()`) | `MultiSportModel.py`'s `eu_build_full_game()` (confirmed: `fiba_build_full_game()` is a manually adapted copy of it, per its own code comment — not a live link, a one-time port); `models/basketball_model.py` (sklearn RF, also depends on a missing `config.py`) |
| Baseball/KBO prediction | `models/baseball_predictor.py` (`BaseballPredictor`) *and* `predict_match.py`'s own `run_baseball_prop_market()` | `models/kbo_model.py` (sklearn RF) — confirmed orphaned. The two baseball paths that ARE live have not been reconciled with each other — still open, see row below. |
| Tennis prediction | `models/tennis_predictor.py` (`predict_tennis_match()`) + `models/tennis_elo.py` (`TennisElo`) | Standalone `tennis_elo.py` and `run_kostyuk_keys_toronto.py` built this session before this was known — see §4 |
| League-specific tuning (soccer) | **Now `models/soccer_predictor.py`'s inline `LEAGUE_CONFIGS`** — extended this session with EPL, La Liga, Bundesliga, Serie A, Ligue 1, 2. Bundesliga, Belgian Pro League, Eredivisie, Eerste Divisie, NPL NSW, Estonian Premium Liiga, EuroLeague, World Cup, `default`. Each entry now also carries a `data_tier` (1/2/3) field per §7 — not yet consumed by `predict()`, just recorded for the fallback-mode work still to come. | `models/soccer_league_config.py`'s `LeagueConfig` system — more structurally developed (dataclass, hyperparameters, feature lists) but orphaned. Worth considering as a future migration target for the live config, but that migration has NOT happened — don't assume the live dict has those richer fields. |
| League-specific tuning (basketball) | **None exists.** `BasketballPredictor.__init__` accepts and stores a `league` string, and it flows into the output dict, but `fiba_build_full_game()` does not branch its formula on league at all — confirmed by reading the function. FIBA-specific adjustments (5-foul disqualification, 40-minute/68-76-possession pace baseline, EuroLeague travel/rest penalties) are real, good suggestions from a previous session but require **new** logic, not an edit to something that already exists. |
| Sport routing / dispatch | `predict_match.py`'s own `main()` | `models/dispatcher.py` — NOT orphaned (it correctly calls the live `SoccerPredictor`/`BasketballPredictor`/`BaseballPredictor` classes and is independently runnable as `python -m models.dispatcher`), but it's a **second, redundant router** duplicating `predict_match.py`'s own routing logic. Decide whether it's meant to be an alternate CLI or should be retired. |
| Real team stats for soccer/basketball | `team_stats_provider.py` (in repo — manual-entry-backed JSON store, see §7) | — |

**The four confirmed-orphaned files now carry an explicit banner at the top
of the file** (`MultiSportModel.py`, `models/soccer_model.py`,
`models/basketball_model.py`, `models/kbo_model.py`,
`models/soccer_league_config.py`) stating they're unreachable and why, so
an agent opening the file directly sees the warning immediately rather than
needing to re-derive it from this doc.

---

## 3. Sport-specific model files — confirmed orphaned, not just suspected

These exist and are real code, but as of this session **confirmed via
repo-wide import grep** to be unreachable from `predict_match.py`:

- `models/soccer_model.py` (`SoccerModel`) — sklearn RandomForest on xG/shots/corners/form, league-aware via `soccer_league_config.py`. **Orphaned.**
- `models/basketball_model.py` (`BasketballModel`) — sklearn RandomForest on per-100-possession metrics. **Orphaned**, and also depends on a `config.py` that wasn't found among the files reviewed — check whether it exists before doing anything with this file.
- `models/kbo_model.py` (`KBOModel`) — sklearn RandomForest, separate from `BaseballPredictor`. **Orphaned.**
- `models/soccer_shots_prop_model.py` (`SoccerShotsPropModel`) — real XGBoost class with save/load and feature importance, **but `load_historical_training_data()` still generates 100% synthetic `np.random` data.** The engineering is solid; the training data is not real. Fix the data source before trusting any output from this model. Reachability from `predict_match.py` not yet checked — verify before assuming it's live.
- `models/referee_features.py` — plain dataclasses (`RefereeStats`, `SoccerRefStats`, `ConsensusSignal`), no logic. Fine as-is, just a data shape. Reachability not checked.
- `models/sharp_predict.py` — **empty stub**, one comment line, no implementation. Either build it or delete it; right now it's a trap for an agent that assumes it does something.

---

## 4. Deprecated — DELETED this session, now redundant

These files have been **removed from the repo**, not just marked deprecated:

| File | Redundant with | Status |
|---|---|---|
| `prediction_store.py` | `core/historical_storage.py` | **DELETED.** `historical_storage.py` stores generic `model_value`/`market_value`, not a raw 0–1 probability — so calibration metrics (Brier score, log-loss) only cleanly apply where `model_value` literally is a probability (moneyline markets). `backtest_report.py` now reads from `historical_storage` and documents this limitation in its docstring. |
| `backtest_report.py` | `core/historical_storage.py` | **REWRITTEN** to read from `core.historical_storage.get_predictions()`. Its calibration logic (Brier/log-loss/reliability table/ROI/CLV) kept; docstring notes Brier/log-loss only apply to moneyline-style rows. |
| `tennis_elo.py` (top-level) | `models/tennis_elo.py` (`TennisElo`, real) | **DELETED.** |
| `run_kostyuk_keys_toronto.py` | `models/tennis_predictor.py` (`predict_tennis_match()`) | **DELETED.** |

---

## 5. Known bugs — fixed this session, NOW LIVE in the repo

1. **Critical — soccer/basketball predictions were identical for every matchup, regardless of teams.** `SoccerPredictor.predict()` and `BasketballPredictor.predict()` accept real stats via `**kwargs` but silently default to hardcoded placeholders (`home_xg_for=1.65` always, `home_ortg=110.0` always) when not supplied. `predict_match.py`'s `run_soccer_game()`/`run_basketball_game()` were calling `.predict()` without passing any of those kwargs — confirmed by direct testing: two unrelated matchups (Liverpool/Villa vs. Man City/Burnley) produced byte-identical output. **Fix:** `run_soccer_game()`/`run_basketball_game()` now accept optional `home_stats`/`away_stats` dicts and forward them as prefixed kwargs; a loud `[WARNING]` prints when stats aren't supplied instead of silently using placeholders. `team_stats_provider.py` (now in repo) supplies the real data; `universal_runner.py`
wires it in automatically for soccer/basketball.
2. **Tennis crash — `round` vs. `round_name`.** `predict_match.py`'s `main()` called `predict_tennis_match(..., round="Second Round")`, but the real function signature takes `round_name`, not `round`. This is a `TypeError` on every tennis invocation. Also: `tournament`/`round`/`surface` were hardcoded to `"Wimbledon"`/`"Second Round"`/(default `"grass"`) for every match regardless of what's actually being played. **Fix:** corrected the kwarg name and parameterized tournament/round_name/surface from CLI args (with safe fallback defaults if those args don't exist yet in `predict_match.py`'s argparse setup — they'll need to be added there too, or handled entirely in `universal_runner.py` once it exists).

## 6. Known bugs — confirmed, not yet fixed

- `predict_match.py`'s baseball CLI defines `--home-sp-era`/`--home-sp-k`/`--away-sp-era`/`--away-sp-k` but never reads them in `main()`'s routing — `auto_mlb_scraper.py` fetches real live starting-pitcher data and it gets silently dropped before reaching the actual math. (A fix exists for `run_baseball_prop_market()`/`run_baseball_game()` themselves — they now accept `home_sp_overrides`/`away_sp_overrides` — but `main()`'s argparse handling still needs to pass them through.)
- `data/team_stats/` currently only contains the starter template that `team_stats_provider.py` auto-creates on first run — real per-team data must be filled in before predictions using it can be trusted.

---

## 7. Data-availability tiers — not yet encoded anywhere, should be

Confirmed via direct research this session, not assumed:

- **Tier 1 (real xG/shot data via FBref):** EPL, Serie A, Bundesliga, Bundesliga 2, Belgian Pro League, Eredivisie.
- **Tier 2 (unconfirmed, check before trusting):** Eerste Divisie, Australian NPL New South Wales.
- **Tier 3 (no public advanced stats exist):** Estonian Premium Liiga. Same category as the Romanian Liga 3 case handled earlier — needs the goals-based Poisson fallback mode, not an xG-based model with nothing real to feed it.

**Note on Tier 1:** FBref is a Sports Reference property and its ToS
prohibits scraping without a license — the same restriction already
flagged for Basketball-Reference. "Data exists publicly" is not the same
as "cleared to scrape." `team_stats_provider.py` is deliberately
manual-entry-backed for this reason; if a licensed data source (Opta,
StatsBomb, a paid API) gets set up later, swap the loader inside that file,
not the interface.

**Status as of this session:** the soccer `data_tier` field now exists in
the LIVE config (`models/soccer_predictor.py`'s inline `LEAGUE_CONFIGS`),
not the orphaned `soccer_league_config.py`. It's recorded per-league but
`SoccerPredictor.predict()` doesn't yet branch its math on it — Tier 3
leagues (Estonian Premium Liiga) still get the same xG-model treatment as
Tier 1 leagues, just with different `avg_goals_per_game`/`goal_variance`
constants. The actual goals-based fallback mode for Tier 3 still needs to
be built as real logic, not just tagged in config.

**Basketball has no per-league calibration system at all**, live or
orphaned — confirmed by reading `fiba_build_full_game()` directly, it
applies one generic FIBA-style formula regardless of league. FIBA-specific
adjustments (5-foul disqualification vs. NBA's 6, 40-minute/68-76-possession
pace baseline vs. NBA's ~98-102, EuroLeague travel/rest penalties around
Thursday/Friday continental games) are accurate, good suggestions from a
prior session but require building new logic in
`models/basketball_predictor.py`, not editing an existing system.

**Suggested next step, not yet built:** add a `data_tier`-driven branch in
`SoccerPredictor.predict()` so Tier 3 leagues actually use different math,
not just different constants in the same formula; and design the
equivalent per-league system for basketball from scratch.

---

## 8. Before you start a new agent session, run this

The file-existence checklist below (PowerShell) should be re-run at the
start of any new Cline/Blackbox/Copilot/Gemini session, and any time this
doc's "canonical" claims are in doubt. Update this doc if reality has
diverged from it.

```powershell
$files = @(
    "predict_match.py", "universal_runner.py", "team_stats_provider.py",
    "core\historical_storage.py", "core\confidence_engine.py", "core\schemas.py", "core\utils.py",
    "models\soccer_predictor.py", "models\basketball_predictor.py", "models\baseball_predictor.py",
    "models\tennis_predictor.py", "models\tennis_elo.py", "models\dispatcher.py",
    "models\soccer_model.py", "models\basketball_model.py", "models\kbo_model.py",
    "models\soccer_league_config.py", "models\soccer_shots_prop_model.py",
    "models\referee_features.py", "models\sharp_predict.py",
    "discord_integration.py", ".env",
    "prediction_store.py", "backtest_report.py", "tennis_elo.py", "run_kostyuk_keys_toronto.py"
)
foreach ($f in $files) {
    if (Test-Path $f) { Write-Host "  [OK]      $f" -ForegroundColor Green }
    else { Write-Host "  [MISSING] $f" -ForegroundColor Red }
}
```

Expected state after this session's reconciliation:
- `universal_runner.py` and `team_stats_provider.py` should show `[OK]`.
- `prediction_store.py`, `backtest_report.py` (still present, read the note
  below), top-level `tennis_elo.py`, and `run_kostyuk_keys_toronto.py`:
  `prediction_store.py`/`tennis_elo.py`/`run_kostyuk_keys_toronto.py` should
  show `[MISSING]` (deleted — see §4). `backtest_report.py` should show `[OK]`
  but now reads from `core.historical_storage` instead of `prediction_store`.

---

## 9. How to keep this doc honest

This file will go stale the moment another agent adds or removes something
without updating it — which defeats the point. Whichever agent (or human)
makes a structural change — new predictor, new store, deprecating a file —
should update the relevant table above in the same session. A stale
architecture doc that nobody trusts is worse than no doc at all, so keep
the edit small and immediate rather than batching it for later.
