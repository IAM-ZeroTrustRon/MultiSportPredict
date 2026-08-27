#!/usr/bin/env python
"""Validate and seed EuroLeague team metrics into a JSON store.

Input JSON must be either a team-to-stats object or a list of objects with a
``team`` field. The script intentionally does not scrape a site: callers can
feed data from an approved league source, export, or manual process.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

DEFAULT_OUTPUT = Path("data/euroleague_stats.json")
REQUIRED_FIELDS = ("ortg", "drtg", "pace")


def _load_records(path: Path) -> Dict[str, Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict):
        records = {name: dict(stats) for name, stats in payload.items() if not name.startswith("_")}
    elif isinstance(payload, list):
        records = {}
        for item in payload:
            if not isinstance(item, dict) or not item.get("team"):
                raise ValueError("List input entries must be objects containing a team field")
            records[str(item["team"])] = {key: value for key, value in item.items() if key != "team"}
    else:
        raise ValueError("Input JSON must be an object or list")
    return records


def _validate(records: Mapping[str, Mapping[str, Any]]) -> None:
    for team, stats in records.items():
        if missing := [field for field in REQUIRED_FIELDS if stats.get(field) is None]:
            raise ValueError(f"{team}: missing required fields: {', '.join(missing)}")
        for field in REQUIRED_FIELDS:
            if float(stats[field]) <= 0:
                raise ValueError(f"{team}: {field} must be positive")


def seed(records: Mapping[str, Mapping[str, Any]], output: Path) -> None:
    _validate(records)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": "Seeded EuroLeague metrics. ORtg/DRtg are per 100 possessions; pace is possessions per 40 minutes.",
        "_league_baseline": {
            "pace": 72.0,
            "ortg": 112.0,
            "drtg": 112.0,
            "q1_ratio": 0.245,
            "ht_ratio": 0.495,
        },
        **{team: dict(stats) for team, stats in sorted(records.items())},
    }
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed EuroLeague ORtg, DRtg, pace, and segment metrics.")
    parser.add_argument("--input", required=True, type=Path, help="Approved JSON export containing team metrics")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    records = _load_records(args.input)
    seed(records, args.output)
    print(f"Seeded {len(records)} EuroLeague teams into {args.output}")


if __name__ == "__main__":
    main()
