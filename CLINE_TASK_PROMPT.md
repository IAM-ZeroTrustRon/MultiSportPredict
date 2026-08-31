# Task prompt — paste this whole thing to Cline or Claude Code

---

You are working in `C:\MultiSportPredict`. Read every rule in section 0 before
running anything. Two previous sessions broke this environment by acting on
assumptions that were wrong; the rules exist because of specific incidents.

## 0. Rules

**0.1 — Every Python command is `venv/Scripts/python.exe`.** Not `python`, not
`python3`, not `.venv/Scripts/python.exe`.

There are two virtualenvs here. `venv/` has bs4, discord.py, pybaseball, scipy,
pandas, numpy, requests (278 packages). `.venv/` is missing the first three.
`venv/pyvenv.cfg` is valid, Python 3.13.14. **It is not broken** — two sessions
have claimed it was and repointed the launchers at `.venv`, which then failed on
`import bs4` and `import discord`.

Bare `python` resolves to the Microsoft Store stub, which does not error — it
blocks forever. A previous session's `python3 --version` was still hanging at a
120-second timeout. **If a command appears to hang, check which interpreter it
invoked before anything else.**

`sys.path.insert(0, str(ROOT))` at the top of these scripts resolves this
project's own modules. It does nothing for installed packages. It is not a
substitute.

**0.2 — Git Bash. Forward slashes. `\` for line continuation, never `^`.**

**0.3 — Never run sqlite against `multisport_history.db` over a network mount.**
It writes every row, then fails on `conn.commit()` with `disk I/O error`, leaving
a hot `.db-journal`. The data is on disk but uncommitted, and the next process to
open the file rolls all of it back silently. Local disk only. If a `.db-journal`
or `.db-wal` exists while nothing is running, the last write did not commit —
check `PRAGMA integrity_check` before trusting the file.

**0.4 — Most files on disk are CRLF.** A patch script that reads them raw fails
every `\n` match; one that rewrites them as LF buries a small change in a
whole-file diff. Read normalised, match in LF, write back in the original ending.

**0.5 — Do not revert these. They were fixed on 2026-08-30/31 and each one was a
live bug:**

| File | Fix |
|---|---|
| `discord_integration.py` | `_tennis_players()` — reads real name keys, raises instead of defaulting to "Player 1" |
| `discord_integration.py` | dedup returns `0` and prints `[SKIP]` instead of reporting success on a suppressed push |
| `discord_integration.py` | dedup key includes destination, so one pick can reach two servers |
| `discord_integration.py` | `push_mode()` / `DISCORD_PUSH_TARGET` (`bot`/`webhooks`/`all`) |
| `discord_integration.py` | `format_prediction_embed()` reads `moneyline_and_side.home_win_probability`; Model Edge and Confidence fields populated |
| `predict_match.py` | `run_baseball_prop_market(team_overrides=...)` |
| `run_mlb.py` | `--league`, and `--odds` fetches `totals,h2h` |
| `run_tennis.py` | refuses when `data/tennis/matches.csv` is missing; tour-level freshness guard |
| `data_guard.py` | thin-sample errors no longer labelled "WRONG SEASON" |
| `msp` | no silent fallback to system Python |

**0.6 — There IS a tennis engine.** `run_tennis.py` + `models/tennis_predictor.py`
+ `models/tennis_elo.py`, running on `data/tennis/matches.csv` (9199 matches).
A previous session reported tennis unsupported without looking. It works.

**0.7 — `ingest_all_sports.py --only tennis` is dead.** It reads Jeff Sackmann's
GitHub repo, which returns 403. Use `ingest_tennis.py` (tennis-data.co.uk).

---

## 1. THE BUG THAT MATTERS MOST — two soccer stores, two meanings

`team_stats_provider.get_soccer_team_stats()` reads `data/soccer_stats.json`,
then falls back to `data/team_stats/soccer_stats.json`. The two files use the
same field name for different quantities:

```
GLOBAL   data/soccer_stats.json              goals_for = PER-GAME RATE
           Bournemouth 1.0    Napoli 1.314

