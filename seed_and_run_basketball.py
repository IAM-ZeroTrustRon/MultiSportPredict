#!/usr/bin/env python3
"""
MultiSportPredict - Comprehensive Basketball Seeder and Runner
1. Ingests and persists Japanese B.League and Australian NBL team ratings.
2. Merges stats directly into data/basketball_stats.json.
3. Automatically executes predictions for:
   - Brisbane Bullets vs Illawarra Hawks (NBL)
   - Kyoto Hannaryz vs Shiga Lakes (B.League)
   - Saga Ballooners vs Hiroshima Dragonflies (B.League)
"""

import os
import sys
import json
import subprocess
from pathlib import Path

DATA_DIR = Path("data")
STATS_FILE = DATA_DIR / "basketball_stats.json"
BLEAGUE_FILE = DATA_DIR / "bleague_stats.json"

# 1. Definitive team metrics (Pace, ORtg, DRtg)
SEED_TEAMS = {
    # Japanese B.League
    "Kyoto Hannaryz": {"league": "B League", "pace": 71.5, "ortg": 107.0, "drtg": 114.8, "pts_for": 76.5, "pts_against": 82.1},
    "Shiga Lakes": {"league": "B League", "pace": 72.8, "ortg": 101.9, "drtg": 116.1, "pts_for": 74.2, "pts_against": 84.5},
    "Saga Ballooners": {"league": "B League", "pace": 69.8, "ortg": 108.6, "drtg": 110.6, "pts_for": 75.8, "pts_against": 77.2},
    "Hiroshima Dragonflies": {"league": "B League", "pace": 70.4, "ortg": 112.8, "drtg": 106.7, "pts_for": 79.4, "pts_against": 75.1},
    "Alvark Tokyo": {"league": "B League", "pace": 69.2, "ortg": 119.2, "drtg": 102.3, "pts_for": 82.5, "pts_against": 70.8},
    "Ryukyu Golden Kings": {"league": "B League", "pace": 70.1, "ortg": 116.8, "drtg": 106.0, "pts_for": 81.9, "pts_against": 74.3},

    # Australian NBL
    "Brisbane Bullets": {"league": "NBL", "pace": 84.0, "ortg": 112.5, "drtg": 115.0, "pts_for": 94.5, "pts_against": 96.6},
    "Illawarra Hawks": {"league": "NBL", "pace": 85.5, "ortg": 116.0, "drtg": 111.5, "pts_for": 99.2, "pts_against": 95.3}
}


def seed_database():
    print("=" * 60)
    print("STEP 1: Seeding B.League and NBL team stats into storage...")
    print("=" * 60)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing basketball_stats.json or initialize
    data = {}
    if STATS_FILE.exists():
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

    # Support both flat dictionary structure and nested "teams" structure
    if "teams" in data and isinstance(data["teams"], dict):
        for team, stats in SEED_TEAMS.items():
            data["teams"][team] = stats
    else:
        for team, stats in SEED_TEAMS.items():
            data[team] = stats

    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[OK] Successfully updated {STATS_FILE}")

    # Also save dedicated data/bleague_stats.json
    bleague_data = {
        "_league": "B League",
        "_league_baseline": {"ortg": 108.5, "drtg": 108.5, "pace": 71.0},
        "teams": {k: v for k, v in SEED_TEAMS.items() if v["league"] == "B League"}
    }
    with open(BLEAGUE_FILE, "w", encoding="utf-8") as f:
        json.dump(bleague_data, f, indent=2)
    print(f"[OK] Successfully created {BLEAGUE_FILE}")


def run_matches():
    print("\n" + "=" * 60)
    print("STEP 2: Executing basketball predictions via euroleague_engine.py...")
    print("=" * 60)

    python_bin = sys.executable
    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)

    matches = [
        {
            "home": "Brisbane Bullets",
            "away": "Illawarra Hawks",
            "league": "NBL",
            "total": "187.5",
            "output": "output/nbl_brisbane_illawarra.json"
        },
        {
            "home": "Kyoto Hannaryz",
            "away": "Shiga Lakes",
            "league": "B League",
            "total": "166.5",
            "output": "output/bleague_kyoto_shiga.json"
        },
        {
            "home": "Saga Ballooners",
            "away": "Hiroshima Dragonflies",
            "league": "B League",
            "total": "166.5",
            "output": "output/bleague_saga_hiroshima.json"
        }
    ]

    for m in matches:
        cmd = [
            python_bin,
            "euroleague_engine.py",
            "--home", m["home"],
            "--away", m["away"],
            "--league", m["league"],
            "--market-total", m["total"],
            "--output-json", m["output"]
        ]
        print(f"\n[RUN] {m['home']} vs {m['away']} ({m['league']})...")
        res = subprocess.run(cmd)
        if res.returncode == 0:
            print(f"[OK] File saved to: {m['output']}")
        else:
            print(f"[FAIL] {m['home']} vs {m['away']}")


if __name__ == "__main__":
    seed_database()
    run_matches()
