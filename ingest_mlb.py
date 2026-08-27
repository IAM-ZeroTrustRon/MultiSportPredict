#!/usr/bin/env python
"""Fetch current-season MLB metrics from pybaseball and write a keyed JSON store."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

OUTPUT_PATH = Path("data/mlb_stats.json")


def _number(row: Any, column: str) -> float | None:
    value = row.get(column)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_and_store_mlb(season: int | None = None, output: Path = OUTPUT_PATH) -> dict[str, Any]:
    """Fetch qualified pitcher/hitter data and atomically write it to ``output``."""
    try:
        from pybaseball import batting_stats, pitching_stats
    except ImportError as exc:
        raise RuntimeError("pybaseball is required: pip install pybaseball") from exc

    season = season or date.today().year
    print(f"[*] Fetching live MLB stats via pybaseball for {season}...")
    pitchers = pitching_stats(season, qual=1)
    batters = batting_stats(season, qual=10)
    if pitchers is None or batters is None or pitchers.empty or batters.empty:
        raise RuntimeError(f"pybaseball returned no MLB data for season {season}")

    data: dict[str, Any] = {
        "season": season,
        "source": "pybaseball",
        "pitchers": {},
        "batters": {},
    }
    for _, row in pitchers.iterrows():
        name = str(row.get("Name", "")).strip()
        metrics = {key: _number(row, source) for key, source in (
            ("era", "ERA"), ("k_per_9", "K/9"), ("k_rate", "K%"),
        )}
        if name and all(value is not None for value in metrics.values()):
            data["pitchers"][name] = metrics

    for _, row in batters.iterrows():
        name = str(row.get("Name", "")).strip()
        metrics = {key: _number(row, source) for key, source in (
            ("woba", "wOBA"), ("iso", "ISO"),
        )}
        if name and all(value is not None for value in metrics.values()):
            data["batters"][name] = metrics

    if not data["pitchers"] or not data["batters"]:
        raise RuntimeError("MLB feed contained no complete pitcher or batter records")
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