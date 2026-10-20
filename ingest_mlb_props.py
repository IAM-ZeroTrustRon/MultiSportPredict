#!/usr/bin/env python
"""Ingest MLB pitcher and hitter metrics from official MLB feeds into JSON."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

OUTPUT_PATH = Path("data/mlb_stats.json")


def ingest(season: int, min_bat_pa: int = 50, min_pitch_ip: float = 10.0) -> Dict[str, Any]:
    from mlb_player_source import fetch_metrics
    return fetch_metrics(season, min_bat_pa, min_pitch_ip)



def write_output(payload: Dict[str, Any], output: Path = OUTPUT_PATH) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest MLB pitcher and hitter metrics from official MLB feeds.")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--min-bat-pa", type=int, default=50)
    parser.add_argument("--min-pitch-ip", type=float, default=10.0)
    args = parser.parse_args()
    payload = ingest(args.season, args.min_bat_pa, args.min_pitch_ip)
    write_output(payload, args.output)
    print(f"Ingested {len(payload['hitters'])} hitters and {len(payload['pitchers'])} pitchers into {args.output}")


if __name__ == "__main__":
    main()
