# Czech Liga Pro — exact worked runs and Git Bash output

These are the actual successful runs for October 10, 2026. The displayed 20:30 start was interpreted as 8:30 PM in America/New_York, which became 00:30 UTC on October 11. The page did not independently confirm its timezone.

**These forecast commands are historical. Old copied prices expire after five minutes, and a match that has started cannot be rerun as a prematch forecast. To see the original output now, use the saved-report commands in step 5.**

## 1. Open Git Bash and enter the project

Click Windows Start, type Git Bash, and open it. Paste these lines into Git Bash and press Enter:

```bash
cd /c/MultiSportPredict
source venv/Scripts/activate
```

## 2. What I did to collect the actual odds

I opened both supplied MyStake pages in Codex’s in-app browser, confirmed the league and player names, and read the visible match panel. No API token or sportsbook login was needed. The standalone runner’s headless browser attempt did not load the market DOM; the loaded in-app browser did.

The visible match text was captured at **2026-10-11 00:23:56.579 UTC**, saved separately as:

- `C:\MultiSportPredict\data\table_tennis\captured_77161125.txt` — Svacha–Wagner.
- `C:\MultiSportPredict\data\table_tennis\captured_77161801.txt` — Regner–Franek.

The shared capture record is `C:\MultiSportPredict\output\table_tennis\browser\requested_20261010_2030_capture.json`.

To repeat collection yourself for a future match, paste this opening command into Git Bash, then paste that match’s fresh full page text into the Notepad window, press Ctrl+S, and close Notepad:

```bash
notepad.exe 'C:\MultiSportPredict\data\table_tennis\captured_77161125.txt'
```

Use the second file for the second match:

```bash
notepad.exe 'C:\MultiSportPredict\data\table_tennis\captured_77161801.txt'
```

**Notepad receives page text. Git Bash receives commands.** Saving old page text again does not refresh the odds.

Capture audit: the transfer initially produced a four-hour file-time offset. I corrected each file’s timestamp to its actual recorded observation time. I did not disable freshness or kickoff guards. A custom batch command was rejected; both successful runs used the existing standard runner below.

## 3. Exact successful command — Svacha vs Wagner

Paste into Git Bash only with that fixture's fresh saved page and before its confirmed start:

```bash
venv/Scripts/python.exe -u run_table_tennis.py --match "Ondrej Svacha vs Richard Wagner" --mystake-url "https://mystake.com/us/sportsbook/prematch/match/77161125" --mystake-text-file data/table_tennis/captured_77161125.txt --start-utc "2026-10-10T20:30:00-04:00" --best-of 5
```

Actual successful terminal output:

