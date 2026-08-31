# MultiSportPredict — Cowork progress catch-up

Generated 2026-08-30. Repo: `C:\MultiSportPredict` (GitHub: IAM-ZeroTrustRon).

---

## 1. Git log — last 20 commits

```
dadbb32 Rewrite README for security engineering focus
73f2af8 Add data_guard, soccer batch runner, MLB runner, sample regression; fix season sorting bug
4d51e1e Add .gitattributes; stop tracking the prediction database
a210695 Add unified daily ingestion, results grading, and fix silent placeholder bugs
71fcdda chore: publish all current workspace changes
25db30a chore: publish current multisport prediction updates
a73ab12 feat: final 5 games analysis - all markets with h2h splits, venue, umpire tendencies
3315ccf feat: MLB game-level props analysis for moneyline and total runs
fd106d2 feat: MLB slate analysis, pitcher/hitter props, NRFI/YRFI
3719a1e feat: soccer analysis Germany vs Ivory Coast
7d9b7be feat: live tennis analysis Choinski vs Wu
a8ccb80 feat: pitcher and hitter props for Twins vs Diamondbacks
f663919 feat: Twins vs Diamondbacks strong plays
ff23b1e improve: clarify Over/Under with +/- line notation
aad5167 feat: Discord delivery script for Reds vs Yankees props
83d6163 enhance: pitcher and hitter prop tables for Reds vs Yankees
a32e3bf feat: MLB analysis Reds vs Yankees
88db970 feat: Valencia vs Barcelona basketball analysis suite
c417e8e Add live scraper hooks, SQLite backtesting, and daily slate runner
28c4c26 Add live match deep dive analysis for Mexico vs South Korea
```

The last four commits (`4d51e1e` through `dadbb32`) are the Cowork work. Everything below `71fcdda` predates it.

**Uncommitted right now:**
```
 M RESULTS_TRACKING.md
 M grade_predictions.py
?? _to_delete/
?? else:                       <- stray directory from a shell accident, delete it
?? output/soccer/AC_Milan_vs_Inter_Milan.json
?? output/soccer/Atalanta_vs_Fiorentina.json
?? output/soccer/Juventus_vs_Roma.json
?? output/soccer/Napoli_vs_Lazio.json
?? run_serie_a_slate_aug29.sh
?? slate_pl_r2.json
?? slate_seriea.json
```

---

## 2. Key files

```
data_guard.py            12K   2026-08-29   NEW
discord_integration.py   47K   2026-08-28   PATCHED
grade_predictions.py     29K   2026-08-30   NEW
ingest_all_sports.py     62K   2026-08-28   NEW
ingest_nfl.py            15K   2026-08-28   NEW
ingest_soccer_fd.py      18K   2026-08-29   NEW
predict_match.py         59K   2026-08-28   PATCHED
run_liga_mx.py           11K   2026-08-29   NEW
run_mlb.py               20K   2026-08-29   NEW
run_soccer_batch.py      16K   2026-08-29   NEW
team_stats_provider.py   13K   2026-08-28   PATCHED
universal_runner.py      32K   2026-08-29   PATCHED
```

Every patched file has a `.bak-2026MMDD` backup beside it.

---

## 3. What's new that didn't exist before

**Daily ingestion — `ingest_all_sports.py`, 10 adapters:**

| Adapter | Source | Status |
|---|---|---|
| `mlb` | statsapi.mlb.com | working, 30/30 teams |
| `mlb-probables` | statsapi.mlb.com | working |
| `mlb-players` | pybaseball | working |
| `kbo` | mykbostats.com | working, 10 teams |
| `euroleague` | euroleague-api | working, 20 teams |
| `kbl` | RealGM | blocked (Cloudflare) |
| `nznbl` | RealGM | blocked (Cloudflare) |
| `tennis` | Sackmann GitHub | source repo went private |
| `soccer-espn` | ESPN | blocked (Akamai) |
| `soccer` | FBref | blocked (Cloudflare) |

**`ingest_soccer_fd.py`** — replacement soccer source (football-data.co.uk), reachable. Currently 120 teams across 6 leagues.

