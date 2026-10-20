## MultiSportPredict — Table tennis in Git Bash

Updated October 19, 2026. Use the root project workflow. Do not switch into czech_liga_pro_engine to run daily matches. Full-score collection can be unavailable; missing point scores cannot be inferred from a match winner.

```bash
cd /c/MultiSportPredict
```

## Refresh available table-tennis history

```bash
venv/Scripts/python.exe -u msp.py refresh --sport table-tennis
```

The public browser source currently reports no readable recent-results page. A nonzero exit is a failed refresh, not fresh data. Provider-backed collection is available when BETSAPI_KEY or ODDS_API_IO_KEY is configured; credentials belong in .env, never commands or documents.

## Run and review a match

Edit this fully filled example to a verified upcoming event; --date filters UTC.

```bash
venv/Scripts/python.exe -u msp.py run --sport table-tennis --match "Jan Trefny vs Richard Krejci" --date 2026-10-19
```

## Copied-page fallback

Open the existing configuration and fresh page-text files. Replace the old matchup, URL and start time with the actual event, and save newly copied page text. This fallback needs manual source capture; the command itself asks no questions.

```bash
notepad.exe data/table_tennis/current_match_config.json
```

```bash
notepad.exe data/table_tennis/current_match.txt
```

```bash
venv/Scripts/python.exe -u msp.py run --sport table-tennis --config data/table_tennis/current_match_config.json
```

The parser requires confirmed participants, competition, a timezone-aware upcoming start, best-of-five format and fresh paired prices. It refuses stale text and ambiguous markets.

## Review and optionally deliver

```bash
venv/Scripts/python.exe -u msp.py show --latest
```

The latest successful workflow run can be from any sport. Confirm the matchup before the next command, which sends to configured Discord destinations.

```bash
venv/Scripts/python.exe -u msp.py push --latest
```

## Grade and inspect outstanding results

```bash
venv/Scripts/python.exe -u msp.py grade --all
```

```bash
venv/Scripts/python.exe -u msp.py pending
```

```bash
venv/Scripts/python.exe -u msp.py record --all-time
```

Hourly grading retries results and sends no Discord messages. Ordinary results, table-tennis research selections, and actual wager records are different records. All 18 unresolved historical table-tennis runs were backed up and removed under the approved cleanup; their event history and backup copies remain available.

## Why some markets need more than a winner

Moneyline needs the confirmed winner and match-completion status. Set markets need every set result. Point spreads and point totals need final points for every set and the original priced line, side and odds. A match winner alone cannot settle a point-total market. Cross-provider matches require verified event/player identity; similar names are insufficient.

## Compatibility

The separate engine directory is retained as legacy code. Its old manual-override commands are not the supported daily workflow. See COMMANDS.md for every sport and mixed slates.