```text
CZECH LIGA PRO | Starting match run...
Browser capture: 4 paired markets
============================================================================
🏓 CZECH LIGA PRO
A: Svacha, Ondrej
B: Wagner, Richard
Start (UTC): 2026-10-11T00:30:00+00:00 | Captured phase: scheduled
============================================================================
📊 MATCH PROJECTION
Svacha, Ondrej: 53.0% to win
Wagner, Richard: 47.0% to win
Expected total points: 77.63 | Games: 4.12
Expected A point margin: +0.63
Method: MARKET-ANCHORED SCORING REFERENCE
⚠️ Market-anchored estimate; independent trained edge unavailable.

🔎 EV REVIEW
Highest calculated EV: Over 74.5 (Match total points), -1.0%. No positive-EV priced selection.
EV is expected return per unit staked. Odds are decimal. Win excludes pushes.

💵 PRICED MARKETS — captured sportsbook odds

💰 Match winner
  Svacha, Ondrej | Odds 1.75 | Win 53.0% | EV -7.3%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00
  Wagner, Richard | Odds 1.97 | Win 47.0% | EV -7.3%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00

🎯 Match total points
  Over 74.5 | Odds 1.74 | Win 56.9% | EV -1.0%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00
  Over 75.5 | Odds 1.82 | Win 54.3% | EV -1.1%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00
  Over 76.5 | Odds 1.90 | Win 51.9% | EV -1.4%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00
  Under 76.5 | Odds 1.80 | Win 48.1% | EV -13.4%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00
  Under 75.5 | Odds 1.89 | Win 45.7% | EV -13.7%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00
  Under 74.5 | Odds 1.98 | Win 43.1% | EV -14.6%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00

🧮 MODEL REFERENCE — unpriced projections; no EV
A = Svacha, Ondrej | B = Wagner, Richard

💰 Match winner
  A wins: 53.0% | B wins: 47.0%

🔢 Match total games
  Over 3.5: 74.9% | Under 3.5: 25.1%
  Over 4.5: 37.4% | Under 4.5: 62.6%

⚖️ Game handicap
  A -1.5: 33.7% | B +1.5: 66.3%
  A +1.5: 71.1% | B -1.5: 28.9%

🎯 Match total points
  Over 65.5: 74.9% | Under 65.5: 25.1%
  Over 69.5: 69.1% | Under 69.5: 30.9%
  Over 73.5: 59.5% | Under 73.5: 40.5%
  Over 77.5: 49.6% | Under 77.5: 50.4%
  Over 81.5: 42.4% | Under 81.5: 57.6%

📏 Point handicap
  A -5.5: 35.3% | B +5.5: 64.7%
  A -2.5: 45.7% | B +2.5: 54.3%
  A +2.5: 60.3% | B -2.5: 39.7%
  A +5.5: 70.1% | B -5.5: 29.9%

🏓 First game winner
  A wins: 51.6% | B wins: 48.4%

🔢 First game total points
  Over 17.5: 66.7% | Under 17.5: 33.3%
  Over 18.5: 51.9% | Under 18.5: 48.1%
  Over 19.5: 35.2% | Under 19.5: 64.8%
  Over 20.5: 17.6% | Under 20.5: 82.4%

📏 First game point handicap
  A -3.5: 25.1% | B +3.5: 74.9%
  A -1.5: 51.6% | B +1.5: 48.4%
  A +1.5: 51.6% | B -1.5: 48.4%
  A +3.5: 77.0% | B -3.5: 23.0%

📚 DATA & OBSERVATIONS
Prior matches: A 0 | B 0 | H2H 0
Rest: A unknown | B unknown
Exact match scores: 3-1: 19.9% | 3-2: 19.3% | 2-3: 18.1% | 1-3: 17.6% | 3-0: 13.7% | 0-3: 11.4%
No captured price: Match total games, Game handicap, Point handicap, First game winner, First game total points, First game point handicap

⚠️ NOTES
Insufficient trained player coverage: this forecasts market-implied scores, not an independent betting edge.
Injury, travel and motivation facts unavailable unless independently supplied; no numerical adjustment assumed.
Excluded ambiguous/unsupported market: Game Handicap
Excluded ambiguous/unsupported market: {!gamenr} game - winner
Excluded ambiguous/unsupported market: {!gamenr} game - point handicap
Excluded ambiguous/unsupported market: {!gamenr} game - total points
Excluded ambiguous/unsupported market: {!gamenr} game - odd/even
DOM capture time is known; upstream sportsbook price age is unverified.
Constant independent point model; serve-specific skill unavailable.
Saved (UTC): 2026-10-11T00:25:32.883491+00:00
Saved output keeps its original prices and captured match state.
Run ID: tt_cb56d0a53f9e47b4bf24df85a4d08f22

Saved report: C:\MultiSportPredict\output\table_tennis\tt_cb56d0a53f9e47b4bf24df85a4d08f22.md
Discord (Git Bash): venv/Scripts/python.exe run_table_tennis.py --push "tt_cb56d0a53f9e47b4bf24df85a4d08f22"
```

## 4. Exact successful command — Regner vs Franek

Paste into Git Bash only with that fixture's fresh saved page and before its confirmed start:

```bash
venv/Scripts/python.exe -u run_table_tennis.py --match "Michal Regner vs Tomas Franek" --mystake-url "https://mystake.com/us/sportsbook/prematch/match/77161801" --mystake-text-file data/table_tennis/captured_77161801.txt --start-utc "2026-10-10T20:30:00-04:00" --best-of 5
```

Actual successful terminal output:

