# Daily Ingestion — MultiSportPredict

One script refreshes every league: `ingest_all_sports.py`.
Last updated 2026-08-28.

---

## Run it

```
cd C:\MultiSportPredict
refresh_all.bat
```

That's the whole thing. It uses `venv\Scripts\python.exe` automatically and writes a log to `logs\ingest_YYYYMMDD.log`.

**Schedule it:** double-click `install_daily_task.bat`. It registers a Windows task called *MultiSportPredict Daily Refresh* that runs at 06:00 every day. If it reports a failure, right-click the file → *Run as administrator* and try again. No Command Prompt typing, no Git Bash.

**Before trusting a run, test the sources:**

```
refresh_all.bat --check
```

`--check` contacts every source and reports what came back **without writing any files**. Do this first — it tells you which of the nine adapters actually reach their source from your network.

---

## What it covers

| Adapter | League | Source | Writes to |
|---|---|---|---|
| `mlb` | MLB team metrics | statsapi.mlb.com (official API) | `data/baseball_stats.json` |
| `mlb-probables` | MLB starters, today + tomorrow | statsapi.mlb.com | `data/mlb_probables.json` |
| `mlb-players` | MLB player props (wOBA/ISO/K%) | pybaseball → existing `ingest_mlb.py` | `data/mlb_stats.json` |
| `kbo` | KBO team metrics | mykbostats.com team splits | `data/baseball_stats.json` |
| `euroleague` | EuroLeague ORTG/DRTG/pace | euroleague-api | `data/euroleague_stats.json` |
| `kbl` | Korean Basketball League | basketball.realgm.com (league 63) | `data/basketball_stats.json` |
| `nznbl` | New Zealand NBL | basketball.realgm.com (league 75) | `data/basketball_stats.json` |
| `tennis` | ATP main tour **+ Challenger** | JeffSackmann/tennis_atp CSVs | `data/tennis/atp_matches.csv` |
| `soccer` | 10 soccer leagues | existing `ingest_soccer.py` | `data/soccer_stats.json` |

Every store is one that `team_stats_provider.py` already reads. Nothing new to install — `ingest_all_sports.py` uses only the Python standard library for its own fetching and parsing.

---

## Useful flags

```
refresh_all.bat --check                  test every source, write nothing
refresh_all.bat --only kbo tennis        just those adapters
refresh_all.bat --skip soccer            everything except soccer
refresh_all.bat --only kbl --season 2025 force a season year
refresh_all.bat --no-cache               ignore the response cache, refetch
refresh_all.bat --debug                  print every URL tried + raw column names
python ingest_all_sports.py --list       show adapter names
```

Exit codes: `0` all adapters succeeded, `1` some failed (the rest still wrote), `2` all failed (usually means no internet, not nine broken sites).

---

## Three bugs this fixed

**1. Baseball ran on league averages for both teams.**
`BaseballPredictor.load_data()` defaults every team metric — `home_runs`, `home_era`, `home_whip`, `obp`, `slg` — to a hardcoded league average, and `universal_runner.py` never passed real ones. Every MLB matchup used 4.5/4.0 runs and 3.8/4.2 ERA; every KBO matchup used 5.2/4.8 and 4.5/4.8. Same shape as the soccer identical-numbers bug.

Fixed in three places: `run_baseball_game()` in `predict_match.py` now takes a `team_overrides` dict and forwards it into `load_data()`; `run_baseball()` in `universal_runner.py` looks the teams up and builds that dict; `team_stats_provider.py` gained `get_baseball_team_stats()`. A team with no ingested data now prints a loud warning naming the command that fixes it, instead of quietly becoming a league-average clone.

**2. Tennis Elo was frozen.**
`models/tennis_predictor.py` called `load_match_history()` with **no CSV path**, so `TennisElo` only ever applied its small hardcoded `SEED_MATCHES` list. Every rating was stuck at whenever that list was written. It now loads `data/tennis/atp_matches.csv` and prints how many real matches went into the ratings — and says so loudly when the file is missing.

**3. EuroLeague ingestion deleted its own league baseline.**
The old `ingest_hoops.py` wrote `euroleague_stats.json` with a plain overwrite, which erased the `_league_baseline` block that `get_euroleague_league_baseline()` reads. Merging in the new script preserves `_`-prefixed keys, and also keeps KBL teams alive when NZ NBL is ingested into the same file.

