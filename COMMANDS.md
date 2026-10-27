## NBA player-prop research — October 26, 2026

Git Bash, from the project folder:

```bash
cd /c/MultiSportPredict
```

Refresh the player-game store from public ESPN box scores (no paid calls):

```bash
venv/Scripts/python.exe -u ingest_basketball_props.py --days 21
```

Project one verified fixture. This is research output: no EV, no stake, no bet.

```bash
venv/Scripts/python.exe -u msp.py run --sport basketball --props --league NBA --date 2026-10-28 --match "Miami Heat vs Atlanta Hawks"
```

The same run through the standalone runner, with a player filter and a dry run that
writes nothing:

```bash
venv/Scripts/python.exe -u run_basketball_props.py --date 2026-10-28 --match "Miami Heat vs Atlanta Hawks" --player "Bam Adebayo" --dry-run
```

Held-out minutes and stat comparison (chronological, whole-game split):

```bash
venv/Scripts/python.exe -u run_basketball_props.py --validate
```

Optional fitted minutes model instead of the default transparent baseline:

```bash
venv/Scripts/python.exe -u run_basketball_props.py --validate --minutes-model candidate
```

Project a single player through the same workflow route, with a dry run:

```bash
venv/Scripts/python.exe -u msp.py run --sport basketball --props --league NBA --date 2026-10-28 --match "Miami Heat vs Atlanta Hawks" --player "Mouhamed Gueye" --dry-run
```

A `--dry-run` is recorded as `preview`, not as a failed run. Props never enter the
team-pick ledger; `msp.py record` is unaffected by them.

Output rules worth knowing: a missing projection prints `--`, never `0.0`; `STALE`
means the rotation history is older than 30 days or from a previous season;
`CROSS-SEASON` means the last appearance came from a different NBA season; an
unavailable player is refused and shows `--` for every field. Availability is taken
only from the fixture's own payload: the event id and both team ids are verified,
and the snapshot expires after 6 hours. A designation dated in the future is
rejected; an old one is disclosed rather than deleted. Only `AVAILABLE`, `ACTIVE` or
`CLEARED` is actionable — any unrecognised status, and any player who is not listed,
remains UNKNOWN rather than available. Only a scheduled fixture that has not started
can be projected.

## Basketball league resolution — October 26, 2026

Git Bash, from the project folder (or select Git Bash in the VS Code terminal):

```bash
cd /c/MultiSportPredict
```

Australian NBL is `NBL`; New Zealand's domestic competition is `NZNBL`.
The New Zealand Breakers play in Australian NBL. Supported public ingestion
now runs automatically when a named matchup is missing, stale or short of history.

This upcoming fixture was verified during the October 26 source check:

```bash
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBL --match "Perth Wildcats vs Sydney Kings" --date 2026-10-28
```

To permit disclosed hybrid inputs if the real team/fixture data cannot be found,
add `--exploratory` to the same command. An eligible normal forecast still uses
the normal model. This flag also accepts unlisted competitions; those use explicit
assumptions when no supported source exists. First named team is assumed home
only if the fixture cannot be verified; the output marks that assumption.

```bash
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBL --match "Perth Wildcats vs Sydney Kings" --date 2026-10-28 --exploratory
```

Read-only check, without recording picks or fetching bookmaker odds:

```bash
venv/Scripts/python.exe -u run_basketball.py --league NBL --match "Perth Wildcats vs Sydney Kings" --date 2026-10-28 --dry-run --no-refresh
```

Separate records:

```bash
venv/Scripts/python.exe -u msp.py record --all-time
venv/Scripts/python.exe -u msp.py record --cohort exploratory
venv/Scripts/python.exe -u msp.py record --cohort high-probability
```

Basketball manual side prices follow the named match order (first/second), and
handicap applies to the first team. The runner remaps prices/handicap if the feed
reverses venue order; totals are unchanged. NBA/NCAAF direct score runners retain
their own HOME/AWAY flag contract. Do not mix `--odds` and manual price flags.
For leagues without a verified odds adapter, missing prices remain unavailable;
they do not prevent an unpriced forecast. Exploratory EV is scenario-only,
assumed uncertainty is disclosed, and no Kelly stake is recorded.

## Tracked pregame odds and CLV — October 25, 2026

No scheduler is active. These commands collect only eligible tracked predictions
and compare last-observed prematch references, not guaranteed sportsbook closes.
No tracked fixture in the window means no paid odds request. A collection request
may cost multiple API credits; its report includes available quota headers.

```bash
venv/Scripts/python.exe -u closing_collector.py --league NHL
venv/Scripts/python.exe -u clv.py --sport nhl --json
```

