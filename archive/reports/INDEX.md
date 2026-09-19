# MultiSportPredict — where everything is

One page. If you are looking for a file, it is described here.

## Run a slate

| Sport | Command |
|---|---|
| MLB | `venv\Scripts\python.exe run_mlb.py --today --odds` |
| NFL | `venv\Scripts\python.exe run_nfl.py --week N --odds` |
| Tennis | `venv\Scripts\python.exe run_tennis.py ...` |
| Soccer | `venv\Scripts\python.exe run_soccer_batch.py ...` |
| Mixed slate from CSV | `venv\Scripts\python.exe run_slate.py --input input/slate.csv` |

Add `--dry-run` to see the matchups without storing. Add `--no-discord` to keep
it off the server.

## Refresh data before you run

```
venv\Scripts\python.exe ingest_all_sports.py --only mlb
venv\Scripts\python.exe ingest_all_sports.py --only mlb-probables
venv\Scripts\python.exe ingest_nfl_schedule.py --season 2026
venv\Scripts\python.exe ingest_ncaaf.py --dates YYYY-MM-DD
venv\Scripts\python.exe data_guard.py --sport <sport>      # is the data fresh?
```

## Record your results

```
venv\Scripts\python.exe grade_predictions.py --pending     # what is unsettled
venv\Scripts\python.exe grade_predictions.py --auto        # settle mlb/nfl/ncaaf/tennis
venv\Scripts\python.exe grade_predictions.py --manual x.csv  # soccer, KBO, basketball
venv\Scripts\python.exe grade_predictions.py --report      # win rate
venv\Scripts\python.exe backtest_report.py
```

Soccer, KBO and basketball have **no auto-grader**. Those only settle by CSV.

## The engine

| File | What it does |
|---|---|
| `universal_runner.py` | The hub. Every sport's runner calls into it. Also writes to the database. |
| `predict_match.py` | Baseball + soccer + prop maths. The biggest file in the project. |
| `models/` | Per-sport predictors — `nfl_predictor.py`, `tennis_predictor.py`, `baseball_predictor.py` |
| `core/historical_storage.py` | The only thing that writes rows to `multisport_history.db` |
| `grade_predictions.py` | Pulls real results and settles predictions |

## Guards — these exist to stop bad output

| File | What it refuses |
|---|---|
| `data_guard.py` | Stale or thin team data |
| `fixture_guard.py` | Games that are not actually scheduled |
| `embed_builder.py` | Empty or invented Discord embeds |
| `team_stats_provider.py` | Silently substituting a league average for a real team |

If a run says it refused something, that is these files working. Fix the data,
do not bypass the guard.

## Data and output

- `data/` — team stats and schedules the model reads. Check the `updated` field.
- `multisport_history.db` — **the** record. Every prediction and result.
- `output/` — per-run JSON dumps
- `logs/` — run logs

## Discord

- `discord_integration.py` — sending
- `embed_builder.py` — one normaliser, one renderer, for every sport
- `msp_bot.py` + `start_bot.bat` — the bot you run commands through from your phone
- `DISCORD_PUSH_TARGET` in `.env` — `bot`, `webhooks`, or `all`

## archive/

Nothing here is needed to run the model. It is kept because it is history.

| Folder | What is in it |
|---|---|
| `one-off-runs/` | ~150 scripts, each written for one game in June–August |
| `discord-pushes/` | One-off push scripts from the same period |
| `backups/` | `.bak-*` copies made before edits |
| `patches/` | One-time fix scripts that have already been applied |
| `reports/` | Dated analysis write-ups |
| `scratch/`, `scratch-data/`, `scratch-scripts/` | Probe output, test files, loose JSON |
| `legacy-modules/` | Earlier engines superseded by the current ones |

To bring something back: `git mv archive/<folder>/<file> .`

## docs/

Reference that is still true but does not need to be at the root — architecture,
Discord setup, ingestion schedule, results tracking.

## Two things to know

**There is one database that counts.** `multisport_history.db`. If you ever see
a tool proposing `predictions.db` or a per-sport `.db`, it is splitting your
record in two and you will not be able to measure anything.

**Two virtual environments exist.** `venv/` is the real one (has bs4, discord.py,
pybaseball, scipy). `.venv/` does not and should be deleted. Always call
`venv\Scripts\python.exe` explicitly — bare `python` hits the Windows Store stub
and hangs for two minutes.
