# MultiSportPredict - Session Status

## WORKING RIGHT NOW
- Soccer: identical-numbers bug FIXED - seeded xG data reaches predictor
- Soccer Discord embed: clean format with Goals, Corners, BTTS, Team Totals
- Baseball/KBO Discord embed: clean format with Moneyline, Total, Run Line, NRFI, K Props
- Git Bash is the terminal (source venv/Scripts/activate)
- universal_runner.py fetches seeded stats directly, raises ValueError if missing
- run_match_safe.py is the safe entry point
- historical_storage.py is the canonical store

## STILL N/A (minor polish)
- Expected corners per team (needs corner data seeded per team)
- Halftime total (extra_markets.py not yet wired)
- Basketball placeholder bug not yet fixed
- EPL/Belgian Pro League odds coverage unconfirmed
- kbo_scraper.py built but bs4 not yet installed

## INSTALL NEEDED
- pip install beautifulsoup4 (for kbo_scraper.py)

## TERMINAL
- Git Bash: source venv/Scripts/activate
- PowerShell: avoid for file patching (string escaping issues)

## KEY FILES
- universal_runner.py, discord_integration.py
- team_stats_provider.py, extra_markets.py
- run_match_safe.py, ARCHITECTURE.md

## RULES
- Never use placeholder stats
- Always seed xg_for/xg_against (not just goals_for/goals_against)
- Seed template: upsert_soccer_team_stats(team, {xg_for, xg_against, shots, sot, goals_for, goals_against})
