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

---

## 2026-08-30 grading run — and what it exposed

24 predictions from 2026-08-26 to 2026-08-29 were graded from verified final scores. Record after: **51 graded of 145 logged.**

```
ACTUAL BETS (STRONG BET + BET)      5-0     100.0%    +4.55u
baseball                           17-12-1   58.6%    +3.45u
soccer                              8-13     38.1%    -5.73u
total (only market graded)         25-25-1   50.0%    -2.27u
```

Five decided bets is not a record. It is five results.

### Nine predictions could not be graded because the fixtures never existed

This is the finding that matters more than the win rate.

**Serie A, 2026-08-29** — the model was run on Atalanta v Fiorentina, Napoli v Lazio, Juventus v Roma, AC Milan v Inter. The actual matchday was Fiorentina 1-3 Frosinone, Monza 2-3 Udinese, Sassuolo 2-1 Torino, Juventus 2-0 Parma, and on the 30th Napoli v Como, Cagliari v Inter, Lazio v Genoa. None of the four predicted pairings were ever scheduled. They were supplied by hand, not read from a schedule feed, and nothing in the pipeline checked them against one.

**KBO, 2026-08-29** — the model was run on Kiwoom v SSG, Doosan v KT, Lotte v KIA, Samsung v Hanwha, NC v LG. The actual card was KT @ Samsung, LG @ Lotte, NC @ Hanwha, SSG @ KIA, Kiwoom @ Doosan. Every team played; not one of the five predicted pairings did. These came from a batch run at 00:32, so a schedule source is producing wrong pairings — worth tracing before the next KBO slate.

A prediction on a fixture that does not exist looks exactly like a real one: it has a confidence score, an edge, and a Discord embed. Nothing downstream can tell the difference. **The fixture list needs the same fail-closed treatment the team data got** — validate every matchup against a schedule feed before predicting, and refuse rather than proceed on a miss.

### Home and away were reversed on three games

NC Dinos v LG Twins and Lotte Giants v KIA Tigers (2026-08-26) and Club Leon v Atlante (2026-08-28) were all logged with the road team as home. The result still grades correctly, but home-field advantage was applied to the wrong side when the number was produced. Same root cause: the matchup was typed rather than read from a feed.

### Duplicates inflate the sample

Club America v Columbus Crew is in the database four times and Toluca v Austin FC twice — one Leagues Cup quarter-final each, logged on both 2026-08-26 and 2026-08-27 because the kickoff crossed UTC midnight. All were graded, so one match now contributes four losses to the record. Dedupe before reading anything into the soccer numbers.

### Fix applied: `--manual` now keys on the date

`cmd_manual()` matched a CSV row to a prediction on the team pair alone. Lotte and KIA appear on the 26th (played), the 27th (rained out) and the 29th (never scheduled) — the old code would have settled all three at the 26th's 16-11. The lookup key is now `(game_date, home, away)`, falling back to a dateless match only when the CSV leaves the date blank. A prediction whose date matches no filled row stays pending instead of borrowing another night's score.

### Do not run the grader through a mounted filesystem

Running `grade_predictions.py --manual` against `multisport_history.db` over a network mount wrote every row and then failed on `conn.commit()` with `disk I/O error`, leaving a hot `multisport_history.db-journal` beside the database. The data was on disk but uncommitted: the next process to open the file would have rolled all of it back, silently. Integrity was verified and the journal cleared by hand.

**Run the grader from Windows, against the local file:**

```
venv/Scripts/python.exe grade_predictions.py --manual pending_results.csv --report
```

If a `.db-journal` or `.db-wal` file is ever sitting next to the database when nothing is running, the last write did not commit. Check `PRAGMA integrity_check` before trusting the contents.

### Still pending from this window

| Game | Why |
|---|---|
| Brewers v Rangers, A's v Orioles, Angels v Phillies (08-29) | in progress or not started at grading time |
| Lotte Giants v KIA Tigers (08-27) | rained out |
| Lumphat SC v Nongrah (08-27) | no reachable source publishes this fixture |
| 4 Serie A + 5 KBO (08-29) | fixtures never existed — these should be deleted, not graded |
