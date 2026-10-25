## Manual score-market prices — repaired October 24, 2026

`msp.py run --sport basketball` and `--sport ncaaf` now omit automatic `--odds`
when you supply `--moneyline`, `--spread` or `--total`. Do not explicitly combine
`--odds` with those manual flags. Prices are HOME/AWAY; spread line applies to
HOME; total prices are OVER/UNDER. Repeated total/spread flags support alternatives.
The runner verifies actual home/away from the fixture; pair manual prices accordingly.

Read-only NHL observation report (separate from wagering returns):

```bash
venv/Scripts/python.exe -u run_nhl.py --observations
```

Historical examples elsewhere in this guide are syntax examples, not today's slate.

## MultiSportPredict — Git Bash command reference

Updated October 19, 2026. Copy one complete command into Git Bash. No input prompts or placeholder values are used. Match examples show command syntax, not a verified schedule: edit the names, date, league and tournament before running. Omit --date to use today in America/New_York; table-tennis date filtering uses UTC.

## Start here

```bash
cd /c/MultiSportPredict
```

Refresh all sports, then grade saved selections. Independent refresh stages continue after failures; inspect the summary before relying on a sport with failed data.

```bash
venv/Scripts/python.exe -u msp.py daily --all
```

Refresh only, without creating picks:

```bash
venv/Scripts/python.exe -u msp.py refresh --all
```

Grade all sports, including older pending selections. The hourly automation also runs this. Each pass backs up the database. Results that are unavailable remain unresolved for retry; automatic grading cannot manufacture a verified result.

```bash
venv/Scripts/python.exe -u msp.py grade --all
```

## Review and records

The fresh reporting period begins October 20, 2026. Settled historical records remain available.

```bash
venv/Scripts/python.exe -u msp.py record
```

```bash
venv/Scripts/python.exe -u msp.py record --all-time
```

```bash
venv/Scripts/python.exe -u msp.py pending
```

After running a match, show the latest successful saved snapshot:

```bash
venv/Scripts/python.exe -u msp.py show --latest
```

Optional: send that reviewed snapshot to configured Discord destinations. This command sends a message. Running, refreshing and grading do not send messages.

```bash
venv/Scripts/python.exe -u msp.py push --latest
```

Show uses the latest successful workflow run across all sports. Check the sport and matchup before sending. Older runs can be selected by the exact RUN_ID printed when they were saved, using --run-id.

## Tennis — ATP and WTA

```bash
venv/Scripts/python.exe -u msp.py run --sport tennis --match "Matteo Arnaldi vs Lorenzo Musetti" --tournament "Lyon" --surface hard --best-of 3 --date 2026-10-19
```

The date must agree with the matched odds fixture. A tournament label does not prove that fixture exists. Correct a mismatch rather than changing the date blindly.

## Tennis — Challenger research

```bash
venv/Scripts/python.exe -u msp.py run --sport tennis-research --match "Dominik Palan vs Semen Pankin"
```

This delegates to run_tennis_full.py. Its research runner does not accept a game-date flag and can refuse players outside its registry. A names-only command cannot fill unavailable history. Research output remains separate from graded ordinary selections; it is not automatically included in the accuracy record.

## Baseball — MLB and KBO

```bash
venv/Scripts/python.exe -u msp.py run --sport mlb --match "New York Yankees vs Baltimore Orioles" --date 2026-10-19
```

```bash
venv/Scripts/python.exe -u msp.py run --sport kbo --match "KIA Tigers vs LG Twins" --date 2026-10-19
```

Run the entire date’s available baseball slate:

```bash
venv/Scripts/python.exe -u msp.py slate --sport mlb --date 2026-10-19
```

```bash
venv/Scripts/python.exe -u msp.py slate --sport kbo --date 2026-10-19
```

Home team goes first. Probable pitchers and lineups are taken from available source data; an unannounced starter remains unavailable. MLB player metrics use official MLB Stats API plus measured Baseball Savant wOBA.

## Football — NFL and NCAAF

```bash
venv/Scripts/python.exe -u msp.py run --sport nfl --match "San Francisco 49ers vs Washington Commanders" --date 2026-10-19
```

```bash
venv/Scripts/python.exe -u msp.py run --sport ncaaf --match "Alabama Crimson Tide vs Tennessee Volunteers" --date 2026-10-19
```

