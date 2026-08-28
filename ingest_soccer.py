#!/usr/bin/env python
"""Fetch team goals and expected-goals metrics from soccerdata/FBref.

This is the entry point refresh_all.sh calls daily. DEFAULT_LEAGUES below is
the set that runs unattended every day; --leagues lets you run a subset
ad hoc (e.g. just the Netherlands) without touching what the daily job does.
"""

from __future__ import annotations

import argparse
import datetime as _dt
from pathlib import Path
from typing import Any

from ingest_soccer_global import LEAGUES, ingest, merge_output

OUTPUT_PATH = Path("data/soccer_stats.json")
DEFAULT_LEAGUES = [
    "ENG-Premier League", "ESP-La Liga", "GER-Bundesliga", "ITA-Serie A",
    "FRA-Ligue 1", "FRA-Ligue 2", "SCO-Premiership", "AUS-A-League",
    "NED-Eredivisie", "NED-Eerste Divisie",
]


def _current_season() -> str:
    """European-season default: Aug-May, so before July it's still last
    season. e.g. run in Aug 2026 -> '2026-27'; run in Mar 2027 -> '2026-27'."""
    today = _dt.date.today()
    start_year = today.year if today.month >= 7 else today.year - 1
    return f"{start_year}-{str(start_year + 1)[2:]}"


def fetch_and_store_soccer(season: str, leagues: list[str], output: Path = OUTPUT_PATH,
                            debug: bool = False) -> dict[str, Any]:
    print(f"[*] Connecting to FBref via soccerdata for season {season}: {leagues}")
    records = ingest(leagues, season, debug=debug)
    # merge_output() reads what's already in the file and updates it in place,
    # instead of overwriting the whole file -- otherwise every daily run would
    # wipe out any league not in this exact call's list.
    merge_output(records, output)
    print(f"[+] Saved {len(records)} soccer team records to {output}")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", default=None,
                         help="e.g. '2026-27'. Defaults to the current European season.")
    parser.add_argument("--leagues", nargs="+", choices=sorted(set(LEAGUES) | set(DEFAULT_LEAGUES)),
                         default=DEFAULT_LEAGUES,
                         help="Defaults to the full daily set. Pass e.g. "
                              "--leagues NED-Eredivisie NED-Eerste Divisie to run just the Dutch tiers.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    season = args.season or _current_season()
    fetch_and_store_soccer(season, args.leagues, args.output, debug=args.debug)


if __name__ == "__main__":
    main()