Default collection window is 30 to 1 minutes before kickoff, with provider quotes
at most five minutes old. Original bookmaker and fresh official fixture identity
must match. A provider kickoff later than the league's is tolerated up to 15
minutes (the provider mirrors the schedule and was measured exactly 600s late);
the league kickoff stays the binding deadline and an earlier provider time is
always refused. These commands do not create a forecast or send Discord. Missing
predictions/closes remain unavailable. Do not fabricate a historic opening quote.

## Read-only soccer fixture verification — October 25, 2026

This checks a real upcoming card without running a model, storing picks or sending
Discord. It prints the verified home/away, project date, kickoff and event ID.
This dated example was verified during the October 25 repair; it is not a perpetual slate.

```bash
venv/Scripts/python.exe -u fixture_guard.py soccer "SV Elversberg" "Mainz" 2026-10-30 "Bundesliga"
```

Normal dated soccer runs through msp.py use the repaired guard automatically.
If you supply teams in reversed order, side prices and the signed handicap follow
the named teams when the runner corrects orientation. Totals/draw prices stay unchanged.
Unknown competitions are refused; use a configured league, never an EPL substitute.

## Manual score-market prices — repaired October 24, 2026

`msp.py run --sport basketball` and `--sport ncaaf` now omit automatic `--odds`
when you supply `--moneyline`, `--spread` or `--total`. Do not explicitly combine
`--odds` with those manual flags. For the unified basketball runner, side prices
follow the named match order and are remapped to verified home/away; the spread
line applies to the first named team. Direct `run_ncaaf.py` prices remain HOME/AWAY.
Legacy direct score-runner spread line applies to
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

Tennis grading keys each result on the match's own date (ESPN returns the whole draw for any
query date), recovers only uniquely resolved players, refuses swapped-side duplicate writes, and
settles by market rule: a match-winner bet survives a retirement, games/sets markets need a
completed match, and a walkover voids every market as a refunded push.

```bash
venv/Scripts/python.exe -u grade_predictions.py --auto --sport tennis --days 7
venv/Scripts/python.exe -u grade_predictions.py --pending --sport tennis
```

PASS/INFO rows are never graded — they are not bets and stay in the database as calibration data.

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

Score-based leagues: NBA, WNBA, NCAAB, NCAAW, Australian NBL, KBL, NZNBL and BBL. Australian NBL is separate from New Zealand NZNBL. EuroLeague retains its international metrics runner. Named basketball matches attempt public ingestion when needed; `--exploratory` authorizes disclosed fallback when verified inputs remain unavailable. Automatic odds coverage is separate from schedule/history coverage.

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

---

## Tonight: copy and paste (verified slate, 2026-10-26 America/New_York)

Run everything from Git Bash:

```bash
cd /c/MultiSportPredict
```

Prices and schedules are discovered automatically; `--odds` is the only flag you need for pricing.

### NBA team picks (verified fixtures, 2026-10-26)

```bash
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --date 2026-10-26 --match "Phoenix Suns vs Oklahoma City Thunder" --odds
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --date 2026-10-26 --match "Indiana Pacers vs Milwaukee Bucks" --odds
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --date 2026-10-26 --match "Golden State Warriors vs Denver Nuggets" --odds
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --date 2026-10-26 --match "Memphis Grizzlies vs Utah Jazz" --odds
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --date 2026-10-26 --match "Chicago Bulls vs Boston Celtics" --odds
```

There is no Pacers–Bulls game tonight. Indiana plays at Milwaukee; Chicago plays at Boston. Both are listed above.

### NBA player props (research only — availability is UNKNOWN)

```bash
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --date 2026-10-26 --match "Phoenix Suns vs Oklahoma City Thunder" --props
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --date 2026-10-26 --match "Phoenix Suns vs Oklahoma City Thunder" --props --player "Shai Gilgeous-Alexander" --player "Devin Booker"
```

Projections use this season's rotation once a player has 3+ games in it, so keep the
boxscore store current. The default look-back is 21 days; a deeper history makes the
prior-season fallback and the holdout meaningful.

```bash
venv/Scripts/python.exe -u ingest_basketball_props.py --days 21                     # routine top-up (free, ESPN)
venv/Scripts/python.exe -u ingest_basketball_props.py --from 2026-02-20 --to 2026-04-12 --cache-hours 720   # history backfill
venv/Scripts/python.exe -u run_basketball_props.py --validate                      # baseline vs candidate, by stat
```

### NFL / NHL / NBL / EuroLeague

