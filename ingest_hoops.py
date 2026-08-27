#!/usr/bin/env python
"""Fetch EuroLeague team efficiencies from the official API wrapper."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

OUTPUT_PATH = Path("data/euroleague_stats.json")


def fetch_and_store_euroleague(season: int = 2025, output: Path = OUTPUT_PATH) -> dict[str, Any]:
    try:
        from euroleague_api.team_stats import TeamStats
    except ImportError as exc:
        raise RuntimeError("euroleague-api is required: pip install euroleague-api") from exc

    print(f"[*] Fetching official EuroLeague team statistics for {season}...")
    frame = TeamStats("E").get_team_stats(season)
    if frame is None or frame.empty:
        raise RuntimeError(f"EuroLeague API returned no data for season {season}")

    records: dict[str, Any] = {}
    for _, row in frame.iterrows():
        name = str(row.get("Team", "")).strip()
        fields = {
            "ortg": row.get("OffensiveRating"),
            "drtg": row.get("DefensiveRating"),
            "pace": row.get("Possessions"),
        }
        if not name or any(value is None for value in fields.values()):
            continue
        try:
            records[name] = {key: float(value) for key, value in fields.items()}
        except (TypeError, ValueError):
            continue
    if not records:
        raise RuntimeError("EuroLeague API returned no complete team metrics")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    print(f"[+] Saved {len(records)} EuroLeague teams to {output}")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    fetch_and_store_euroleague(args.season, args.output)


if __name__ == "__main__":
    main()