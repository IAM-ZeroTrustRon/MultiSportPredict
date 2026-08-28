#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ingest_nfl.py - NFL team metrics from ESPN

DAY 1 OF THE NFL BUILD. Populates data/nfl_stats.json with every team's
scoring, yardage, play-mix and home/road splits.

WHICH ESPN HOST MATTERS -- this cost a round trip to learn:
    site.api.espn.com        -> Akamai "Access Denied" on this machine
    site.web.api.espn.com    -> WORKS  (standings)
    sports.core.api.espn.com -> WORKS  (per-team statistics)
Pro-Football-Reference is blocked too, same Cloudflare wall as FBref. Do not
build against it.

USAGE
    python ingest_nfl.py                    current or most recent season
    python ingest_nfl.py --season 2025      an explicit season
    python ingest_nfl.py --check            fetch and report, write nothing
    python ingest_nfl.py --no-team-stats    standings only, 1 request not 33
    python ingest_nfl.py --debug

THE COLD-START PROBLEM
    On Week 1 there is no current-season data at all, and through Week 4 the
    sample is too small to mean much. So ingest the COMPLETED prior season
    first -- it becomes the prior that early-season predictions lean on:

        python ingest_nfl.py --season 2025

    Records carry `games`, so a consumer can weight current against prior
    rather than treating a 2-game sample as settled fact. Nothing here blends
    them for you; that belongs in the predictor, where the weighting is
    visible instead of baked into the store.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUT = DATA / "nfl_stats.json"
PROBE = DATA / "cache" / "probe"

STANDINGS_URL = ("https://site.web.api.espn.com/apis/v2/sports/football/nfl/standings"
                 "?season={season}")
TEAM_STATS_URL = ("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/"
                  "seasons/{season}/types/2/teams/{team_id}/statistics")

TIMEOUT = 30
POLITE = 0.35          # seconds between per-team requests
TODAY = _dt.date.today()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

try:
    import requests
except ImportError:
    sys.exit("requests is required:  pip install requests")

DEBUG = False


def log(message: str = "") -> None:
    print(message, flush=True)


def debug(message: str) -> None:
    if DEBUG:
        log(f"    [debug] {message}")


def get_json(url: str, save_as: Optional[str] = None) -> Any:
    response = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
    if save_as:
        PROBE.mkdir(parents=True, exist_ok=True)
        (PROBE / f"{save_as}.json").write_text(response.text, encoding="utf-8",
                                               errors="replace")
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code} from {url}")
    return response.json()


