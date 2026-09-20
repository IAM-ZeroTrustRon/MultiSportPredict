# Handoff — Cline

You edit files in this repo. Read `STATE_OF_MODEL.md` for what the project is
and `INDEX.md` for where things live. This page is the working agreement.

## Non-negotiables

**1. One database.** `multisport_history.db`, written only by
`core/historical_storage.py`. Do not add a second store. `predictions.db` is
dead and lives in `archive/scratch-data/`; a per-sport `.db` splits the record
and makes the model unmeasurable.

**2. Never commit half a feature.** On 2026-09-11 `run_mlb.py` was committed
with `--home-sp-limit` flags while `universal_runner.py` and
`predict_match.py` — which implement them — were left uncommitted. HEAD
crashed with `TypeError` on every MLB run. If a change spans files, commit the
files together or not at all.

**3. Preserve line endings.** This repo is CRLF. Read as bytes, normalise to
LF for matching, write back in the original ending. A patch that flips line
endings turns a three-line diff into a whole-file diff.

**4. Back up before patching.** `cp file.py file.py.bak-<what>`. Every fix in
this project has one. They live in `archive/backups/` once superseded.

**5. Anchor edits on exact unique strings and refuse if the anchor is missing
or ambiguous.** Do not patch by line number.

**6. Never bypass a guard.** `data_guard.py`, `fixture_guard.py`,
`embed_builder.py` and `team_stats_provider.py` exist to refuse bad output. If
one refuses, the data is wrong. Fix the data.

**7. Do not touch files you were not asked about.** You got this right in
September — you committed three files and left the rest alone because you had
no context on them. Keep doing that.

## The bug class to hunt

Every serious bug here has been the same shape: **a lookup that fails and
returns a plausible default instead of an error.**

```python
value = stats.get("era", 4.20)        # a missing team now has a league ERA
prob   = result.get("home_win", 0.5)  # a failed model now shows a coin flip
name   = player.get("name", "Player 1")
```

When you see `.get(key, fallback)` in this codebase, ask what happens when the
key is genuinely absent. If the answer is "it produces a number that looks
real", that is a bug even if nothing has crashed. The fix is to return `None`
and refuse downstream, not to pick a better default.

Found this way so far: fabricated sharp consensus, hardcoded strikeout rates,
a K/9 unit error that inflated every NRFI ever produced, and first-half
averages overwriting 32 teams' prior season.

## Open tasks, in order

**1. Grade the backlog — 198 ungraded predictions.**
```bash
python grade_predictions.py --auto        # settles mlb, nfl, ncaaf, tennis
```
That leaves 78 rows (soccer 86 minus overlap, KBO, basketball) with no auto
source. Building a soccer auto-grader off ESPN results is the highest-value
task in the project — it is the largest ungraded block by far.

**2. Retry the tennis ingest.** `ingest_tennis.py` was fixed on 09-19 to try
`https://` before `http://` and to print the HTTP status on failure. It has
not been re-run. The store is 21 days stale.
```bash
python ingest_tennis.py --years 2025 2026 --tours atp wta
```
If it still fails, the status codes will now say why.

**3. Fix the fixture guard's season blindness.** `nfl_schedule.json` holds 544
games across 2025 and 2026. A 2026 Week 1 lookup can match a 2025 game —
observed with SF@LAR matching 2025-10-03 week 5. Filter on season.

**4. Stop `(2025)` leaking into output.** NFL runs display
`New England Patriots (2025)` and would store that as the team name, which
will not match ESPN at grading time. Strip the season tag at the display and
storage boundary, not in the store.

**5. Fix the NFL Odds API URL.** `run_nfl.py` builds
`api.opticodds.com/api/v3/v4/sports/...` — two different APIs spliced
together. `live_odds.py` already has the correct base.

**6. Replace substring error classification in `data_guard.py`.** Lines 237
and 312 test `"game" in message`. Add a `kind` attribute to `Problem` so
tennis can say "matches" without silently reclassifying its own errors.

**7. Build the NCAAF predictor.** Results ingest and auto-grader exist;
nothing makes a prediction. Scope: Big 12 and MAC only. Use 2025 as prior,
exclude FCS opponents, margin SD ~17–19 rising with the spread.

## Environment

- Git Bash, forward slashes. `venv/Scripts/python.exe`.
- Never run sqlite writes over a network mount — the commit fails and leaves a
  hot journal that rolls back silently.
- Python 3.13 in the venv. Backslashes in f-strings (PEP 701) are 3.12+ only.
- `nul` in the root cannot be moved or deleted. It is gitignored. Leave it.

## Commit messages

Say what changed and why it was wrong, not just what the code now does. The
commit log is the only record of why a constant has the value it has.
