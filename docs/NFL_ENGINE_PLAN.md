# NFL Engine — 3-Day Build Plan

Target markets: full-game ML, halftime ML, ATS, game totals, team totals, and rushing / passing / TD props.
Written 2026-08-28. Regular season opens ~Sept 10, so this lands with about two weeks to spare.

---

## Read this before choosing a source

**Pro-Football-Reference will almost certainly be blocked.** It runs on Sports Reference infrastructure — the same stack as FBref, which returns 403 on this machine, alongside FanGraphs and RealGM. Every NFL tutorial online points at PFR. Building against it would burn a day and end in a Cloudflare challenge page.

Use **ESPN's public JSON APIs** instead. No key, no Cloudflare interstitial, and the same shape as the MLB Stats API that already works here:

```
site.api.espn.com/apis/site/v2/sports/football/nfl/teams
site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard
site.web.api.espn.com/apis/v2/sports/football/nfl/standings?season=2025
sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2025/types/2/teams/{id}/statistics
sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2025/athletes
```

`probe_sources.py` tests all of these plus PFR and nflverse. **Run it before writing any ingestion code.**

Note on nflverse (nflfastR): it is the best free play-by-play data in football and would give real EPA. It ships through GitHub releases, and GitHub currently 404s on this machine — the same failure that killed the tennis feed. If the probe shows GitHub working for the API but not raw files, nflverse may still be usable via its release assets.

## The cold-start problem nobody warns you about

On **Week 1, there is no current-season data.** Zero games played. A model built on season-to-date averages produces nothing on opening weekend, and something close to noise through Week 4 — nine games is not a sample.

Plan for it deliberately:

1. **Ingest the full 2025 season as the prior.** Every team gets last year's per-game numbers as its starting point.
2. **Blend toward current season as games accumulate**, with a documented weight. A standard shrinkage: `weight_current = games_played / (games_played + k)`, with `k ≈ 4` for team scoring rates. Week 1 is 100% prior; by Week 8 it's about 67% current.
3. **Regress the prior toward league average before using it.** Last year's 13-4 team is not a 13-4 team this year. Regressing point differential about 30% toward zero is a reasonable starting assumption — and it is an assumption, so record it as one and revisit after a season.
4. **Adjust for roster turnover manually** where you know it matters (a new starting QB moves a team several points; nothing in a stats feed will tell you that).

Tag every Week 1–4 prediction with the blend weight used. When you grade results later, you will want to know which ones ran mostly on priors.

---

## Day 1 — the data spine

**Goal:** `data/nfl_stats.json` populated with all 32 teams, and a schedule feed.

Build `ingest_nfl()` as a new adapter inside `ingest_all_sports.py`. Follow the MLB adapter — it already solves merge-safety, caching, dry-run and season handling.

Team fields to pull (per game, not season totals):

| Field | Used by |
|---|---|
| `points_for`, `points_against` | ML, spread, totals |
| `yards_for`, `yards_against` | strength estimate |
| `plays_per_game` | pace → totals |
| `pass_att`, `rush_att`, `pass_yards`, `rush_yards` | props, play-mix |
| `pass_yards_allowed`, `rush_yards_allowed` | opponent adjustment for props |
| `turnover_diff` | regression signal |
| `third_down_pct`, `red_zone_td_pct` | scoring efficiency |
| `home_record`, `away_record`, `l5_record` | splits and form |
| `points_1h_for`, `points_1h_against` | **halftime markets** |

That last row matters. Halftime ML needs real first-half scoring, not a full-game number multiplied by a guess. If ESPN doesn't expose 1H splits directly, derive them from the scoreboard's per-quarter线 scores across the season and **tag the field `derived`**.

Also build `ingest_nfl_schedule()` → `data/nfl_schedule.json` with game id, date, teams, and final scores once played. Grading depends on this.

**Odds are already solved.** `OddsApiIngestor` takes any sport key and already supports `h2h,spreads,totals`:

```python
from OddsApiIngestor import OddsApiIngestor
ingestor = OddsApiIngestor(markets="h2h,spreads,totals")
games = ingestor.fetch_live_odds("americanfootball_nfl", days=7)
```

ATS and totals are meaningless without the market line, so wire this on Day 1, not Day 3.

**End of Day 1 test:** all 32 teams in the store with distinct numbers, and this week's lines fetched.

## Day 2 — the game-level model

**Goal:** `models/nfl_predictor.py` producing ML, ATS, totals and team totals.

The core is a points model. Expected points for each side:

```
home_pts = league_avg + (home_off_strength - away_def_strength) + home_field_advantage
away_pts = league_avg + (away_off_strength - home_def_strength)
```

