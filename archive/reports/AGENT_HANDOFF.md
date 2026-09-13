# MultiSportPredict — agent handoff

**For: Claude Code / Cline working in `C:\MultiSportPredict`**
**Written: 2026-08-30. Everything below was verified on disk on that date.**

Read this whole file before running anything. It exists because two previous
sessions each broke the environment by acting on stale information, and both
times the failure looked like a hang rather than an error.

---

## 0. Non-negotiables

**Every Python command starts with `venv/Scripts/python.exe`.**

```bash
venv/Scripts/python.exe <script>.py
```

Not `python`. Not `python3`. Not `.venv/Scripts/python.exe`.

### Why this keeps going wrong

There are **two** virtualenvs in this repo and they are not equivalent:

| | `venv/` | `.venv/` |
|---|---|---|
| numpy, pandas, requests, scipy | yes | yes |
| **bs4** | **yes** | no |
| **discord.py** | **yes** | no |
| **pybaseball** | **yes** | no |
| site-packages | 278 | fewer |

`venv/pyvenv.cfg` is valid, Python 3.13.14, with `python.exe`, `pip.exe` and
`activate` present. **It is not broken.** Two sessions have now asserted that it
is; both were wrong, and both "fixed" it by switching to something worse.

Bare `python` on this machine resolves to the Microsoft Store stub at
`C:\Users\RonRi\AppData\Local\Microsoft\WindowsApps\python3`. It does not error —
**it blocks forever.** A previous session ran `python3 --version` and the command
was still hanging at the 120-second timeout. If a command in this repo appears to
hang, the first thing to check is which interpreter it invoked.

`sys.path.insert(0, str(ROOT))` at the top of these scripts is **not** a
substitute. It resolves this project's own modules. It does nothing for
installed packages, so under system Python `run_tennis.py` dies on `import
scipy` and `msp_bot.py` dies on `import discord`.

### Shell

Git Bash. Forward slashes. Line continuation is `\`, not `^`. Only `schtasks`
needs Command Prompt.

---

## 1. Verified state as of 2026-08-30

```
data/soccer_stats.json      150 teams   Championship 24, Eredivisie 18, Liga MX 18,
                                        MLS 30, Premier League 20, Serie A 20, Serie B 20
data/baseball_stats.json     40 teams   MLB 30, KBO 10 (2026 season, 111-113 games)
data/nfl_stats.json          32 teams   2025 season, held as an early-season prior
data/euroleague_stats.json   20 teams
data/tennis/players.json      6 players  <- FABRICATED, see §3
data/tennis/matches.csv      MISSING    <- blocks all real tennis

multisport_history.db       147 rows, 51 graded, integrity ok
.env                        7 keys, DISCORD_PUSH_TARGET=bot
```

All of `discord_integration.py`, `universal_runner.py`, `run_mlb.py`,
`run_tennis.py`, `ingest_tennis.py`, `grade_predictions.py`, `mcp_server.py`,
`msp_bot.py`, `core/historical_storage.py` compile clean.
`mcp_server.py --selftest` passes with 15 tools.

---

## 2. Tasks, in order

### 2.1 Build the tennis store — blocks everything else in tennis

```bash
venv/Scripts/python.exe ingest_tennis.py
```

Writes `data/tennis/matches.csv`, `players.json`, `atp_matches.csv`.
Takes a few minutes; it downloads one archive per tour per season.

**Do NOT run `ingest_all_sports.py --only tennis`.** That adapter reads
Jeff Sackmann's `tennis_atp` GitHub repo, which is no longer publicly
reachable — the GitHub API returns 403 from this machine, re-verified
2026-08-30. `ingest_tennis.py` exists specifically because of that, and reads
`http://www.tennis-data.co.uk` instead.

`venv` has no `openpyxl`. `ingest_tennis.py` carries a stdlib `.xlsx` reader as a
fallback and it has been tested against a synthetic workbook (shared strings,
date serials, compound surnames all parse). If it still complains about the
format: `venv/Scripts/python.exe -m pip install openpyxl`.

