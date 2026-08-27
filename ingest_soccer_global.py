#!/usr/bin/env python
"""Ingest global soccer xG team metrics from soccerdata/FBref."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

OUTPUT_PATH = Path("data/soccer_stats.json")
LEAGUES = {
    "bundesliga": "GER-Bundesliga",
    "la_liga": "ESP-La Liga",
    "serie_a": "ITA-Serie A",
    "eliteserien": "NOR-Eliteserien",
    "a_league": "AUS-A-League",
    "scotland_premiership": "SCO-Premiership",
    "meistriliiga": "EST-Meistriliiga",
    "allsvenskan": "SWE-Allsvenskan",
    "ligue_1": "FRA-Ligue 1",
    "ligue_2": "FRA-Ligue 2",
    "china_super_league": "CHN-Super League",
}


def _numeric(row: Any, *columns: str) -> Optional[float]:
    for column in columns:
        if column in row and row[column] is not None:
            with contextlib.suppress(TypeError, ValueError):
                return float(row[column])
    return None


def ingest(leagues: Iterable[str], season: str) -> Dict[str, Dict[str, Any]]:
    try:
        import soccerdata as sd
    except ImportError as exc:
        raise RuntimeError("soccerdata is required: pip install soccerdata") from exc

    selected = [LEAGUES.get(name, name) for name in leagues]
    try:
        fbref = sd.FBref(leagues=selected, seasons=season)
        standard = fbref.read_team_season_stats()
        shooting = fbref.read_team_season_stats(stat_type="shooting")
    except Exception as exc:
        raise RuntimeError(f"FBref ingestion failed: {exc}") from exc
    if standard is None or standard.empty:
        raise RuntimeError("FBref returned no standard team-season rows")

    records: Dict[str, Dict[str, Any]] = {}
    for index, row in standard.iterrows():
        team = str(index[-1] if isinstance(index, tuple) else index).strip()
        if not team:
            continue
        league = str(index[0]) if isinstance(index, tuple) else ""
        xg_row = shooting.loc[index] if shooting is not None and index in shooting.index else row
        xg_for = _numeric(xg_row, "xG", "Expected Goals", "xg_for")
        xg_against = _numeric(row, "xGA", "Expected Goals Against", "xg_against")
        if xg_for is None or xg_against is None:
            continue
        records[team] = {
            "league": league,
            "season": season,
            "xg_for": xg_for,
            "xg_against": xg_against,
            "goals_for": _numeric(row, "GF", "Gls"),
            "goals_against": _numeric(row, "GA"),
            "source": "soccerdata.FBref",
        }
    if not records:
        raise RuntimeError("FBref rows contained no usable xG fields")
    return records


def merge_output(records: Dict[str, Dict[str, Any]], output: Path = OUTPUT_PATH) -> None:
    existing: Dict[str, Any] = {}
    if output.exists():
        existing = json.loads(output.read_text(encoding="utf-8-sig"))
    existing.update(records)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest global soccer xG from soccerdata/FBref.")
    parser.add_argument("--season", default="2024")
    parser.add_argument("--leagues", nargs="+", choices=sorted(LEAGUES), default=list(LEAGUES))
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    records = ingest(args.leagues, args.season)
    merge_output(records, args.output)
    print(f"Merged {len(records)} global soccer team records into {args.output}")


if __name__ == "__main__":
    main()