```bash
venv/Scripts/python.exe -u msp.py run --sport nfl --league NFL --date 2026-10-26 --match "Philadelphia Eagles vs Dallas Cowboys" --odds
venv/Scripts/python.exe -u msp.py run --sport nhl --league NHL --date 2026-10-26 --match "Detroit Red Wings vs Edmonton Oilers" --odds
venv/Scripts/python.exe -u msp.py run --sport nhl --league NHL --date 2026-10-26 --match "Los Angeles Kings vs New York Rangers" --odds
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBL --date 2026-10-28 --match "Sydney Kings vs Perth Wildcats" --odds
venv/Scripts/python.exe -u msp.py run --sport basketball --league EUROLEAGUE --date 2026-10-27 --match "Bayern Munich vs FC Barcelona" --odds
```

NBL and NZNBL are different competitions and are never merged. Pass `--league NZNBL` for New Zealand games.

### Review, preview, grade, record

```bash
venv/Scripts/python.exe -u msp.py show --latest            # formatted saved review
venv/Scripts/python.exe -u msp.py push --latest --preview  # build Discord payload locally, sends nothing
venv/Scripts/python.exe -u msp.py show --run-id <run_id>   # a specific saved run
venv/Scripts/python.exe -u msp.py pending                  # ungraded picks
venv/Scripts/python.exe -u msp.py grade                    # collect results and grade
venv/Scripts/python.exe -u msp.py record --cohort value    # value ledger
venv/Scripts/python.exe -u msp.py record --cohort high-probability
venv/Scripts/python.exe -u msp.py record --cohort exploratory
venv/Scripts/python.exe -u msp.py cleanup --before 2026-09-26           # dry run of hourly-snapshot pruning
```

Previews are written to `output/workflow/previews/<run_id>.json`. `--preview` never calls a webhook.

### Discord pushes (separate, deliberate step)

Webhook delivery is opt-in and is never part of a research run:

```bash
venv/Scripts/python.exe -u msp.py push --run-id <run_id>
venv/Scripts/python.exe -u msp.py push --latest
```

Omitting `--preview` is the send path: it posts the saved run and prints the confirmed destinations. Check `--preview` output first, and keep the webhook in `.env`.

### Exploratory mode (disclosed substitutions only)

```bash
venv/Scripts/python.exe -u run_basketball.py --league NBL --date 2026-10-28 --match "Sydney Kings vs Perth Wildcats" --exploratory
venv/Scripts/python.exe -u universal_runner.py --sport soccer --league EPL --home Arsenal --away Chelsea --game-date 2026-10-31 --live-odds --exploratory
```

Exploratory output lists every substituted input and is stored in its own grading cohort. It is never written to the value ledger.

### Next verified fixtures — checked against the live feeds (2026-10-27 / 2026-10-28)

Every line below was resolved against the actual feed before being written here. Basketball and
NHL take matches as **away vs home**; the EuroLeague engine has no fixture feed, so it takes
**home vs away**.

```bash
# NHL — 2026-10-27 (priced at FanDuel when --odds is used; verdict is NO BET until goalies are confirmed)
venv/Scripts/python.exe -u msp.py run --sport nhl --league NHL --date 2026-10-27 --match "Boston Bruins vs Carolina Hurricanes" --odds
venv/Scripts/python.exe -u msp.py run --sport nhl --league NHL --date 2026-10-27 --match "Columbus Blue Jackets vs Philadelphia Flyers" --odds
venv/Scripts/python.exe -u msp.py run --sport nhl --league NHL --date 2026-10-27 --match "Los Angeles Kings vs Chicago Blackhawks" --odds

# NBA — 2026-10-27 (away vs home, verified)
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --date 2026-10-27 --match "Brooklyn Nets vs Boston Celtics" --odds
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --date 2026-10-27 --match "Detroit Pistons vs New York Knicks" --odds
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --date 2026-10-27 --match "Sacramento Kings vs San Antonio Spurs" --odds
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --date 2026-10-27 --match "Portland Trail Blazers vs Los Angeles Lakers" --odds

# NBA props — 2026-10-28 (away vs home; books had not posted props lines at the time of writing)
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --date 2026-10-28 --match "Philadelphia 76ers vs Indiana Pacers" --props

# NBL — 2026-10-28 (away vs home, verified)
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBL --date 2026-10-28 --match "Sydney Kings vs Perth Wildcats" --odds

# EuroLeague — 2026-10-27 (home vs away, verified; standings/stats from euroleague-api)
venv/Scripts/python.exe -u msp.py run --sport basketball --league EUROLEAGUE --date 2026-10-27 --match "Bayern Munich vs FC Barcelona" --no-odds
```

`--no-odds` exists on the props runner and the EuroLeague route only. The NBA/NHL team routes always
price automatically; pass manual `--moneyline`/`--spread`/`--total` values instead if you want to
suppress automatic pricing.

A gated NHL game now prints **one** verdict (`VERDICT: NO BET — starting goalies unconfirmed`) above
one market table, and the same single verdict is what the Discord card carries.

### Tests

```bash
venv/Scripts/python.exe -m pytest -q
```