Expected output ends with a match count, a player count, a date span, and a
per-surface breakdown. If it reports 0 matches it wrote nothing and the old
store is untouched.

### 2.2 Run the ATP card

Six US Open R1 matches starting before 13:00 ET on 2026-08-30. Times from Sky
Sports are UK: 16:00 BST = 11:00 ET, 17:00 = 12:00 ET, "midnight" = night
session and is excluded.

```bash
venv/Scripts/python.exe run_tennis.py --tournament "US Open" --round R1 --surface hard \
  --match "Coleman Wong vs Tommy Paul" \
  --match "Jiri Lehecka vs Pablo Carreno Busta" \
  --match "Miomir Kecmanovic vs Denis Shapovalov" \
  --match "Luca Van Assche vs Cameron Norrie" \
  --match "Martin Landaluce vs Jacob Fearnley" \
  --match "Daniil Medvedev vs Hugo Gaston"
```

Nothing is pushed by this. It prints a review table and saves
`data/tennis_review.json`.

You may type real names — the resolver maps `Carlos Alcaraz` to the feed's
`Alcaraz C.`, works right-to-left so compound surnames survive
(`Roberto Carballes Baena` → `Carballes Baena R.`), and **refuses** rather than
guessing when a surname is shared (`Zverev` → ambiguous, stops). 15/15 resolver
cases pass.

If a name will not resolve, find the store's spelling — do not edit the
resolver:

```bash
venv/Scripts/python.exe run_tennis.py --list "part of the name"
```

Then push the ones worth pushing, by line number:

```bash
venv/Scripts/python.exe run_tennis.py --push 1 2 3 4 5 6
```

### 2.3 Run the KBO slate

Five games, all 18:00 KST = 05:00 ET. Home team is listed **first**; the
mykbostats feed lists them as `away @ home`, so these are already flipped.

```bash
venv/Scripts/python.exe run_mlb.py --league KBO \
  --match "Samsung Lions vs KT Wiz" \
  --match "Lotte Giants vs LG Twins" \
  --match "Hanwha Eagles vs NC Dinos" \
  --match "KIA Tigers vs SSG Landers" \
  --match "Doosan Bears vs Kiwoom Heroes"
```

This one pushes as it runs (add `--no-discord` to suppress).

Four of the five carry a "Chance of Rainout" flag. A rained-out game will sit
ungraded — that is correct behaviour, not a bug.

### 2.4 Optional cleanup

Nine predictions in the database are for fixtures that were never scheduled:
IDs **128, 129, 130, 131** (Serie A: AC Milan v Inter, Juventus v Roma,
Napoli v Lazio, Atalanta v Fiorentina — the real 2026-08-29 card was
Fiorentina-Frosinone, Monza-Udinese, Sassuolo-Torino, Juventus-Parma) and
**118, 119, 120** plus the other two KBO rows dated 2026-08-29, where every
team played but not one of the predicted pairings existed.

They are ungraded so they do not affect the record; they clutter `--pending`
forever. Delete them only if asked. **See §4 before touching the database.**

---

## 3. Traps

### 3.1 `data/tennis/players.json` is fabricated

Its six entries carry hand-written ratings (`"elo": 1810.0, "hard_elo": 1840.0`)
that were generated by a model, not derived from results. A previous handoff
described them as "curated ratings". They are the same class of artefact as the
fabricated KBO stats that were rejected earlier in this project.

`ingest_tennis.py` overwrites this file with counts derived from real matches.
**Do not wire the Elo engine to read the invented numbers instead of fixing the
missing CSV.** That converts a visible gap into an invisible one.

### 3.2 Nothing validates that a fixture exists

On 2026-08-29 the model produced nine predictions for games that were never
scheduled. They carried confidence scores, edges and Discord embeds, and were
indistinguishable from real ones. `data_guard.py` checks team *data*; nothing
checks the *matchup*.

**This is the highest-value unbuilt feature in the repo.** Validate every
matchup against a schedule feed before predicting, and refuse on a miss.

### 3.3 Home and away get reversed when typed by hand

