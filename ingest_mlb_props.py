#!/usr/bin/env python
"""Ingest MLB pitcher and hitter metrics from pybaseball into JSON."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

OUTPUT_PATH = Path("data/mlb_stats.json")


def _import_pybaseball():
    try:
        from pybaseball import batting_stats, pitching_stats
    except ImportError as exc:
        raise RuntimeError("pybaseball is required: pip install pybaseball") from exc
    return batting_stats, pitching_stats


def _value(row: Any, *names: str) -> Optional[float]:
    for name in names:
        if name in row and row[name] is not None:
            try:
                return float(row[name])
            except (TypeError, ValueError):
                return None
    return None


def ingest(season: int, min_bat_pa: int = 50, min_pitch_ip: float = 10.0) -> Dict[str, Any]:
    batting_stats, pitching_stats = _import_pybaseball()
    hitters = batting_stats(season, qual=min_bat_pa)
    pitchers = pitching_stats(season, qual=min_pitch_ip)
    if hitters is None or pitchers is None or hitters.empty or pitchers.empty:
        raise RuntimeError(f"pybaseball returned no MLB data for season {season}")

    hitter_records = []
    for _, row in hitters.iterrows():
        name = str(row.get("Name", "")).strip()
        if not name:
            continue
        record = {
            "name": name,
            "team": str(row.get("Team", "")).strip(),
            "pa": _value(row, "PA"),
            "tb_per_pa": _value(row, "TB/PA"),
            "iso": _value(row, "ISO"),
            "woba": _value(row, "wOBA"),
            "source": "pybaseball.batting_stats",
        }
        if record["tb_per_pa"] is None:
            hits = _value(row, "H") or 0.0
            doubles = _value(row, "2B") or 0.0
            triples = _value(row, "3B") or 0.0
            home_runs = _value(row, "HR") or 0.0
            pa = record["pa"] or 0.0
            record["tb_per_pa"] = (hits + doubles + 2 * triples + 3 * home_runs) / pa if pa else None
        if record["tb_per_pa"] is not None:
            hitter_records.append(record)

    pitcher_records = []
    for _, row in pitchers.iterrows():
        name = str(row.get("Name", "")).strip()
        if not name:
            continue
        record = {
            "name": name,
            "team": str(row.get("Team", "")).strip(),
            "ip": _value(row, "IP"),
            "k_per_9": _value(row, "K/9"),
            "k_percent": _value(row, "K%"),
            "era": _value(row, "ERA"),
            "whiff_rate": _value(row, "SwStr%", "Whiff%"),
            "source": "pybaseball.pitching_stats",
        }
        if record["k_per_9"] is not None:
            pitcher_records.append(record)

    if not hitter_records or not pitcher_records:
        raise RuntimeError("pybaseball data lacked usable hitter or pitcher records")
    return {"season": season, "source": "pybaseball", "hitters": hitter_records, "pitchers": pitcher_records}


def write_output(payload: Dict[str, Any], output: Path = OUTPUT_PATH) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest MLB pitcher and hitter metrics from pybaseball.")
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