Home field in the NFL is worth roughly **1.5–2.0 points** in recent seasons — down from the ~3 points older references quote. Use 1.8 and make it a named constant you can tune, not a number buried in a formula.

Then:

- **Spread** = `home_pts − away_pts`. Compare to the market spread; the difference is your edge.
- **Moneyline** — convert margin to win probability. NFL margin has a standard deviation of about **13.5 points**, so `win_prob = Φ(margin / 13.5)`. Do not reuse a sigmoid tuned for another sport; that is how a 3-point favourite ends up priced like a 10-point one.
- **Total** = `home_pts + away_pts`, compared to the market total.
- **Team totals** — the two components you already computed.
- **Halftime ML** — first half is roughly **47–48%** of full-game scoring, but the distribution matters more than the mean: fewer points means margin variance is smaller, so first-half margin standard deviation is around **9.5**, not 13.5 halved. Derive both numbers from your own ingested 1H data rather than adopting mine.

**Key-number awareness.** NFL margins cluster hard on **3** and **7**. A model spread of 3.4 against a market spread of 3.0 is not a real edge — it's inside the noise around the single most common margin in the sport. Suppress recommendations where your edge is under about 1.5 points near a key number. This single rule will save you more money than any modelling refinement.

Wire into `universal_runner.py` with a `run_nfl()` that looks stats up through `get_nfl_team_stats()` and **raises when a team is missing** — the same guard that fixed soccer and baseball. Do not let it fall back to league averages.

**End of Day 2 test:** run last season's Week 10 slate from stored priors and check the spreads look sane against what the market actually was. Anything more than a touchdown off the closing line means a bug, not an edge.

## Day 3 — props, then wiring

**Goal:** projections for rushing / passing / TD, plus Discord and grading.

Player projection is a usage-times-efficiency-times-context problem:

```
proj_pass_yards = team_pass_att × player_share × yards_per_att × opponent_pass_def_adj
proj_rush_yards = team_rush_att × player_share × yards_per_carry × opponent_rush_def_adj
proj_anytime_td = expected_team_tds × player_td_share
```

Then convert to a probability against the book's line. For yardage, a normal distribution around the projection is workable; typical standard deviation is around **35–40%** of the mean for receiving and rushing yards — these are extremely high-variance markets. For anytime TD, Poisson on expected touchdowns is the standard approach.

### Be realistic about props

**Do not push prop bet recommendations in week one.** Player props are the sharpest markets on the board, priced by people with injury reports, snap counts, and weather you do not have. Your projections will be reasonable; your *edges* will mostly be model error.

Emit props as **projections with no recommendation** for the first three weeks. Log them, grade them, and only turn on recommendations for a prop type once its graded record justifies it. `grade_predictions.py` already separates informational rows from actual bets, which is exactly this workflow.

Two things will hurt props most, and neither is a modelling problem:

- **Injuries and inactives.** A projection for a player ruled out 90 minutes before kickoff is worse than no projection. Check the ESPN scoreboard feed for inactives before any prop goes out.
- **Snap-share changes.** Usage shifts week to week far more than efficiency does. Weight recent games heavily for share, lightly for efficiency.

### Then wire the plumbing

- `discord_integration.py` — add `push_nfl_prediction_to_discord()`, following the baseball formatter.
- `grade_predictions.py` — add `fetch_nfl_results()` returning `{(date, home_key, away_key): (home_score, away_score)}` from the ESPN scoreboard, and register it in `AUTO_SOURCES`. About 20 lines.
- **Store the ATS side explicitly.** Spread markets are currently ungradable because `model_value` doesn't record which side the number belongs to. Do not repeat that for NFL — write the pick into the `pick` column at prediction time.

---

## Scope check

Honest expectations for three days:

| Market | Realistic by day 3 |
|---|---|
| Game total, team totals | Yes |
| Full-game ML | Yes |
| ATS | Yes, with the key-number rule |
| Halftime ML | Yes, if 1H data is ingested on Day 1 |
| Rushing / passing / TD props | Projections yes, **recommendations no** |

The binding constraint is not code — it's sample size. The NFL plays about **16 games a week**. Three weeks is roughly 48 games; a full season is 272. Baseball gives you 2,430. You will not know whether this model is good until deep into the season, and a hot 8-3 start after three weeks is statistically indistinguishable from luck.

Build it to log everything and grade honestly. The engine can be finished in three days; knowing whether to trust it takes months.

## Order of operations

1. Run `probe_sources.py` → confirm ESPN reachable, PFR blocked.
2. Ingest **2025** first, not 2026. Priors before live data.
3. Wire the Odds API on Day 1 — ATS and totals need lines.
4. Build the points model before anything else; every game market derives from it.
5. Props last, as projections only.
6. Grade from the first prediction. A record that starts in Week 6 tells you nothing about Weeks 1–5.