MANUAL   data/team_stats/soccer_stats.json   goals_for = SEASON TOTAL
           AC Milan 6   Bayern Munich 14   (and xg_for IS per-game: 1.45, 2.45)
```

**16 clubs exist only in the manual store**, so for them the fallback is the data:
AC Milan, Ath Madrid, Bayern Munich, Bradford City, Dinamo Zagreb, Inter Milan,
Lumphat SC, Newcastle United, Nongrah, Real Madrid, Real Sociedad, Salernitana
and others. The model reads Bayern at **14 goals per game**. Every one of those
clubs has been in a prediction in the last week.

`data_guard.py` does not catch it: those records have no `season` and no `games`,
so the season check reports "age cannot be verified" (a WARNING) and the
minimum-games check has nothing to compare.

**Do this:**

1. Convert every record in `data/team_stats/soccer_stats.json` to per-game rates,
   and add `games`, `season`, `updated` and `source` to each. Where the number of
   games is unknown, **delete the record** — do not guess a denominator.
2. Rename the field so a total and a rate cannot share a name again
   (`goals_for_per_game`, or keep `goals_for` as the rate and drop totals
   entirely). Update every reader.
3. Make the fallback fail closed: `get_soccer_team_stats()` must refuse a manual
   record lacking `games` and `season` rather than returning it.

**Acceptance:** `venv/Scripts/python.exe data_guard.py --sport soccer` reports no
record with an unverifiable season, and no club resolves to a goals-per-game
figure above 4.

---

## 2. Four remaining placeholder-name defaults

`predict_tennis_match()` returns names at `moneyline.home` / `moneyline.away`
and in `match`. It returns none of `home_player`, `away_player`, `home`, `away`.
These four paths therefore publish literal placeholder names with real edges
attached:

```
discord_integration.py:837   push_soccer_prediction_to_discord   get("home_team", "Home")
discord_integration.py:1015  push_tennis_prediction_to_discord   get("home", "Player 1")
discord_integration.py:1209  format_prediction_embed             get("home", "Home")
discord_integration.py:1531  push_recommendation_to_discord      get("home", "Player 1")
```

`_tennis_players(data)` (line ~1300) already does this correctly: it checks
`moneyline.home/away`, `home_player/away_player`, `player1/player2`, `p1/p2`,
then splits `match`, and **raises** on a miss.

Route all four through it. Do not add another default.

**Acceptance:** a payload with no resolvable names raises `ValueError`; no code
path can emit "Player 1", "Player 2", "Home" or "Away" as a team or player name.

---

## 3. `xg` falls back to a magic 1.5

```
team_stats_provider.py:164   stats["xg_for"] = stats.get("goals_for", 1.5)
team_stats_provider.py:166   stats["xg_against"] = stats.get("goals_against", 1.5)
```

Substituting goals for xG is a documented tier-2 estimate and is fine. The `1.5`
is not: a club with no goals data silently becomes league-average. Return `None`
and let the caller refuse.

---

## 4. Nothing validates that a fixture exists

**This is the highest-value unbuilt feature in the repo.**

On 2026-08-29 the model produced nine predictions for games that were never
scheduled — four Serie A (Atalanta v Fiorentina, Napoli v Lazio, Juventus v Roma,
AC Milan v Inter; the real card was Fiorentina-Frosinone, Monza-Udinese,
Sassuolo-Torino, Juventus-Parma) and five KBO (every team played, not one of the
predicted pairings existed). All carried confidence scores, edges and Discord
embeds. Nothing downstream could tell them from real ones.

Build a `fixture_guard.py` on the pattern of `data_guard.py`:

- `verify_fixture(sport, home, away, date) -> (bool, str)`
- MLB: `statsapi.mlb.com/api/v1/schedule?sportId=1&date=YYYY-MM-DD` (reachable)
- KBO: `mykbostats.com` (reachable)
- Soccer: `site.web.api.espn.com/apis/site/v2/sports/soccer/<league>/scoreboard`
  (reachable; `site.api.espn.com` is Akamai-blocked, do not use it)
- Tennis: no reachable draw feed — return "unverified", not "valid"
- Wire into `run_mlb.py`, `run_soccer_batch.py`, `run_tennis.py`, `run_liga_mx.py`
  and refuse on a confirmed miss, the way `data_guard` already refuses

It must also **return the feed's home/away orientation**, because typed matchups
get reversed: NC Dinos v LG Twins and Lotte v KIA (2026-08-26), Club Leon v
Atlante (2026-08-28) were all logged with the road team as home, so home
advantage was applied to the wrong side. `run_mlb.py` already does this for MLB
and prints `[home/away] schedule says ...` — copy that behaviour.

**Acceptance:** a made-up fixture is refused with the real card printed; a real
one runs and reports which side the feed says is home.

---

## 5. Prior-season blend — unblocks every European league

Premier League, Championship, Serie A, Serie B, Eredivisie and La Liga are all
1-3 games into 2026/27 against a `MIN_GAMES` floor of 5, so every one of them is
blocked. Re-ingesting cannot help; those are all the games that have been played.

`ingest_soccer_fd.py` already regresses toward the league average with
`weight = games / (games + 6)`. Extend it to blend toward **the club's own prior
season** first, then the league average for a promoted club with no prior season.
Store `prior_season_games` and `prior_season_source` on each record so the blend
is auditable, and keep `data_tier` honest about it.

**Acceptance:** `venv/Scripts/python.exe run_soccer_batch.py --slate <an
Eredivisie slate>` runs instead of refusing, and each record shows what fraction
of its number came from the prior season.

---

## 6. Smaller items

- **`sport` column holds both `baseball` (42 rows) and `mlb` (18).** Same sport,
  two labels; every per-sport report splits them. Normalise, and fix whatever
  writes `mlb`.
- **Nine phantom predictions** are still in the DB ungraded (§4). Delete them
  after §4 lands, so they cannot be regenerated.
- **`run_mlb.py` has no `--push` after review.** `run_tennis.py` writes
  `data/tennis_review.json` so `--push 1 4 7` can fire later. Give `run_mlb.py`
  the same, so `!kbo` and `!mlb` in the Discord bot match `!tennis`.
- **The Discord bot dumps raw stdout into a code block.** Unreadable on a phone.
  It should build an embed through `format_prediction_embed()` like pushes do.
  `msp_bot.py` `chunks()` is the current path.
- **Commit.** There were 45 uncommitted changes as of the last scan.
- **Delete `.venv/`** once §0.1 is understood. It exists only to be mistaken for
  the real one.

---

## 7. Verify before you report done

```bash
venv/Scripts/python.exe -m py_compile run_mlb.py run_tennis.py ingest_tennis.py \
  discord_integration.py universal_runner.py predict_match.py grade_predictions.py \
  data_guard.py mcp_server.py msp_bot.py team_stats_provider.py \
  core/historical_storage.py models/tennis_predictor.py

venv/Scripts/python.exe mcp_server.py --selftest      # expect 15 tools, 0 failures
venv/Scripts/python.exe data_guard.py
venv/Scripts/python.exe grade_predictions.py --report
./msp status
```

Then run four different MLB matchups and confirm **four different projected
totals**. Identical numbers across different teams is the signature failure of
this codebase and has appeared three times: hardcoded league averages, fabricated
Elo ratings, and placeholder names. Each time the code printed something
reassuring that was true and did not mean what it appeared to mean.

## 8. Working style

- Plain, short, direct. Facts and steps.
- Do the task; do not hand back commands for the user to run when you can run
  them yourself.
- Never paste a secret into the conversation. `.env` is gitignored and untracked;
  values go from their source into that file and nowhere else.
- Do not push to Discord unless asked. Predict, show the table, wait.
- If a check fails, say which check and what it returned. Do not describe work as
  complete because a command exited 0.
