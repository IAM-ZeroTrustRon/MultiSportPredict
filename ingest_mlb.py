#!/usr/bin/env python
"""Fetch current-season MLB metrics from official MLB feeds and write a keyed JSON store."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

OUTPUT_PATH = Path("data/mlb_stats.json")


def fetch_and_store_mlb(season: int | None = None, output: Path = OUTPUT_PATH) -> dict[str, Any]:
    """Fetch qualified pitcher/hitter data and atomically write it to ``output``."""
    from mlb_player_source import fetch_metrics
    season = season or date.today().year
    print(f"[*] Fetching official MLB player metrics for {season}...")
    data = fetch_metrics(season)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    print(f"[+] Saved {len(data['pitchers'])} pitchers and {len(data['batters'])} batters to {output}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=date.today().year)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    fetch_and_store_mlb(args.season, args.output)


if __name__ == "__main__":
    main()