#!/usr/bin/env python
"""Fetch team goals and expected-goals metrics from soccerdata/FBref."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from ingest_soccer_global import LEAGUES, ingest

OUTPUT_PATH = Path("data/soccer_stats.json")
DEFAULT_LEAGUES = [
    "ENG-Premier League", "ESP-La Liga", "GER-Bundesliga", "ITA-Serie A",
    "FRA-Ligue 1", "FRA-Ligue 2", "SCO-Premiership", "AUS-A-League",
]


def fetch_and_store_soccer(season: str = "2025", output: Path = OUTPUT_PATH) -> dict[str, Any]:
    print(f"[*] Connecting to FBref via soccerdata for season {season}...")
    records = ingest(DEFAULT_LEAGUES, season)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    print(f"[+] Saved {len(records)} soccer team records to {output}")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", default="2025")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    fetch_and_store_soccer(args.season, args.output)


if __name__ == "__main__":
    main()