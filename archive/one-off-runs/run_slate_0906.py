#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_slate_0906.py - today's 5-match slate, no Discord push.

Matches:
  1. Brondby vs Randers        (Superliga)
  2. Arsenal vs Chelsea        (Premier League)
  3. Aryna Sabalenka vs Taylor Townsend   (US Open, Round of 16)
  4. Marta Kostyuk vs Linda Noskova       (US Open, Round of 16)
  5. Cleveland Guardians vs Detroit Tigers (MLB - Guardians are actually
     home for this game, at Progressive Field, even though you listed
     Tigers first)

Run it the same way you run anything else in this repo:
    venv/Scripts/python.exe run_slate_0906.py

No --push-discord anywhere. Everything still goes through --store-to-db
so it lands in multisport_history.db for grading later.

Soccer notes: Brondby and Randers weren't in data/soccer_stats.json, so
they were seeded from the real 2026/27 Superliga table (6 games each,
Brondby 11-7 GF/GA, Randers 5-8 GF/GA) using the same data_tier-2
xG-from-goals convention as the rest of the store. Nothing else needed
seeding.

Baseball notes: pitcher ERA/K9 for the Tigers/Guardians game are pulled
live from data/mlb_probables.json at run time (after refreshing it),
not hardcoded - yesterday's file had different starters than today's
game will, and hardcoding them here would go stale by the time you run
this.
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

PY = sys.executable  # use whatever python you invoke this script with
TODAY = date.today().isoformat()


def run(cmd: list[str]) -> None:
    print("\n$ " + " ".join(cmd))
    subprocess.run(cmd, check=False)


# ---------------------------------------------------------------------------
# 1-2. Soccer (through run_match_safe.py - hard-gates on missing real data)
# ---------------------------------------------------------------------------
run([
    PY, "run_match_safe.py",
    "--sport", "soccer", "--home", "Brondby", "--away", "Randers",
    "--league", "Superliga", "--market-total", "2.5",
    "--store-to-db", "--live-odds",
])

run([
    PY, "run_match_safe.py",
    "--sport", "soccer", "--home", "Arsenal", "--away", "Chelsea",
    "--league", "Premier League", "--market-total", "2.5",
    "--store-to-db", "--live-odds",
])

# ---------------------------------------------------------------------------
# 3-4. Tennis (TennisElo - no seeding needed)
# ---------------------------------------------------------------------------
run([
    PY, "universal_runner.py",
    "--sport", "tennis", "--home", "Aryna Sabalenka", "--away", "Taylor Townsend",
    "--tournament", "US Open", "--round-name", "Round of 16", "--surface", "hard",
    "--store-to-db",
])

run([
    PY, "universal_runner.py",
    "--sport", "tennis", "--home", "Marta Kostyuk", "--away", "Linda Noskova",
    "--tournament", "US Open", "--round-name", "Round of 16", "--surface", "hard",
    "--store-to-db",
])

# ---------------------------------------------------------------------------
# 5. Baseball - refresh probables first, then look up today's starters
# ---------------------------------------------------------------------------
run([PY, "ingest_all_sports.py", "--only", "mlb-probables"])

probables_path = Path("data/mlb_probables.json")
game = None
if probables_path.exists():
    data = json.loads(probables_path.read_text(encoding="utf-8"))
    if data.get("generated") != TODAY:
        print(
            f"\n[WARNING] data/mlb_probables.json is dated {data.get('generated')}, "
            f"not today ({TODAY}). The refresh above may have failed (no internet, "
            "or statsapi.mlb.com unreachable) - starters below could be stale. "
            "Run 'venv/Scripts/python.exe ingest_all_sports.py --only mlb-probables "
            "--debug' by hand to see why before trusting this."
        )
    for g in data.get("games", []):
        teams = {g.get("home_team"), g.get("away_team")}
        if {"Detroit Tigers", "Cleveland Guardians"} <= teams:
            game = g
            break

if game is None:
    print(
        "\n[BLOCKED] Tigers/Guardians game not found in data/mlb_probables.json "
        "after refresh. Check the game is today and re-run "
        "'venv/Scripts/python.exe ingest_all_sports.py --only mlb-probables --debug'."
    )
else:
    home_team = game["home_team"]
    away_team = game["away_team"]
    print(f"\nToday's starters: {home_team} (home) - {game['home_pitcher']} "
          f"(ERA {game['home_pitcher_era']}, K/9 {game['home_pitcher_k9']}) vs "
          f"{away_team} (away) - {game['away_pitcher']} "
          f"(ERA {game['away_pitcher_era']}, K/9 {game['away_pitcher_k9']})")

    run([
        PY, "universal_runner.py",
        "--sport", "baseball", "--home", home_team, "--away", away_team,
        "--league", "MLB",
        "--home-sp-era", str(game["home_pitcher_era"]),
        "--home-sp-k", str(game["home_pitcher_k9"]),
        "--away-sp-era", str(game["away_pitcher_era"]),
        "--away-sp-k", str(game["away_pitcher_k9"]),
        "--markets", "nrfi", "strikeouts",
        "--store-to-db",
    ])

print("\nDone. No Discord pushes were made.")