**`ingest_nfl.py`** — 32 NFL teams seeded from the 2025 season as an early-season prior. Predictor model not written yet; design is in `NFL_ENGINE_PLAN.md`.

**`data_guard.py`** — fail-closed data validation. Refuses to predict when a team's record is the wrong season or has too few games. `MIN_GAMES`: soccer 5, baseball 15, basketball 5, NFL 4. This exists because a season-folder sorting bug silently loaded the **1999/2000** Premier League and produced two confident predictions from 25-year-old squads. It also caught 1-3 game samples producing 6-goal projections and fake 54% edges.

**`grade_predictions.py`** — results grading. The DB had 104 predictions logged and **0 graded**; `update_prediction_outcome()` existed and was never called. Now grades `total`, `moneyline`, `btts` (spread deliberately left ungraded — the stored value doesn't record which side it belongs to). Settles at recorded odds where `raw_json` has them, -110 otherwise.

**Runners:** `run_mlb.py`, `run_soccer_batch.py`, `run_liga_mx.py` — name resolution that refuses ambiguity rather than guessing, de-vigged three-way odds comparison, no Discord push until reviewed (`--push N` / `--push-all`).

**Discord:** `push_soccer_prediction_to_discord()` rewritten to inline grid fields with emoji badges, matching the baseball output format.

**Regression toward the mean** added to soccer ingestion: `weight = games / (games + 6)`.

---

## 4. Database schema

`multisport_history.db` → table `predictions`, 145 rows, 51 graded.

```
id, sport, home_team, away_team, market_type, model_value, market_value,
edge, confidence, recommendation, timestamp, raw_json, result_outcome,
profit_loss,
game_date, league, pick, actual_home_score, actual_away_score,
graded_at, grade_note          <- these 7 added by grade_predictions.py
```

Rows by sport: soccer 78, baseball 40, mlb 18, basketball 6, tennis 3.
(`baseball` and `mlb` are separate sport labels — worth normalizing.)

---

## 5. What's seeded and ready to run

```
data/soccer_stats.json      120 teams   Championship 24, Eredivisie 18, Liga MX 18,
                                        Premier League 20, Serie A 20, Serie B 20
data/baseball_stats.json     40 teams   MLB 30, KBO 10
data/nfl_stats.json          32 teams   NFL 32 (2025 season, as prior)
data/euroleague_stats.json   20 teams   EuroLeague 20
data/basketball_stats.json   MISSING    (KBL and NZ NBL never landed — sources blocked)
```

`team_stats_provider.py` public API:

```
get_soccer_team_stats(team, league=None)        upsert_soccer_team_stats(team, stats)
get_basketball_team_stats(team, league=None)    upsert_basketball_team_stats(team, stats)
get_euroleague_team_stats(team)                 upsert_euroleague_team_stats(team, stats)
get_baseball_team_stats(team, league=None)      upsert_baseball_team_stats(team, stats)
get_euroleague_league_baseline()
```

`get_baseball_team_stats` / `upsert_baseball_team_stats` and `BASEBALL_STATS_PATH` are new — baseball had no provider at all before, so `universal_runner.run_baseball()` was silently falling back to hardcoded league averages and returning identical predictions for every matchup.

---

## 6. Known open problems

1. **Nothing validates that a fixture exists.** On 2026-08-29 the model produced predictions for 4 Serie A and 5 KBO matchups that were never scheduled. They look identical to real predictions — confidence score, edge, Discord embed. This is the highest-priority fix.
2. **Home/away gets reversed** when a matchup is typed by hand instead of read from a schedule feed. Confirmed on 3 games.
3. **Duplicate predictions** — one Leagues Cup match is in the DB 4 times (kickoff crossed UTC midnight, logged on both dates).
4. **No source publishes xG** that is reachable. All soccer xG is estimated from goals and tagged `data_tier: 2`.
5. **Spread is never graded** — the side isn't stored at write time.
6. **No closing-line value tracking.**
7. **`sport` column has both `baseball` and `mlb`.**

## 7. Not started

- `models/nfl_predictor.py` (data seeded, model not written; NFL season opens ~Sept 10)
- MCP server
- Web-based mobile app
- Termius / SSH access from phone — no decision made yet
