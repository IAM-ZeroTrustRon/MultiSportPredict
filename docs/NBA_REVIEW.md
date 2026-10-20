# NBA reviews and provisional period projections

Updated October 20, 2026.

The score-based basketball runner prints named Home/Away selections for moneylines and spreads, and Over/Under selections for totals. Both sides show their original American odds, probability to one decimal place, and signed estimated EV to two decimal places. `prob_a`/`ev_a` still mean Home for side markets and Over for totals internally; the storage/grading contract has not changed. An EV fraction of `0.125` displays as `+12.50%`.

## Full-game markets

The original full-game projections, probabilities, prices, recommendations and grading are unchanged. Holdout RMSE displays with two decimal places. Displayed score totals sum the displayed team scores to avoid an apparent rounding mismatch; calculations and JSON numeric fields retain their original precision.

## First half and first quarter

NBA reviews include two explicitly provisional sections:

- **1H:** each underlying full-game team projection multiplied by `0.495`.
- **1Q:** each underlying full-game team projection multiplied by `0.245`.

Team period scores round to one decimal place first. The period total and home margin derive from those displayed team scores. The model fair home spread is the negative of that margin. A model fair spread is not an offered bookmaker handicap.

These ratios are declared assumptions, not validated NBA period models. No period variance, cover probability, moneyline probability, EV or betting recommendation is manufactured from them. These sections are not stored as additional bets and do not create grading tasks. They are attached as `h1_projection` and `q1_projection` metadata to new NBA forecasts; the other score-based leagues do not inherit NBA ratios.

If the already retrieved, uniquely matched bookmaker event contains paired `h2h_h1`, `spreads_h1`, `totals_h1` or corresponding `_q1` markets, the adapter can retain them as separate period quotes from the selected bookmaker. A period quote does not enable EV without a calibrated period distribution. The existing full-game odds request is unchanged: no extra period-odds API requests are made and period lines are not guaranteed to be available.

## Saved reviews

**Git Bash**, from `/c/MultiSportPredict`:

```bash
venv/Scripts/python.exe -u msp.py run --sport basketball --league NBA --match "New York Knicks vs Philadelphia 76ers" --date 2026-10-20
venv/Scripts/python.exe -u msp.py show --latest
```

Review the existing October 20 Knicks–Sixers run without predicting again:

```bash
venv/Scripts/python.exe -u msp.py show --run-id msp_79dbfb16a433420d9443702d3f247989
```

Inspect its original full-precision saved JSON:

```bash
venv/Scripts/python.exe -u msp.py show --run-id msp_79dbfb16a433420d9443702d3f247989 --json
```

Historical score-run snapshots receive the new formatting and read-only derived NBA period display without changing their saved payload, odds or record. New snapshots also contain a `formatted_review` string alongside their numeric fields. Terminal and Discord use the same label/percentage helpers; no Discord messages are sent during review or testing.

## Verification

The October 20 Knicks–Sixers forecast was recomputed from the real NBA history using its saved full-game odds. Full-game projections, probabilities and EV matched the original exactly. The original workflow snapshot remained byte-for-byte identical to the pre-edit database backup. A six-field Discord preview rendered without sending. The full suite passed 186 tests (14 existing warnings), and the final focused suite passed 40 tests.