def num(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("+", "")
    if text in {"", "-", "--", "N/A"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def rounded(value: Optional[float], places: int = 3) -> Optional[float]:
    return None if value is None else round(value, places)


def safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or not b:
        return None
    return a / b


def parse_record(display: Any) -> Optional[Tuple[int, int, int]]:
    """'6-3' or '8-0-1' -> (wins, losses, ties)."""
    match = re.match(r"^\s*(\d+)-(\d+)(?:-(\d+))?\s*$", str(display or ""))
    if not match:
        return None
    wins, losses = int(match.group(1)), int(match.group(2))
    ties = int(match.group(3) or 0)
    return wins, losses, ties


def record_win_pct(record: Optional[Tuple[int, int, int]]) -> Optional[float]:
    if not record:
        return None
    wins, losses, ties = record
    played = wins + losses + ties
    if played == 0:
        return None
    return round((wins + 0.5 * ties) / played, 3)


# ==========================================================================
# STANDINGS
# ==========================================================================

def walk_entries(node: Any) -> Iterable[Dict[str, Any]]:
    """Standings nest under conference/division children; walk for entries."""
    if isinstance(node, dict):
        if isinstance(node.get("entries"), list):
            for entry in node["entries"]:
                if isinstance(entry, dict) and "team" in entry:
                    yield entry
        for value in node.values():
            yield from walk_entries(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_entries(item)


def parse_standings(payload: Any, season: int) -> Dict[str, Dict[str, Any]]:
    """One record per team: scoring, record, and home/road splits.

    pointsFor / pointsAgainst are SEASON TOTALS in this feed, so they are
    divided by games played. Home and Road arrive only as display strings
    ("6-3"), with value None -- hence parse_record rather than reading .value.
    """
    records: Dict[str, Dict[str, Any]] = {}
    for entry in walk_entries(payload):
        team_block = entry.get("team") or {}
        team = (team_block.get("displayName") or team_block.get("name") or "").strip()
        if not team:
            continue

        stats: Dict[str, Dict[str, Any]] = {}
        for stat in entry.get("stats", []):
            if isinstance(stat, dict) and stat.get("name"):
                stats[str(stat["name"])] = stat

        def value(name: str) -> Optional[float]:
            return num((stats.get(name) or {}).get("value"))

        def display(name: str) -> Optional[str]:
            raw = (stats.get(name) or {}).get("displayValue")
            return None if raw is None else str(raw)

        wins, losses = value("wins"), value("losses")
        ties = value("ties") or 0.0
        games = None
        if wins is not None and losses is not None:
            games = wins + losses + ties

        points_for, points_against = value("pointsFor"), value("pointsAgainst")

        record: Dict[str, Any] = {
            "league": "NFL",
            "season": season,
            "team_id": team_block.get("id"),
            "abbreviation": team_block.get("abbreviation"),
            "source": "espn (site.web.api standings)",
            "updated": TODAY.isoformat(),
        }
        if games:
            record["games"] = int(games)
            record["wins"] = int(wins)
            record["losses"] = int(losses)
            record["ties"] = int(ties)
            record["points_for"] = rounded(safe_div(points_for, games), 2)
            record["points_against"] = rounded(safe_div(points_against, games), 2)
            differential = value("pointDifferential")
            record["point_diff_per_game"] = rounded(safe_div(differential, games), 2)
        record["win_pct"] = rounded(value("winPercent"), 3)
        streak = display("streak")
        if streak:
            record["streak"] = streak

        for label, key in (("home", "Home"), ("away", "Road")):
            parsed = parse_record(display(key))
            if parsed:
                record[f"{label}_record"] = f"{parsed[0]}-{parsed[1]}" + (
                    f"-{parsed[2]}" if parsed[2] else "")
                record[f"{label}_win_pct"] = record_win_pct(parsed)

        records[team] = {k: v for k, v in record.items() if v is not None}
    return records


# ==========================================================================
# PER-TEAM STATISTICS
# ==========================================================================

# (output key, category, ESPN stat name, already per-game?)
TEAM_STAT_FIELDS: List[Tuple[str, str, str, bool]] = [
    ("pass_yards_per_game",  "passing",  "netPassingYardsPerGame", True),
    ("completion_pct",       "passing",  "completionPct",          True),
    ("pass_attempts",        "passing",  "passingAttempts",        False),
    ("total_yards_per_game", "passing",  "netYardsPerGame",        True),
    ("rush_yards_per_game",  "rushing",  "rushingYardsPerGame",    True),
    ("rush_attempts",        "rushing",  "rushingAttempts",        False),
    ("rush_touchdowns",      "rushing",  "rushingTouchdowns",      False),
    ("points_per_game",      "scoring",  "totalPointsPerGame",     True),
    ("touchdowns",           "scoring",  "totalTouchdowns",        False),
    ("passing_touchdowns",   "scoring",  "passingTouchdowns",      False),
    ("sacks",                "defensive", "sacks",                 False),
    ("penalty_yards",        "general",  "totalPenaltyYards",      False),
    ("turnovers_lost",       "general",  "fumblesLost",            False),
]


def parse_team_stats(payload: Any) -> Dict[str, Any]:
    categories = {
        str(category.get("name")): {
            str(stat.get("name")): stat
            for stat in category.get("stats", []) if isinstance(stat, dict)
        }
        for category in (payload.get("splits") or {}).get("categories", [])
        if isinstance(category, dict)
    }
    if not categories:
        return {}

    games = num(((categories.get("general") or {}).get("gamesPlayed") or {}).get("value"))
    out: Dict[str, Any] = {}
    if games:
        out["stat_games"] = int(games)

    for key, category_name, stat_name, is_per_game in TEAM_STAT_FIELDS:
        stat = (categories.get(category_name) or {}).get(stat_name)
        if not stat:
            continue
        value = num(stat.get("value"))
        if value is None:
            continue
        if is_per_game:
            out[key] = rounded(value, 2)
        else:
            # Counting stat -- ESPN sometimes supplies perGameValue, but it is
            # rounded to whole numbers for some fields (passingAttempts shows
            # 32.0 for 545/17 = 32.06), so divide from the total instead.
            per_game = safe_div(value, games)
            if per_game is not None:
                out[f"{key}_per_game"] = rounded(per_game, 2)
            out[key] = rounded(value, 2)

    passes = out.get("pass_attempts_per_game")
    rushes = out.get("rush_attempts_per_game")
    if passes is not None and rushes is not None:
        plays = passes + rushes
        out["plays_per_game"] = rounded(plays, 2)
        if plays:
            out["pass_rate"] = rounded(passes / plays, 3)
    return out


# ==========================================================================
# STORE
# ==========================================================================

def merge_store(records: Dict[str, Dict[str, Any]], path: Path) -> None:
    existing: Dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            backup = path.with_suffix(".corrupt.json")
            path.replace(backup)
            log(f"    [warn] {path.name} was not valid JSON; moved to {backup.name}")
    # Records are keyed "Team (season)" so a prior season and the live season
    # coexist -- the predictor needs both to blend early-season weeks.
    existing.update(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)


def default_season() -> int:
    """NFL seasons are labelled by their starting year and run Sep-Feb."""
    return TODAY.year if TODAY.month >= 8 else TODAY.year - 1


def main() -> None:
    global DEBUG
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--check", action="store_true", help="Write nothing.")
    parser.add_argument("--no-team-stats", action="store_true",
                        help="Standings only (1 request instead of 33).")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    DEBUG = args.debug

    season = args.season or default_season()
    log("=" * 74)
    log(f"NFL ingestion  -  season {season}"
        + ("  (CHECK, nothing written)" if args.check else ""))
    log("=" * 74)

    log(f"\n[standings] season {season}")
    payload = get_json(STANDINGS_URL.format(season=season),
                       save_as=f"nfl_standings_{season}")
    records = parse_standings(payload, season)
    if not records:
        raise SystemExit(
            f"No teams parsed. Raw response saved to "
            f"data/cache/probe/nfl_standings_{season}.json -- the real shape is in there."
        )
    log(f"    {len(records)} team(s)")

    played = [r for r in records.values() if r.get("games")]
    if not played:
        log("    [warn] no games played yet this season -- every record is empty. "
            "Ingest the previous season as a prior:  --season " + str(season - 1))

    if not args.no_team_stats:
        log(f"\n[team statistics] {len(records)} request(s), ~{POLITE}s apart")
        enriched = 0
        for team, record in records.items():
            team_id = record.get("team_id")
            if not team_id:
                continue
            try:
                time.sleep(POLITE)
                stats_payload = get_json(
                    TEAM_STATS_URL.format(season=season, team_id=team_id),
                    save_as=f"nfl_teamstats_{season}_{team_id}" if DEBUG else None)
                extra = parse_team_stats(stats_payload)
                if extra:
                    record.update(extra)
                    enriched += 1
                    debug(f"{team}: {sorted(extra)}")
            except Exception as exc:  # noqa: BLE001
                log(f"    [warn] {team}: {type(exc).__name__}: {exc}")
        log(f"    enriched {enriched}/{len(records)}")

    log("\n" + "-" * 74)
    for team in sorted(records)[:6]:
        row = records[team]
        log(f"  {team:<24} PF {str(row.get('points_for','?')):<6} "
            f"PA {str(row.get('points_against','?')):<6} "
            f"{row.get('home_record','?')}H/{row.get('away_record','?')}A  "
            f"plays {row.get('plays_per_game','?')}")
    log("-" * 74)

    if args.check:
        log("\n(check mode -- nothing written)")
        return

    keyed = {f"{team} ({season})": record for team, record in records.items()}
    merge_store(keyed, OUTPUT)
    log(f"\nWrote {len(keyed)} team-season record(s) to {OUTPUT.relative_to(ROOT)}")
    log(f'Keys are "Team Name ({season})" so a prior season can sit alongside the')
    log("live one -- early-season weeks need both.")


if __name__ == "__main__":
    main()
