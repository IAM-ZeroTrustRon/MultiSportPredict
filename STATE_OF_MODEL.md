# MultiSportPredict — State of the Model

**As of 2026-09-20.** Machine: `C:\MultiSportPredict` (Windows 11, Git Bash).
Interpreter: `venv/Scripts/python.exe` — 312 packages. There is only one venv;
`.venv` was deleted 2026-09-13 because it lacked bs4, discord.py and pybaseball
and two sessions had already been fooled into pointing launchers at it.

---

## 1. The record — there isn't one yet

**The raw database says 60 W – 52 L – 2 P over 114 settled rows, 53.6%. That
number is not real.** Audited 2026-09-20:

| Problem | Rows affected |
|---|---|
| Rows the model said **PASS** on, graded as if they were bets | **38 of 114** |
| Duplicate fixtures (same game, both home/away orders, or re-runs) | **17 extra rows** |
| Settled at a flat −110 regardless of the real price | **all 114** |
| Legacy rows whose `recommendation` is neither a side nor a pass (`"Over: 63.9% \| Under: 36.1%"`) | ~20 |

Every `profit_loss` in the database is exactly `-1.0`, `0.0` or `+0.9091`.
`run_mlb.py` writes the real market odds into `raw_json` via
`record_market_odds()`, and grading ignores them.

**Stripping PASS rows and duplicates leaves 62 actual bets: 34–28, 54.8%.**

| Sport | Real record | Bets |
|---|---|---|
| Baseball | 21–25 (45.7%) | 46 |
| Tennis | 9–3 (75.0%) | 12 |
| Soccer | 4–0 (100%) | 4 |

Sixty-two bets settled at a fabricated price. Baseball flips from marginally
positive to losing once PASS rows come out. Tennis at 9–3 and soccer at 4–0
are too small to mean anything.

**Conclusion: this model has no measured performance.** Not "a small edge",
not "break-even" — unmeasured. Nothing about scope, market selection or model
tuning can be decided until grading counts only real bets at real prices.

## 2. Data stores — freshness

| Store | Updated | State |
|---|---|---|
| `data/baseball_stats.json` (MLB + KBO) | 09-20 | current |
| `data/mlb_probables.json` | 09-20 | current |
| `data/soccer_stats.json` | 09-20 | current |
| `data/nfl_stats.json` | 09-20 | current |
| `data/nfl_schedule.json` | 09-20 | current |
| `data/ncaaf_schedule.json` | 09-18 | current |
| `data/tennis/players.json` | **08-30** | **21 days stale — broken** |

Tennis is the one broken feed. See §5.

Refresh everything: `bash ingest_all.sh > ingest_all.log 2>&1`

---

## 3. What each sport can actually do

| Sport | Predict | Auto-grade | Notes |
|---|---|---|---|
| MLB | yes | yes | Best developed. Totals, moneyline, run line, NRFI, F5, K/HR props |
| NFL | yes | yes | Built Sept 2026. Spread, total, moneyline, first half |
| Tennis | yes | yes | Elo + surface splits. Feed currently broken |
| Soccer | yes | **no** | 86 ungraded and no auto-grader — manual CSV only |
| KBO | yes | **no** | No auto source |
| Basketball | yes | **no** | EuroLeague only, 6 rows, stale since 08-28 |
| NCAAF | **no** | yes | Results ingest exists; no predictor, no runner |

NCAAF is half-built: `ingest_ncaaf.py` pulls FBS results into
`ncaaf_schedule.json`, and `grade_predictions.py` has an `ncaaf` auto source,
but nothing makes a college football prediction. The Big 12 + MAC plan never
got past the data layer.

---

## 4. Architecture

```
run_mlb.py  run_nfl.py  run_tennis.py  run_soccer_batch.py     entry points
        |
universal_runner.py        the hub — every sport routes through it
        |
predict_match.py           baseball + soccer + prop maths (81 KB)
models/                    nfl_predictor, tennis_predictor, baseball_predictor
core/historical_storage.py the ONLY writer to multisport_history.db
        |
grade_predictions.py       pulls real results, settles rows
backtest_report.py         win rate and P/L
```

**One database counts: `multisport_history.db`.** If a tool ever proposes
`predictions.db` or a per-sport `.db`, it is splitting your record and you
will not be able to measure anything. `predictions.db` is dead and now sits in
`archive/scratch-data/`.

### The guards

These refuse rather than degrade. When a run says it refused something, that
is the design working — fix the data, do not bypass the guard.

| File | Refuses |
|---|---|
| `data_guard.py` | Stale stores; too-thin samples (soccer 5 games, baseball 15, nfl 4, tennis 8 matches) |
| `fixture_guard.py` | Games not actually on the schedule |
| `embed_builder.py` | Empty embeds, invented player names |
| `team_stats_provider.py` | Silently swapping a league average for a real team |
| `run_nfl.py` | Storing a projection with no market price |

---

## 5. Open problems, ranked

**1. 198 ungraded predictions.** 78 of them (soccer, KBO, basketball) have no
auto-grader and can only be settled by CSV. Until these are graded the record
above is built on a third of the data.

**2. Tennis feed is down.** `tennis-data.co.uk` began refusing requests
between 08-30 and 09-18. All four downloads return `HTTPError`. Fixed in code
on 09-19 — `BASE` now tries `https://` first with `http://` as fallback, and
failures now print the HTTP status instead of a bare class name — but
**the retry has not been run**, so the store is still 21 days old.
Run: `python ingest_tennis.py --years 2025 2026 --tours atp wta`

