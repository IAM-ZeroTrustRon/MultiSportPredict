#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
push_two_0910.py - push the two matches from today's slate Ron wants on
Discord: PSV Eindhoven vs Shakhtar Donetsk (soccer, BTTS Yes) and
Colorado Rockies @ New York Yankees (baseball, OVER 8.5).

Loads the already-computed result dicts from output/soccer/*.json and
output/_ron_slate_0910.json -- does NOT recompute the model or call
--store-to-db again, so this won't create duplicate DB rows or burn a
live-odds API call. discord_integration.py's own dedup/supersede logic
(data/discord_push_log.json) still applies as normal.

Run it the same way you run anything else in this repo:
    venv/Scripts/python.exe push_two_0910.py
"""
import json
import sys

sys.path.insert(0, ".")

from discord_integration import push_prediction_to_all

with open("output/soccer/PSV_Eindhoven_vs_Shakhtar_Donetsk.json", encoding="utf-8") as f:
    soccer_result = json.load(f)

with open("output/_ron_slate_0910.json", encoding="utf-8") as f:
    all_results = json.load(f)
baseball_result = all_results["baseball_Colorado Rockies_at_New York Yankees"]

print("Pushing PSV Eindhoven vs Shakhtar Donetsk (soccer, BTTS Yes)...")
n1 = push_prediction_to_all("soccer", soccer_result, dry_run=False)
print(f"  -> pushed to {n1} destination(s)")

print("Pushing Colorado Rockies @ New York Yankees (baseball, OVER 8.5)...")
n2 = push_prediction_to_all("baseball", baseball_result, dry_run=False)
print(f"  -> pushed to {n2} destination(s)")
