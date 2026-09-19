#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
push_ucl_slate_0908.py - push today's 4 UCL predictions to Discord, once each.

Deliberately does NOT re-run the model. All 4 matches were already run today
(real data, --store-to-db, --live-odds) and are sitting in output/soccer/ as
enriched result JSON - the same shape run_soccer() builds. Re-running would
burn another live-odds call for nothing and write a second, identical row to
multisport_history.db. This script just loads what's already there and pushes
it.

"Push once" is also enforced by discord_integration.py itself: pushes are
keyed by (sport, home, away, today's date, destination) and a second push for
the same game today PATCHes the existing Discord message instead of posting
a new card (see SUPERSEDE_LOG_PATH / _game_key in discord_integration.py).
So running this script twice today is safe - it won't spam duplicates - but
it's still written to only run each match once per invocation.

Run it: venv/Scripts/python.exe push_ucl_slate_0908.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from discord_integration import push_prediction_to_all

MATCHES = [
    "output/soccer/AEK_Athens_vs_LASK.json",
    "output/soccer/Borussia_Dortmund_vs_Villarreal.json",
    "output/soccer/FC_Porto_vs_Manchester_City.json",
    "output/soccer/Club_Brugge_vs_Aston_Villa.json",
]

results = []
for path_str in MATCHES:
    path = Path(path_str)
    if not path.exists():
        print(f"[SKIP] {path} not found - run that match through universal_runner.py first.")
        results.append((path_str, "missing"))
        continue

    data = json.loads(path.read_text(encoding="utf-8"))
    label = f"{data.get('home_team')} vs {data.get('away_team')}"
    print(f"\nPushing: {label}")
    count = push_prediction_to_all("soccer", data, dry_run=False)
    if count > 0:
        print(f"  [OK] sent to {count} destination(s)")
        results.append((label, f"sent to {count}"))
    else:
        print(f"  [REFUSED/FAILED] nothing pushed - see message above")
        results.append((label, "failed"))

print("\n" + "=" * 60)
print("PUSH SUMMARY")
print("=" * 60)
for label, status in results:
    print(f"  {label}: {status}")
