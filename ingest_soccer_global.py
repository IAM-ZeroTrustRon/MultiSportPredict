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
    "eredivisie": "NED-Eredivisie",
    "eerste_divisie": "NED-Eerste Divisie",
}

# ---------------------------------------------------------------------------
# soccerdata's FBref wrapper only ships the top-5 European leagues built in
# (see https://soccerdata.readthedocs.io/en/latest/howto/custom-leagues.html
# -- the Eredivisie is literally that page's own worked example). Everything
# else, including both Dutch tiers, has to be registered as a "custom league"
# in SOCCERDATA_DIR/config/league_dict.json before sd.FBref() will recognize
# the key. This registers them automatically and idempotently so a scheduled/
# unattended daily run doesn't need a human to hand-edit that file first.
# ---------------------------------------------------------------------------
DUTCH_LEAGUE_ENTRIES: Dict[str, Dict[str, Any]] = {
    "NED-Eredivisie": {
        "ClubElo": "NED_1",
        "MatchHistory": "N1",
        "SoFIFA": "[Netherlands] Eredivisie",
        "FBref": "Eredivisie",
        "ESPN": "ned.1",
        "FiveThirtyEight": "eredivisie",
        "WhoScored": "Netherlands - Eredivisie",
        "Sofascore": "Eredivisie",
        "season_start": "Aug",
        "season_end": "May",
    },
    "NED-Eerste Divisie": {
        "ClubElo": "NED_2",
        "MatchHistory": "N2",
        "SoFIFA": "[Netherlands] Eerste Divisie",
        "FBref": "Eerste Divisie",
        "ESPN": "ned.2",
        "WhoScored": "Netherlands - Eerste Divisie",
        "Sofascore": "Eerste Divisie",
        "season_start": "Aug",
        "season_end": "May",
    },
}


def _soccerdata_dir() -> Path:
    override = os.environ.get("SOCCERDATA_DIR")
    return Path(override).expanduser() if override else Path.home() / "soccerdata"


def ensure_custom_leagues_registered() -> None:
    """Add the Dutch league entries to soccerdata's league_dict.json if
    they're not already there. Safe to call on every run -- no-ops once
    registered. If the config file is corrupt, warns and leaves it alone
    rather than clobbering whatever else is in it."""
    config_path = _soccerdata_dir() / "config" / "league_dict.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    existing: Dict[str, Any] = {}
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            print(f"[WARNING] {config_path} is not valid JSON -- leaving it untouched. "
                  f"Register the Dutch leagues manually: see "
                  f"https://soccerdata.readthedocs.io/en/latest/howto/custom-leagues.html")
            return

    changed = False
    for key, entry in DUTCH_LEAGUE_ENTRIES.items():
        if key not in existing:
            existing[key] = entry
            changed = True

    if changed:
        tmp = config_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, config_path)
        print(f"[+] Registered Dutch league(s) in {config_path}")


def _numeric(row: Any, *columns: str) -> Optional[float]:
    for column in columns:
        if column in row and row[column] is not None:
            with contextlib.suppress(TypeError, ValueError):
                return float(row[column])
    return None