NFL resolves a specific upcoming event in the requested season. Started, completed or mismatched fixtures are refused.

## Basketball

```bash
venv/Scripts/python.exe -u msp.py run --sport basketball --league KBL --match "Suwon KT Sonicboom vs Ulsan Mobis Phoebus" --date 2026-10-19
```

```bash
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --match "New York Knicks vs Philadelphia 76ers" --date 2026-10-20
```

```bash
venv/Scripts/python.exe -u msp.py slate --sport basketball --league NBA --date 2026-10-19
```

NBA reviews now show Home/Away team names, signed EV percentages, and provisional 1H/1Q score estimates. Period estimates do not carry probabilities, EV or betting recommendations. `msp.py show --latest` prints the readable saved review; add `--json` for full-precision JSON. See [NBA review details](docs/NBA_REVIEW.md).

Score-based leagues: NBA, WNBA, NCAAB, NCAAW, KBL, NZNBL and BBL. Australian NBL differs from NZNBL. NBL and EuroLeague delegate to the international metrics runner and retain its coverage limits; do not assume automatic fixture verification or priced markets for every league.

## Soccer

```bash
venv/Scripts/python.exe -u msp.py run --sport soccer --league "Premier League" --match "Liverpool vs Aston Villa" --date 2026-10-19
```

Home team goes first. A date and home/away fixture check runs before the model. Current football-data team xG fields remain explicitly goal-derived estimates, not measured xG.

## Table tennis — one root workflow

```bash
venv/Scripts/python.exe -u msp.py run --sport table-tennis --match "Jan Trefny vs Richard Krejci" --date 2026-10-19
```

This calls the root run_table_tennis.py, not the separate engine-folder copy. The provider route needs configured results/odds access. When using the copied-page route, first update the saved match configuration and paste fresh page text; that fallback requires confirmed identity, timezone-aware start, format and fresh quotes.

```bash
venv/Scripts/python.exe -u msp.py run --sport table-tennis --config data/table_tennis/current_match_config.json
```

Table-tennis quote and point-score coverage can be unavailable. Do not disable freshness, identity or point-total checks. Detailed guidance: TABLE_TENNIS_COMMANDS.md.

## Batch several matches

Repeat --match within one sport:

```bash
venv/Scripts/python.exe -u msp.py slate --sport tennis --match "Matteo Arnaldi vs Lorenzo Musetti" --match "Lorenzo Sonego vs Moise Kouame" --tournament "Lyon" --surface hard --best-of 3 --date 2026-10-19
```

A mixed-sport slate example is saved in slate_workflow.json. Edit its filled-in values to the actual fixtures, then run:

```bash
venv/Scripts/python.exe -u msp.py slate --file slate_workflow.json
```

## Refresh one sport

```bash
venv/Scripts/python.exe -u msp.py refresh --sport mlb
```

```bash
venv/Scripts/python.exe -u msp.py refresh --sport kbo
```

```bash
venv/Scripts/python.exe -u msp.py refresh --sport soccer
```

```bash
venv/Scripts/python.exe -u msp.py refresh --sport tennis
```

```bash
venv/Scripts/python.exe -u msp.py refresh --sport nfl
```

```bash
venv/Scripts/python.exe -u msp.py refresh --sport ncaaf
```

```bash
venv/Scripts/python.exe -u msp.py refresh --sport basketball
```

```bash
venv/Scripts/python.exe -u msp.py refresh --sport table-tennis
```

## Cleanup — exceptional maintenance

Historical cleanup was performed after verified grading on October 19. Routine hourly grading never deletes records. Preview unresolved selections dated before October 19:

```bash
venv/Scripts/python.exe -u msp.py cleanup --before 2026-10-19
```

The following command permanently removes the previewed unresolved historical selections after a verified SQLite backup and an exact deleted-record manifest. It preserves settled selections and events on/after the cutoff. Use it only when intentionally repeating cleanup:

```bash
venv/Scripts/python.exe -u msp.py cleanup --before 2026-10-19 --apply
```

## When a command refuses

Inspect the printed log path. A failed lookup, absent price, wrong date, missing history or inaccessible result is a data issue. Fix the source or fixture; do not bypass guards. A zero exit from a legacy runner is not enough: this workflow verifies that a forecast was actually saved. Logs and immutable run snapshots are in output/workflow/. No command here places a wager.