```text
CZECH LIGA PRO | Starting match run...
Browser capture: 4 paired markets
============================================================================
🏓 CZECH LIGA PRO
A: Regner, Michal
B: Franek, Tomas
Start (UTC): 2026-10-11T00:30:00+00:00 | Captured phase: scheduled
============================================================================
📊 MATCH PROJECTION
Regner, Michal: 37.7% to win
Franek, Tomas: 62.3% to win
Expected total points: 77.04 | Games: 4.10
Expected A point margin: -2.65
Method: MARKET-ANCHORED SCORING REFERENCE
⚠️ Market-anchored estimate; independent trained edge unavailable.

🔎 EV REVIEW
Highest calculated EV: Under 78.5 (Match total points), +3.5%. Unvalidated estimate; not a strong-bet designation.
EV is expected return per unit staked. Odds are decimal. Win excludes pushes.

💵 PRICED MARKETS — captured sportsbook odds

💰 Match winner
  Regner, Michal | Odds 2.46 | Win 37.7% | EV -7.2%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00
  Franek, Tomas | Odds 1.49 | Win 62.3% | EV -7.2%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00

🎯 Match total points
  Under 78.5 | Odds 1.92 | Win 53.9% | EV +3.5%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00
  Under 80.5 | Odds 1.80 | Win 57.4% | EV +3.4%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00
  Under 79.5 | Odds 1.85 | Win 55.7% | EV +3.1%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00
  Over 78.5 | Odds 1.79 | Win 46.1% | EV -17.5%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00
  Over 79.5 | Odds 1.85 | Win 44.3% | EV -18.1%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00
  Over 80.5 | Odds 1.91 | Win 42.6% | EV -18.7%
    MyStake | Quote (UTC): 2026-10-11T00:23:56.579000+00:00

🧮 MODEL REFERENCE — unpriced projections; no EV
A = Regner, Michal | B = Franek, Tomas

💰 Match winner
  A wins: 37.7% | B wins: 62.3%

🔢 Match total games
  Over 3.5: 73.7% | Under 3.5: 26.3%
  Over 4.5: 36.2% | Under 4.5: 63.8%

⚖️ Game handicap
  A -1.5: 22.0% | B +1.5: 78.0%
  A +1.5: 58.2% | B -1.5: 41.8%

🎯 Match total points
  Over 65.5: 73.6% | Under 65.5: 26.4%
  Over 69.5: 67.6% | Under 69.5: 32.4%
  Over 73.5: 58.0% | Under 73.5: 42.0%
  Over 77.5: 48.1% | Under 77.5: 51.9%
  Over 81.5: 41.0% | Under 81.5: 59.0%

📏 Point handicap
  A -5.5: 22.2% | B +5.5: 77.8%
  A -2.5: 30.5% | B +2.5: 69.5%
  A +2.5: 44.4% | B -2.5: 55.6%
  A +5.5: 55.4% | B -5.5: 44.6%

🏓 First game winner
  A wins: 43.4% | B wins: 56.6%

🔢 First game total points
  Over 17.5: 66.3% | Under 17.5: 33.7%
  Over 18.5: 51.5% | Under 18.5: 48.5%
  Over 19.5: 34.9% | Under 19.5: 65.1%
  Over 20.5: 17.4% | Under 20.5: 82.6%

📏 First game point handicap
  A -3.5: 19.7% | B +3.5: 80.3%
  A -1.5: 43.4% | B +1.5: 56.6%
  A +1.5: 43.4% | B -1.5: 56.6%
  A +3.5: 71.2% | B -3.5: 28.8%

📚 DATA & OBSERVATIONS
Prior matches: A 0 | B 0 | H2H 0
Rest: A unknown | B unknown
Exact match scores: 1-3: 23.6% | 2-3: 20.5% | 0-3: 18.2% | 3-2: 15.7% | 3-1: 13.9% | 3-0: 8.2%
No captured price: Match total games, Game handicap, Point handicap, First game winner, First game total points, First game point handicap

⚠️ NOTES
Insufficient trained player coverage: this forecasts market-implied scores, not an independent betting edge.
Injury, travel and motivation facts unavailable unless independently supplied; no numerical adjustment assumed.
DOM capture time is known; upstream sportsbook price age is unverified.
Constant independent point model; serve-specific skill unavailable.
Saved (UTC): 2026-10-11T00:25:35.679435+00:00
Saved output keeps its original prices and captured match state.
Run ID: tt_8dd65196d314414fac3990e38188b9b6

Saved report: C:\MultiSportPredict\output\table_tennis\tt_8dd65196d314414fac3990e38188b9b6.md
Discord (Git Bash): venv/Scripts/python.exe run_table_tennis.py --push "tt_8dd65196d314414fac3990e38188b9b6"
```

## 5. Display those original results now

In Git Bash, paste either command and press Enter. These read the saved output; they do not fetch new odds or create a forecast.

```bash
venv/Scripts/python.exe -u run_table_tennis.py --show "tt_cb56d0a53f9e47b4bf24df85a4d08f22"
venv/Scripts/python.exe -u run_table_tennis.py --show "tt_8dd65196d314414fac3990e38188b9b6"
```

The terminal begins with `CZECH LIGA PRO | Loading saved report...` and `SAVED REPORT — original captured prices; no fresh forecast.`, then displays the corresponding full report above.

## 6. Exact Discord commands I ran

Both have already been sent. Use these only when you intentionally want to send/update those same reports again:

```bash
venv/Scripts/python.exe -u run_table_tennis.py --push "tt_cb56d0a53f9e47b4bf24df85a4d08f22"
venv/Scripts/python.exe -u run_table_tennis.py --push "tt_8dd65196d314414fac3990e38188b9b6"
```

Actual delivery status for each run:

```text
CZECH LIGA PRO | Loading saved report...
Webhook post failed [404] ... Unknown Webhook
[PARTIAL] Czech Liga Pro research: 1/2 webhook(s) + bot channel.
Discord deliveries: 2
```

The failed-webhook message above is shortened to omit its address. One working webhook and the bot channel received each report. One other configured webhook returned Unknown Webhook. A later resend may be suppressed as a duplicate; delivery text need not remain identical.

## 7. What was recorded

Both runs exist in `multisport_history.db`, with captured event identities and paired prices. Each run also has a `.json` report and a readable `.md` report in `C:\MultiSportPredict\output\table_tennis`. The browser capture and separate match-text files preserve the source evidence. No actual wager placement or final match result was recorded; these are saved forecasts ready for later grading when verified final game scores are available.

Both runs used **MARKET-ANCHORED SCORING REFERENCE**, with zero stored prior matches for these players and zero H2H matches. The Regner–Franek Under 78.5 calculated EV of +3.5% is an unvalidated model estimate, not an independently trained betting recommendation. The ambiguous Game Handicap and {!gamenr} markets were excluded from priced selections; their generic model references are not bookmaker-priced recommendations.