def ingest(leagues: Iterable[str], season: str, debug: bool = False) -> Dict[str, Dict[str, Any]]:
    try:
        import soccerdata as sd
    except ImportError as exc:
        raise RuntimeError("soccerdata is required: pip install soccerdata") from exc

    selected = [LEAGUES.get(name, name) for name in leagues]

    if any(name.startswith("NED-") for name in selected):
        ensure_custom_leagues_registered()

    try:
        fbref = sd.FBref(leagues=selected, seasons=season)
        standard = fbref.read_team_season_stats()
        shooting = fbref.read_team_season_stats(stat_type="shooting")
    except Exception as exc:
        raise RuntimeError(f"FBref ingestion failed: {exc}") from exc
    if standard is None or standard.empty:
        raise RuntimeError("FBref returned no standard team-season rows")

    if debug:
        print("[DEBUG] standard columns:", list(standard.columns))
        if shooting is not None:
            print("[DEBUG] shooting columns:", list(shooting.columns))

    records: Dict[str, Dict[str, Any]] = {}
    skipped: list[str] = []
    estimated: list[str] = []
    unnormalized: list[str] = []

    for index, row in standard.iterrows():
        team = str(index[-1] if isinstance(index, tuple) else index).strip()
        if not team:
            continue
        league = str(index[0]) if isinstance(index, tuple) else ""
        xg_row = shooting.loc[index] if shooting is not None and index in shooting.index else row

        # FBref's season tables are SEASON TOTALS, not per-match rates -- but
        # every consumer of this data (team_stats_provider.py's template,
        # SoccerPredictor) expects per-match averages. Divide through by
        # matches played (MP) to normalize. If MP can't be found, we still
        # emit a row (better than dropping the team) but flag it loudly so
        # it's not silently mistaken for a real per-match number.
        matches = _numeric(row, "MP")
        goals_for_total = _numeric(row, "GF", "Gls")
        goals_against_total = _numeric(row, "GA")
        xg_for_total = _numeric(xg_row, "xG", "Expected Goals", "xg_for")
        xg_against_total = _numeric(row, "xGA", "Expected Goals Against", "xg_against")
        shots_total = _numeric(xg_row, "Sh", "Shots")
        sot_total = _numeric(xg_row, "SoT", "Shots on Target")

        if goals_for_total is None or goals_against_total is None:
            skipped.append(team)
            continue

        def per_match(total: Optional[float]) -> Optional[float]:
            if total is None:
                return None
            if matches and matches > 0:
                return round(total / matches, 3)
            return round(total, 3)

        if not matches:
            unnormalized.append(team)

        goals_for = per_match(goals_for_total)
        goals_against = per_match(goals_against_total)
        xg_for = per_match(xg_for_total)
        xg_against = per_match(xg_against_total)
        shots = per_match(shots_total)
        sot = per_match(sot_total)

        source = "soccerdata.FBref"
        if xg_for is None or xg_against is None:
            # Expected for lower-tier leagues without Opta/StatsBomb xG
            # coverage on FBref (this is exactly the Eerste Divisie case --
            # it's tagged data_tier=2/"unconfirmed" in ARCHITECTURE.md).
            # Fall back to goals as the xG proxy -- the same convention
            # team_stats_provider.py's own get_soccer_team_stats() already
            # uses when xg_for/xg_against are absent from a stored record.
            xg_for = xg_for if xg_for is not None else goals_for
            xg_against = xg_against if xg_against is not None else goals_against
            source = "estimated_from_goals (no FBref xG for this league/tier)"
            estimated.append(team)

        record: Dict[str, Any] = {
            "league": league,
            "season": season,
            "xg_for": xg_for,
            "xg_against": xg_against,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "source": source,
        }
        if shots is not None:
            record["shots"] = shots
        if sot is not None:
            record["sot"] = sot
        records[team] = record

    if not records:
        raise RuntimeError("FBref rows contained no usable xG/goals fields")
    if skipped:
        print(f"[NOTE] Skipped {len(skipped)} team(s) with no goals data at all: {skipped}")
    if unnormalized:
        print(f"[WARNING] Couldn't find a matches-played (MP) column for: {unnormalized} -- "
              f"their goals/xG values may be SEASON TOTALS, not per-match rates. Re-run with "
              f"--debug to see the raw FBref column names and fix the lookup if they've changed.")
    if estimated:
        print(f"[WARNING] No real FBref xG for {len(estimated)} team(s) -- estimated from goals "
              f"instead: {estimated}")
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
    parser.add_argument("--debug", action="store_true",
                         help="Print raw FBref column names -- use this on the first live run "
                              "for a new league to confirm the column-name guesses in ingest() "
                              "still match FBref's current table layout.")
    args = parser.parse_args()
    records = ingest(args.leagues, args.season, debug=args.debug)
    merge_output(records, args.output)
    print(f"Merged {len(records)} global soccer team records into {args.output}")


if __name__ == "__main__":
    main()