**3. The 39 NFL rows have `game_date = NULL`.** Self-healing —
`grade_predictions.py` backfills it from the timestamp at line 104 — but they
cannot be auto-graded until a grading pass runs.

**4. The NFL totals model was inverted until 09-13.** `nfl_predictor.py`
subtracted the opposing defence's points-allowed instead of adding it, so
facing a *good* defence raised your projected score. It put Patriots/Seahawks
at a 62.7 total and Jets/Titans at 31.5. Fixed in both the full-game and
first-half blocks. **Any NFL projection produced before 2026-09-13 is garbage.**

**5. Fixture guard ignores the season.** With 544 games across 2025 and 2026
in one file, a 2026 Week 1 lookup can match a 2025 game. Observed: SF@LAR
matched 2025-10-03 week 5. Not yet fixed.

**6. Team names carry `(2025)` into NFL output.** The stats-store key leaks
into display and into `home_team`/`away_team` in the database, which will not
match ESPN's names at grading time. Not yet fixed.

**7. The Odds API URL in the NFL path is malformed.**
`api.opticodds.com/api/v3/v4/...` — two APIs spliced together. `live_odds.py`
uses the correct `api.the-odds-api.com/v4`; only the NFL path is wrong.

**8. `data_guard` classifies errors by substring.** Lines 237 and 312 test
`"game" in message`, so tennis sample errors read "only 1 game(s) played".
Renaming the noun would silently reclassify them. The fix is a `kind`
attribute on `Problem`, not a string edit.

**9. No park factors, bullpen fatigue, weather, umpire, platoon splits or
lineup data** in the baseball model. Kauffman's outfield does nothing to the
numbers.

**10. Baseball's ERA coefficient is 0.3.** A full run of ERA difference moves
the projected total by three tenths of a run, so pitching barely affects the
total. Structural, not a bug — but it should be refit against graded results
before it is trusted.

---

## 6. The recurring failure mode

Every significant bug in this project has been the same shape: **a lookup that
fails and returns a plausible default instead of an error.** A partial list of
what has been found and fixed:

- `calculate_sharp_confidence(0.75, 0.35)` — two hardcoded constants that
  satisfied the alignment test by construction, so **every** baseball
  prediction ever printed "ALIGNED WITH SHARPS" and took a confidence boost
  for a claim about professional money that no data source supported.
- Strikeouts computed as `k_rate * 38 * 0.5` with `k_rate` hardcoded to 0.22 —
  4.2 projected strikeouts for both teams in every game ever run.
- K/9 divided by batters-faced-per-*start* (23.65) instead of per-nine-innings
  (38), inflating every starter's strikeout rate ~60% and therefore **every
  NRFI this project ever produced**.
- `home_win_prob, 0.5` — a failed lookup rendering as a 50/50 coin flip.
- First-half averages merged by a name function that deliberately strips the
  season tag, so 2026 Week 1 numbers overwrote all 32 teams' 2025 records
  while those records still claimed `games: 17`.
- `_store_prediction` returning `None` on success, so callers reported failure
  for every write that actually landed.

**The rule that follows: a number with no source is worse than no number.**
When a value cannot be computed, the code must say so and refuse. That is why
the guards exist and why they should not be worked around.

---

## 7. Sources

**Working:** statsapi.mlb.com · mykbostats.com · football-data.co.uk ·
site.web.api.espn.com · sports.core.api.espn.com · api.the-odds-api.com

**Blocked:** FBref · FanGraphs · RealGM · Pro-Football-Reference (Cloudflare) ·
site.api.espn.com without "web" (Akamai) · GitHub raw and API (403) ·
tennis-data.co.uk (new, under investigation)

This is why `ingest_all.sh` uses `ingest_soccer_espn.py` rather than the
`soccer` adapter, and `ingest_tennis.py` rather than the `tennis` adapter —
both of those adapters read blocked hosts.

---

## 8. Commands

All Git Bash, from `/c/MultiSportPredict`. `python` works while `(venv)` is in
the prompt; otherwise use `venv/Scripts/python.exe`.

```bash
# refresh everything
bash ingest_all.sh > ingest_all.log 2>&1

# run a slate
python run_mlb.py --today --odds
python run_nfl.py --week N --odds
python run_soccer_batch.py --slate slate_today.json
python run_tennis.py ...

# record results
python grade_predictions.py --pending
python grade_predictions.py --auto
python grade_predictions.py --manual results.csv
python grade_predictions.py --report
python backtest_report.py

# check before trusting
python data_guard.py --sport baseball|nfl|soccer|tennis|basketball
```

Valid `--sport` names are `baseball, basketball, nfl, soccer, tennis` —
**not** `mlb`.

---

## 9. Environment traps

- **Bare `python` without `(venv)`** hits the Windows Store stub and hangs 120s.
- **Git Bash needs forward slashes.** `venv\Scripts\python.exe` becomes
  `venvScriptspython.exe` — backslash is an escape character in bash.
- **Never run sqlite writes over a network mount.** Writes land, `commit()`
  fails with `disk I/O error`, and a hot `.db-journal` is left that silently
  rolls back on the next open. Database work happens on Windows only.
- **`nul`** in the root cannot be moved or deleted — reserved Windows device
  name. It is gitignored. Leave it.
- Repo root went from ~330 files to ~75 on 09-13. Everything removed is under
  `archive/`, nothing deleted. `INDEX.md` is the map.
