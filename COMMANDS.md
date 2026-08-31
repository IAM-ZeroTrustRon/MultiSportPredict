# MultiSportPredict — Command Cheat Sheet

Everything you might need to type, grouped by what you're trying to do.
Last updated 2026-08-28.

---

## Before any command

Open **Git Bash**, then:

```bash
cd /c/MultiSportPredict
```

Every command below assumes you did that first.

If you'd rather use **Command Prompt**, use `cd C:\MultiSportPredict` and swap
the slashes: `venv\Scripts\python.exe` instead of `venv/Scripts/python.exe`.

> **Why `venv/Scripts/python.exe` and not just `python`?**
> Your project's libraries are installed inside `venv`. Plain `python` is a
> different Python that can't see them. Always use the long version.

---

## 1. Get fresh data

```bash
# Everything — this is the daily job
venv/Scripts/python.exe ingest_all_sports.py

# Test every source WITHOUT saving anything
venv/Scripts/python.exe ingest_all_sports.py --check

# Just one or two leagues
venv/Scripts/python.exe ingest_all_sports.py --only mlb
venv/Scripts/python.exe ingest_all_sports.py --only kbo euroleague

# Everything except one
venv/Scripts/python.exe ingest_all_sports.py --skip soccer

# Show me the adapter names
venv/Scripts/python.exe ingest_all_sports.py --list

# Show every URL tried and every column found (use when something breaks)
venv/Scripts/python.exe ingest_all_sports.py --only kbo --debug

# Ignore saved copies and download everything fresh
venv/Scripts/python.exe ingest_all_sports.py --no-cache
```

**Adapter names:** `mlb`, `mlb-probables`, `mlb-players`, `kbo`, `euroleague`,
`kbl`, `nznbl`, `tennis`, `soccer`

**What the exit code means:** `0` = all good. `1` = some sources failed, the
rest still saved. `2` = everything failed (usually means no internet).

---

## 2. Run a prediction

```bash
# Soccer
venv/Scripts/python.exe universal_runner.py --sport soccer \
  --home "Bayern Munich" --away "VfB Stuttgart" \
  --league Bundesliga --market-total 3.0 --store-to-db

# Baseball (MLB or KBO)
venv/Scripts/python.exe universal_runner.py --sport baseball \
  --home "KT Wiz" --away "LG Twins" --league KBO \
  --market-total 9.5 --markets nrfi strikeouts --store-to-db

# Basketball
venv/Scripts/python.exe universal_runner.py --sport basketball \
  --home "Real Madrid" --away "FC Barcelona" \
  --league EuroLeague --market-line -4.5 --store-to-db

# Tennis
venv/Scripts/python.exe universal_runner.py --sport tennis \
  --home "Jannik Sinner" --away "Carlos Alcaraz" --store-to-db
```

Add `--push-discord` to any of them to send it to Discord.

**Not sure what flags exist?**

```bash
venv/Scripts/python.exe universal_runner.py --help
```

**Important:** always use `--store-to-db`. If it isn't stored, it can't be
graded later, and your win-rate record won't include it.

---

## 3. Track results and see your record

```bash
# What's waiting for a result? (also writes pending_results.csv)
venv/Scripts/python.exe grade_predictions.py --pending

# Fetch final scores and grade them (MLB works automatically today)
venv/Scripts/python.exe grade_predictions.py --auto

# Grade from a spreadsheet you filled in yourself
venv/Scripts/python.exe grade_predictions.py --manual pending_results.csv

# Show the win-rate record
venv/Scripts/python.exe grade_predictions.py --report

# The normal daily one — grade, then show the record
venv/Scripts/python.exe grade_predictions.py --auto --report

# Post the record to Discord
venv/Scripts/python.exe grade_predictions.py --report --push-discord

# Narrow it down
venv/Scripts/python.exe grade_predictions.py --report --sport soccer
venv/Scripts/python.exe grade_predictions.py --report --days 30
```

### Grading a sport that has no automatic score feed

1. `venv/Scripts/python.exe grade_predictions.py --pending`
2. Open `pending_results.csv` in Excel
3. Type the final scores into the `home_score` and `away_score` columns
4. Save it
5. `venv/Scripts/python.exe grade_predictions.py --manual pending_results.csv --report`

---

## 4. When something's broken

```bash
# Why are sources being refused? Saves diagnostic_report.txt
venv/Scripts/python.exe diagnose_sources.py

# Download candidate pages so they can be inspected
venv/Scripts/python.exe probe_sources.py

# Read today's log (Git Bash)
cat logs/ingest_20260828.log

# Just the summary lines
grep "\[OK\|\[FAIL" logs/ingest_20260828.log
```

**Reading a failure:**

| Message | What it means |
|---|---|
| `HTTP 403` | The site is blocking automated access (Cloudflare) |
| `HTTP 404` | The page or file isn't there |
| `table parsed but contained no usable rows` | Page loaded, but its layout changed — run with `--debug` |
| everything fails at once | Your internet, not the sites |

---

## 5. Save your work to GitHub

```bash
# One-time cleanup if git complains about a lock or a worktree
rm -f .git/index.lock
rm -rf .git/worktrees/i-want-to-run-the-soccer-match-between
git worktree prune

# Normal save
git status --short
git add -A
git commit -m "describe what changed"
git push origin main
```

Repo: https://github.com/IAM-ZeroTrustRon/MultiSportPredict

---

## 6. Schedule the daily refresh

This one **must** be Command Prompt, not Git Bash — `schtasks` is a Windows
built-in and Git Bash mangles it.

```
schtasks /create /tn "MultiSportPredict Daily Refresh" /tr "C:\MultiSportPredict\refresh_all.bat" /sc daily /st 06:00 /f
```

```
schtasks /query  /tn "MultiSportPredict Daily Refresh"     see it
schtasks /run    /tn "MultiSportPredict Daily Refresh"     run it now
schtasks /delete /tn "MultiSportPredict Daily Refresh" /f  remove it
```

---

## 7. Where things live

| Path | What's in it |
|---|---|
| `data/baseball_stats.json` | MLB + KBO team numbers |
| `data/mlb_probables.json` | Today's and tomorrow's starting pitchers |
| `data/euroleague_stats.json` | EuroLeague team ratings |
| `data/basketball_stats.json` | KBL + NZ NBL *(not working yet)* |
| `data/soccer_stats.json` | Auto-scraped soccer *(not working yet)* |
| `data/team_stats/soccer_stats.json` | Hand-entered soccer — what soccer actually uses today |
| `data/tennis/atp_matches.csv` | Tennis match history for Elo *(not working yet)* |
| `multisport_history.db` | Every prediction and its result |
| `logs/` | One log file per day |
| `data/cache/ingest/` | Saved copies of downloaded pages |

**Reference docs:** `DAILY_INGESTION.md`, `RESULTS_TRACKING.md`,
`NFL_ENGINE_PLAN.md`, `ADDING_SPORTS_AND_LEAGUES.md`

---

## 8. Current status

**Working:** MLB team stats (with home/away splits and last-10 form), MLB
probable pitchers, KBO team stats, EuroLeague ratings.

**Not working:** KBL and NZ NBL (RealGM blocks automated access), tennis
(the data files moved), soccer auto-scrape (FBref blocks automated access),
MLB player props (FanGraphs blocks automated access).

Soccer predictions still run — they use the hand-entered store instead.

---

## 9. Undo something

Every file that was edited has a backup beside it:

```bash
ls *.bak-*
cp team_stats_provider.py.bak-20260828 team_stats_provider.py   # restore one
```
