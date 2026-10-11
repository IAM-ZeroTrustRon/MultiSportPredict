#!/usr/bin/env python3
"""
MultiSportPredict - Automated Basketball Match Runner
Runs Science City Jena vs SC Rasta Vechta (German BBL)
and Tasmania JackJumpers vs Melbourne United (Australian NBL).
"""

import sys
import subprocess
from pathlib import Path

# Ensure emoji output works on Windows (cp1252) consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PYTHON_EXE = sys.executable
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MATCHES = [
    {
        "name": "Science City Jena vs SC Rasta Vechta (BBL)",
        "cmd": [
            PYTHON_EXE, "euroleague_engine.py",
            "--home", "Jena",
            "--away", "Vechta",
            "--league", "BBL",
            "--market-total", "171.5",
            "--market-spread", "4.5",
            "--home-ortg", "107.5",
            "--home-drtg", "114.5",
            "--home-pace", "72.8",
            "--away-ortg", "114.2",
            "--away-drtg", "109.5",
            "--away-pace", "74.0",
            "--output-json", "output/bbl_jena_vechta.json"
        ]
    },
    {
        "name": "Tasmania JackJumpers vs Melbourne United (NBL)",
        "cmd": [
            PYTHON_EXE, "euroleague_engine.py",
            "--home", "Tasmania JackJumpers",
            "--away", "Melbourne United",
            "--league", "NBL",
            "--market-total", "174.5",
            "--market-spread", "2.5",
            "--home-ortg", "111.0",
            "--home-drtg", "107.5",
            "--home-pace", "81.5",
            "--away-ortg", "115.5",
            "--away-drtg", "108.0",
            "--away-pace", "83.2",
            "--output-json", "output/nbl_tasmania_melbourne.json"
        ]
    }
]

def main():
    print("=" * 65)
    print("🏀 EXECUTING BASKETBALL PREDICTION PIPELINE")
    print("=" * 65)

    for match in MATCHES:
        print(f"\n▶ Running: {match['name']}...")
        result = subprocess.run(match["cmd"])
        if result.returncode == 0:
            print(f"✔ Completed successfully. Output saved.")
        else:
            print(f"✖ Prediction run failed (exit code {result.returncode}).")

if __name__ == "__main__":
    main()