---

## Design rules

- **Never invent a number.** If a source omits a field, that field is absent from the record — not backfilled with a league average. Downstream code is supposed to warn on a miss; that warning is the product.
- **Every record carries `source` and `updated`,** so you can always tell where a number came from and how stale it is.
- **Stores are merged, never overwritten,** and written atomically (`.tmp` + `os.replace`), so a crash mid-write can't corrupt a store and one league can't wipe another.
- **One dead source never kills the run.** Adapters are isolated; failures are summarized at the end.
- Responses are cached on disk for 6–12 hours in `data/cache/ingest/`, so re-running to debug one adapter doesn't refetch everything.

---

## Data sources

statsapi.mlb.com and the Sackmann CSVs are public feeds meant to be read programmatically. mykbostats.com and basketball.realgm.com are ordinary web pages, so the script requests them at human pace — one page every few seconds, once a day, cached in between.

**koreabaseball.com is deliberately not used**: its robots.txt disallows automated access, so KBO comes from mykbostats instead.

**Sackmann's tennis data is CC BY-NC-SA 4.0** — fine for your own analysis, requires attribution, and forbids commercial redistribution. If this model ever becomes a paid product, that feed needs replacing with a licensed one.

The current-year Challenger file (`atp_matches_qual_chall_2026.csv`) is published on a lag and doesn't exist yet. The adapter reports the 404 and carries on with what's available — Challenger results for prior years still feed the Elo ratings. It'll pick the file up automatically once Sackmann publishes it.

---

## Adding another league

1. Write an adapter function `ingest_x(check=False, season=None) -> AdapterResult` in `ingest_all_sports.py`.
2. Fetch with `http_get()` / `http_get_json()` (use `polite=True` for scraped HTML pages).
3. For HTML tables: `pick_table(parse_tables(html), ["Team", "GP", ...])` then `table_to_dicts(table)`.
4. Build records, omitting fields the source didn't provide.
5. `merge_store(records, THE_STORE)` — never write the file directly.
6. Register it in the `ADAPTERS` dict and add the name to `DEFAULT_ORDER`.
7. Test with `python ingest_all_sports.py --only x --check`.

For a genuinely new **sport**, also add a `get_<sport>_team_stats()` to `team_stats_provider.py` and wire the lookup into that sport's `run_*()` in `universal_runner.py` — the baseball path is the worked example.

---

## Troubleshooting

Run `refresh_all.bat --debug` first — it prints every URL tried and the raw column names each source returned, which usually identifies the problem in one go.

**`HTTP 403 Forbidden` (RealGM)** — the site is screening automated clients. The script now sends a full browser header set and a Referer through `requests`, which is usually enough. If it persists, open the URL from the error in a browser: if the page loads fine there but the script still gets 403, RealGM is blocking your IP or requires a cookie, and KBL/NZ NBL need a different source.

**`404 from every mirror` (tennis)** — files for past seasons definitely exist, so a 404 on *all* of them is a network block, not missing data. A firewall, VPN, DNS filter or antivirus is intercepting GitHub. The script now tries four mirrors including jsDelivr. Test in a browser: `https://cdn.jsdelivr.net/gh/JeffSackmann/tennis_atp@master/atp_matches_2025.csv`. A 404 for one *current-year* Challenger file only is normal and expected — those are published on a lag.

**`table parsed but contained no usable team rows`** — the page loaded but the column layout moved. `--debug` prints the header row it found. Compare that against what the adapter reads.

**`Statistic type, <year>, is not applicable` (EuroLeague)** — `get_team_stats()` takes the stat type first and the season as a keyword. Use `get_team_stats_single_season(endpoint=..., season=...)`. Note `season` is the season's **start** year: 2025 means 2025-26.

**Everything fails at once** — that is one broken internet connection, not nine broken sites. Exit code 2 means exactly this.

## Rollback

Every file the wiring touched was backed up before it was edited:

```
team_stats_provider.py.bak-20260828
predict_match.py.bak-20260828
universal_runner.py.bak-20260828
models/tennis_predictor.py.bak-20260828
```

Rename one back over the original to undo that change.