Confirmed on NC Dinos v LG Twins, Lotte Giants v KIA Tigers (2026-08-26) and
Club Leon v Atlante (2026-08-28) — all logged with the road team as home. The
result still grades, but home-field advantage was applied to the wrong side when
the number was produced. Read the matchup from a feed rather than accepting the
typed order. `run_mlb.py` already does this for MLB and prints
`[home/away] schedule says ...`.

### 3.4 The duplicate-push suppressor used to report success

`_broadcast_embed()` in `discord_integration.py` returned `len(targets)` when the
6-hour dedup window swallowed a message, so the caller printed `[OK] pushed`
having sent nothing, and the explanation went to `logger.info` — invisible,
because nothing in this project calls `logging.basicConfig`.

Fixed 2026-08-30: it returns `0` and prints `[SKIP] ... NOTHING WAS SENT`.
`clear_dedup_cache()` forces a resend. Do not revert this.

### 3.5 CRLF

Most files on disk are CRLF. A patch script that reads them raw will fail every
`\n`-based match; one that rewrites them as LF buries a five-line change in a
whole-file diff. Read normalised, match in LF, write back in the file's original
ending.

### 3.6 Blocked sources

Verified unreachable from this machine: FBref, FanGraphs, RealGM,
Pro-Football-Reference (Cloudflare); ESPN `site.api` (Akamai); GitHub raw,
jsDelivr and the GitHub API (403).

Working: `statsapi.mlb.com`, `mykbostats.com`, `football-data.co.uk`,
`tennis-data.co.uk`, `api.the-odds-api.com`, `site.web.api.espn.com`,
`sports.core.api.espn.com`.

No reachable source publishes xG. All soccer xG is estimated from goals and
tagged `data_tier: 2`. Do not present it as measured xG.

---

## 4. Never run sqlite against the database over a network mount

Doing so wrote every row and then failed on `conn.commit()` with
`disk I/O error`, leaving a hot `multisport_history.db-journal`. The data was on
disk but uncommitted: the next process to open the file would have rolled all of
it back, silently.

Run database work from Windows, against the local file. If a `.db-journal` or
`.db-wal` sits next to the database when nothing is running, the last write did
not commit — check `PRAGMA integrity_check` before trusting the contents, and
back the file up before doing anything else.

---

## 5. Where a push goes

`DISCORD_PUSH_TARGET` in `.env`, read by `push_mode()` in
`discord_integration.py`:

| value | webhooks | bot channel |
|---|---|---|
| `bot` (current) | no | yes |
| `webhooks` | yes | no |
| `all` | yes | yes |
| anything else | yes | yes (falls back to `all`) |

`load_dotenv()` runs with `override=False`, so a shell variable beats `.env`.
A one-off override needs no file edit:

```bash
DISCORD_PUSH_TARGET=all venv/Scripts/python.exe run_tennis.py --push 1
```

Multi-webhook fan-out already works and needs no new code —
`DISCORD_WEBHOOK_URLS` accepts space- or comma-separated URLs, deduplicated
against `DISCORD_WEBHOOK_URL` and `DISCORD_RECOMMENDATIONS_WEBHOOK_URL`.

---

## 6. Verification

```bash
venv/Scripts/python.exe -m py_compile run_mlb.py run_tennis.py ingest_tennis.py \
  discord_integration.py universal_runner.py grade_predictions.py \
  mcp_server.py msp_bot.py core/historical_storage.py

venv/Scripts/python.exe mcp_server.py --selftest     # expect 15 tools, 0 failures
venv/Scripts/python.exe data_guard.py                # stale / thin / wrong-season
venv/Scripts/python.exe grade_predictions.py --report
./msp status
```

`msp` no longer falls back to system Python. If the venv is missing it now says
which interpreter it wanted and exits, rather than silently invoking the Store
stub and hanging.

---

## 7. Standing instructions from Ron

- Plain, short, direct. Facts and steps. No fluff, no double talk, no ambiguity.
- Do the task; do not hand back instructions for him to run when you can run it.
- Never paste a secret into a conversation. `.env` is gitignored and untracked;
  values go from their source into that file and nowhere else.
- Do not push to Discord without being asked. Predict, show the table, wait.
