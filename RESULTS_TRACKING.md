# Results Tracking — MultiSportPredict

Closing the loop on predictions pushed to Discord, so you have a real win-rate record.
Added 2026-08-28.

---

## The gap this filled

`multisport_history.db` had **104 predictions logged and 0 graded.** The `predictions` table always had `result_outcome` and `profit_loss` columns, and `core/historical_storage.py` always had `update_prediction_outcome()` — but nothing ever called it. Every forecast went out to Discord and was never scored.

`grade_predictions.py` is the missing caller.

---

## Daily use

After the previous day's games have finished:

```
python grade_predictions.py --auto --report
```

That fetches final scores where a feed is wired up, grades everything it can match, and prints the record.

## The four commands

```
python grade_predictions.py --pending      what still needs a result
python grade_predictions.py --auto         fetch scores and grade
python grade_predictions.py --manual FILE  grade from a filled-in CSV
python grade_predictions.py --report       the win-rate record
```

Useful flags: `--sport soccer`, `--days 30`, `--push-discord`.

## Grading sports with no reachable feed

`--pending` writes `pending_results.csv` — one row per game, with empty `home_score` and `away_score` columns:

```
game_date,sport,home_team,away_team,home_score,away_score
2026-08-27,soccer,Bayern Munich,VfB Stuttgart,,
```

Open it in Excel, type the scores, save, then:

```
python grade_predictions.py --manual pending_results.csv --report
```

This works for every sport regardless of what the network is blocking. MLB is the only sport with automatic fetching today (statsapi.mlb.com); the rest wait on the source-access problem being resolved.

---

## What gets graded, and how

| Market | Pick derived from | Settled against |
|---|---|---|
| `total` | OVER if the model's projected total beat the market line, else UNDER | actual combined score vs the line (exact = push) |
| `moneyline` | HOME if the model gave home better than even odds, else AWAY | who won (a draw is a loss in soccer, an error elsewhere) |
| `btts` | YES above even odds, else NO | whether both teams scored |
| `spread` | **not graded** | — |

**Spread is deliberately left ungraded.** The stored `model_value` doesn't record which side the number belongs to, so grading it would be guesswork. The fix belongs where predictions are *written*, not here — store the side explicitly and spread becomes gradable.

Nothing is graded from a guess. A prediction with no matching final score stays ungraded and keeps appearing in `--pending` until a result arrives.

## Recommendation tiers

The `recommendation` column holds a mix of clean decisions (`BET`, `STRONG BET`, `PASS`) and raw model output (`Over: 44.5% | Under: 55.5%`, `Model Prob: 41.1%`). Only the first kind is a decision to place a bet, so the report separates them:

- **ACTUAL BETS** — `STRONG BET` + `BET`. This is your betting record.
- **NOT BETS** — passes and informational rows, reported separately as model calibration. No money was risked on these, so mixing them into a win rate would flatter or distort it.

Worth cleaning up at the source eventually: a market that writes `Over: 44.5% | Under: 55.5%` into a field meant to hold a decision is losing information the grader could otherwise use.

## Profit and loss

Units assume **-110** pricing (risk 1 to win 0.909) unless the prediction's `raw_json` carries real odds. That's a modelling convention, not a claim about what you were actually priced at — read the unit record as directional, not as a P&L statement. Break-even at -110 is **52.4%**, and the report says so explicitly next to your number.

Under about 30 settled bets, the win rate moves several points on a single result. The report warns when the sample is that thin.

## Schema additions

`grade_predictions.py` adds these to `predictions` on first run (idempotent, safe to re-run):

```
game_date            the day the game was played
league
pick                 OVER / UNDER / HOME / AWAY / YES / NO
actual_home_score
actual_away_score
graded_at
grade_note           source of the result, or why it could not be graded
```

`game_date` is backfilled from `date(timestamp)` for existing rows. That's an assumption — predictions are usually made the day of or the evening before — and it's why a game played the day after its prediction may not match automatically. Rows fixed by a real result overwrite it.

## Posting the record to Discord

```
python grade_predictions.py --report --push-discord
```

Uses `DISCORD_RESULTS_WEBHOOK_URL` if set, falling back to `DISCORD_WEBHOOK_URL`. Posting the record to a **separate** webhook from the picks is worth doing — it keeps the scoreboard out of the pick feed.

## Adding an automatic results source

1. Write `fetch_<sport>_results(start, end)` returning `{(date, home_key, away_key): (home_score, away_score)}`, where the keys come from `normalise_team()`.
2. Register it in the `AUTO_SOURCES` dict.

`fetch_mlb_results()` is the worked example. The matcher also tries the reversed home/away orientation, since those are sometimes logged the opposite way from how a feed reports them.

---

## Honest limits

- **Only MLB grades automatically right now.** Everything else needs the CSV until the blocked-sources problem is fixed.
- **Team-name matching is exact after normalization** (lowercase, punctuation stripped). "Fenerbache" in your database won't match "Fenerbahçe" from a feed. Mismatches are reported as unmatched rather than guessed at.
- **Closing-line value isn't tracked.** Hit rate tells you whether picks won; CLV tells you whether they were *good*. That needs the closing line captured at settlement time, which nothing currently records.
