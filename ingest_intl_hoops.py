#!/usr/bin/env python
"""Ingest KBL and NZNBL team efficiency metrics from approved boxscore JSON.

Input is a JSON list of games. Each game must contain home/away team names and
box-score fields: points, fga, fta, orb, and tov for both sides.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable

OUTPUT_PATH = Path("data/basketball_stats.json")
LEAGUES = {"kbl", "nznbl"}


def _possessions(box: Dict[str, Any]) -> float:
    return float(box["fga"]) + 0.44 * float(box["fta"]) - float(box["orb"]) + float(box["tov"])


def ingest(games: Iterable[Dict[str, Any]], league: str) -> Dict[str, Dict[str, Any]]:
    if league.lower() not in LEAGUES:
        raise ValueError(f"Unsupported league '{league}'. Use KBL or NZNBL.")
    totals: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    counts: Dict[str, int] = defaultdict(int)
    for game in games:
        for side, opponent in (("home", "away"), ("away", "home")):
            team = str(game.get(f"{side}_team", "")).strip()
            box = game.get(side)
            opp_box = game.get(opponent)
            if not team or not isinstance(box, dict) or not isinstance(opp_box, dict):
                raise ValueError("Every game needs home/away team and box-score objects")
            required = {"points", "fga", "fta", "orb", "tov"}
            if not required <= box.keys() or not required <= opp_box.keys():
                raise ValueError(f"Missing box-score fields for {team}")
            pace = _possessions(box)
            if pace <= 0:
                raise ValueError(f"Non-positive possession count for {team}")
            totals[team]["pace"] += pace
            totals[team]["ortg"] += 100.0 * float(box["points"]) / pace
            totals[team]["drtg"] += 100.0 * float(opp_box["points"]) / pace
            counts[team] += 1
    if not totals:
        raise ValueError("No box-score games supplied")
    return {
        team: {
            "league": league,
            "pace": round(values["pace"] / counts[team], 3),
            "ortg": round(values["ortg"] / counts[team], 3),
            "drtg": round(values["drtg"] / counts[team], 3),
            "source": "approved_boxscore_json",
        }
        for team, values in totals.items()
    }


def merge_output(records: Dict[str, Dict[str, Any]], output: Path = OUTPUT_PATH) -> None:
    existing = json.loads(output.read_text(encoding="utf-8-sig")) if output.exists() else {}
    existing.update(records)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest KBL/NZNBL box-score metrics.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--league", required=True, choices=sorted(LEAGUES))
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    records = ingest(json.loads(args.input.read_text(encoding="utf-8-sig")), args.league)
    merge_output(records, args.output)
    print(f"Merged {len(records)} {args.league.upper()} team records into {args.output}")


if __name__ == "__main__":
    main()
