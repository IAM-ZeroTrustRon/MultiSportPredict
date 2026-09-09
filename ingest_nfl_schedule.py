#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ingest_nfl_schedule.py - NFL schedule, results, and first-half scoring

    python ingest_nfl_schedule.py                     2025 regular season + 2026 so far
    python ingest_nfl_schedule.py --season 2025
    python ingest_nfl_schedule.py --season 2026 --weeks 1 2 3
    python ingest_nfl_schedule.py --check             fetch and report, write nothing

WHAT IT WRITES
    data/nfl_schedule.json   one row per game: id, date, week, season, home, away,
                             final scores, per-quarter linescores, status
    data/nfl_stats.json      merges points_1h_for / points_1h_against into each
                             team, tagged data_tier and source so it is obvious
                             they were derived rather than published

WHY THE SCHEDULE IS NOT OPTIONAL
    Three things in this project need it and none of them work without it:

    1. HALFTIME MARKETS. Nothing publishes NFL first-half scoring averages. They
       come from adding Q1 and Q2 across a season. Multiplying a full-game
       number by a guessed fraction is not the same thing and will be wrong in
       exactly the games where it matters.

    2. FIXTURE VALIDATION. On 2026-08-29 this project produced nine predictions
       for games that were never scheduled, each with a confidence score and a
       Discord embed. `home_away(...)` below answers "does this game exist, and
       who is home" from the feed rather than from what somebody typed.

    3. GRADING. grade_predictions.py cannot settle a bet without a final score.

HOME AND AWAY COME FROM THE FEED
    ESPN marks each competitor with an explicit "homeAway" field. Position in
    the array is NOT reliable. Typed matchups have been logged backwards here
    before -- three KBO games and a Liga MX game -- which grades correctly and
    applies home-field advantage to the wrong club.

SOURCE
    site.web.api.espn.com. Note the "web": site.api.espn.com (no "web") is
    Akamai-blocked from this machine and returns 403. NFL_ENGINE_PLAN.md
    originally listed the blocked spelling.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SCHEDULE_PATH = DATA / "nfl_schedule.json"
STATS_PATH = DATA / "nfl_stats.json"

BASE = ("https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/"
        "scoreboard?dates={season}&seasontype={stype}&week={week}")
UA = {"User-Agent": "Mozilla/5.0 (MultiSportPredict NFL schedule ingest)"}

REGULAR_SEASON = 2
MAX_WEEK = 18


def log(message: str = "") -> None:
    print(message, flush=True)


def rule(char: str = "=") -> None:
    log(char * 78)


# ==========================================================================
# FETCH
# ==========================================================================

def fetch(url: str, timeout: int = 60, attempts: int = 3) -> Dict[str, Any]:
    """Retry a timeout, never a 404. A missing week answers immediately."""
    last: Exception = RuntimeError("no attempt made")
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError:
            raise
        except Exception as exc:                        # noqa: BLE001
            last = exc
            if attempt < attempts:
                time.sleep(2 * attempt)
    raise last


# ==========================================================================
# PARSE
# ==========================================================================

def half_points(linescores: Any) -> Optional[int]:
    """Q1 + Q2. Returns None rather than a partial sum when a quarter is absent.

    A game that has only played one quarter would otherwise report a first-half
    score of whatever Q1 was, which reads as a real number and is not one.
    """
    if not isinstance(linescores, list):
        return None
    by_period: Dict[int, float] = {}
    for entry in linescores:
        if not isinstance(entry, dict):
            continue
        period, value = entry.get("period"), entry.get("value")
        if period is not None and value is not None:
            by_period[int(period)] = float(value)
    if 1 in by_period and 2 in by_period:
        return int(by_period[1] + by_period[2])
    return None


def parse_event(event: Dict[str, Any], season: int, week: int) -> Optional[Dict[str, Any]]:
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    competition = competitions[0]
    competitors = competition.get("competitors") or []
    if len(competitors) != 2:
        return None

    sides: Dict[str, Dict[str, Any]] = {}
    for competitor in competitors:
        # Explicit field, not array position. See the module docstring.
        which = str(competitor.get("homeAway", "")).lower()
        if which not in ("home", "away"):
            return None
        team = competitor.get("team") or {}
        score = competitor.get("score")
        sides[which] = {
            "team": team.get("displayName") or team.get("name"),
            "abbr": team.get("abbreviation"),
            "team_id": str(team.get("id")) if team.get("id") is not None else None,
            "score": int(float(score)) if score not in (None, "") else None,
            "half": half_points(competitor.get("linescores")),
        }

    status = ((competition.get("status") or {}).get("type") or {})
    return {
        "game_id": str(event.get("id")),
        "date": str(event.get("date", ""))[:10],
        "season": season,
        "week": week,
        "status": status.get("name", "unknown"),
        "completed": bool(status.get("completed")),
        "home_team": sides["home"]["team"],
        "away_team": sides["away"]["team"],
        "home_abbr": sides["home"]["abbr"],
        "away_abbr": sides["away"]["abbr"],
        "home_score": sides["home"]["score"],
        "away_score": sides["away"]["score"],
        "home_1h": sides["home"]["half"],
        "away_1h": sides["away"]["half"],
    }


# ==========================================================================
# FIRST-HALF AGGREGATION
# ==========================================================================

def first_half_averages(games: List[Dict[str, Any]], season: int) -> Dict[str, Dict[str, Any]]:
    """Per-team first-half points scored and allowed, from completed games only."""
    scored: Dict[str, List[int]] = defaultdict(list)
    allowed: Dict[str, List[int]] = defaultdict(list)

    for game in games:
        if game["season"] != season or not game["completed"]:
            continue
        if game["home_1h"] is None or game["away_1h"] is None:
            continue
        scored[game["home_team"]].append(game["home_1h"])
        allowed[game["home_team"]].append(game["away_1h"])
        scored[game["away_team"]].append(game["away_1h"])
        allowed[game["away_team"]].append(game["home_1h"])

    out: Dict[str, Dict[str, Any]] = {}
    for team, values in scored.items():
        against = allowed.get(team, [])
        if not values or not against:
            continue
        out[team] = {
            "points_1h_for": round(sum(values) / len(values), 2),
            "points_1h_against": round(sum(against) / len(against), 2),
            "games_1h": len(values),
            "points_1h_source": "derived from ESPN per-quarter linescores (Q1+Q2)",
            "points_1h_tier": 2,
        }
    return out


# ==========================================================================
# LOOKUPS FOR OTHER MODULES
# ==========================================================================

def norm_team(name: str) -> str:
    """Squash a team name for comparison, ignoring a trailing season tag.

    ingest_nfl.py keys the stats store as "Buffalo Bills (2025)" while the
    schedule feed says "Buffalo Bills". Normalising without stripping that
    suffix made every comparison fail: the first-half merge matched zero of 32
    teams and wrote nothing, and the fixture check reported that no scheduled
    game existed between two teams who play twice a year. Neither raised --
    they just quietly found nothing.
    """
    name = re.sub(r"\s*\((?:19|20)\d{2}(?:[-/]\d{2,4})?\)\s*$", "", name or "")
    return "".join(ch for ch in name.lower() if ch.isalnum())


def load_schedule() -> List[Dict[str, Any]]:
    if not SCHEDULE_PATH.exists():
        return []
    try:
        payload = json.loads(SCHEDULE_PATH.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return []
    return payload.get("games", []) if isinstance(payload, dict) else []


def home_away(team_a: str, team_b: str, date: Optional[str] = None
              ) -> Tuple[Optional[str], Optional[str], str]:
    """Return (home, away, note) for a real fixture, or (None, None, why).

    This is the fixture check. Two clubs being real does not make a game real --
    that is precisely how nine predictions were produced for matchups nobody
    had scheduled.
    """
    games = load_schedule()
    if not games:
        return None, None, "no schedule on disk -- run ingest_nfl_schedule.py"

    a, b = norm_team(team_a), norm_team(team_b)
    for game in games:
        if date and game["date"] != date:
            continue
        home, away = norm_team(game["home_team"]), norm_team(game["away_team"])
        if {a, b} == {home, away}:
            return (game["home_team"], game["away_team"],
                    f"{game['date']} week {game['week']}")
    scope = f" on {date}" if date else ""
    return None, None, f"no scheduled game between these two{scope}"


# ==========================================================================
# WRITE
# ==========================================================================

def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def merge_first_half(averages: Dict[str, Dict[str, Any]]) -> int:
    """Add the 1H fields to nfl_stats.json without disturbing anything else."""
    if not STATS_PATH.exists():
        log(f"[warn] {STATS_PATH.name} missing -- 1H averages not merged.")
        return 0
    store = json.loads(STATS_PATH.read_text(encoding="utf-8-sig"))

    by_norm = {norm_team(k): k for k in store if not k.startswith("_")}
    merged = 0
    for team, fields in averages.items():
        key = by_norm.get(norm_team(team))
        if key is None:
            continue
        if isinstance(store.get(key), dict):
            store[key].update(fields)
            merged += 1
    write_atomic(STATS_PATH, json.dumps(store, indent=2, ensure_ascii=False))
    return merged


# ==========================================================================
# MAIN
# ==========================================================================

def collect(season: int, weeks: List[int]) -> Tuple[List[Dict[str, Any]], List[str]]:
    games: List[Dict[str, Any]] = []
    problems: List[str] = []
    for week in weeks:
        url = BASE.format(season=season, stype=REGULAR_SEASON, week=week)
        try:
            payload = fetch(url)
        except Exception as exc:                        # noqa: BLE001
            problems.append(f"{season} wk{week}: {type(exc).__name__}")
            continue
        events = payload.get("events") or []
        if not events:
            for league in payload.get("leagues") or []:
                events = league.get("events") or events
        parsed = [g for g in (parse_event(e, season, week) for e in events) if g]
        games.extend(parsed)
        done = sum(1 for g in parsed if g["completed"])
        halves = sum(1 for g in parsed if g["home_1h"] is not None)
        log(f"  {season} wk{week:<2} {len(parsed):>2} games  "
            f"{done:>2} final  {halves:>2} with 1H splits")
    return games, problems


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--season", type=int, action="append")
    parser.add_argument("--weeks", type=int, nargs="+")
    parser.add_argument("--check", action="store_true",
                        help="Fetch and report, write nothing.")
    args = parser.parse_args()

    seasons = args.season or [2025, 2026]
    weeks = args.weeks or list(range(1, MAX_WEEK + 1))

    rule()
    log(f"NFL SCHEDULE INGEST  -  seasons {', '.join(str(s) for s in seasons)}")
    rule()

    all_games: List[Dict[str, Any]] = []
    problems: List[str] = []
    for season in seasons:
        games, issues = collect(season, weeks)
        all_games.extend(games)
        problems.extend(issues)

    if not all_games:
        rule()
        log("Nothing was ingested. The existing schedule, if any, is untouched.")
        if problems:
            log("Failed: " + ", ".join(problems))
        rule()
        sys.exit(1)

    all_games.sort(key=lambda g: (g["season"], g["week"], g["date"], g["game_id"]))
    completed = [g for g in all_games if g["completed"]]
    with_halves = [g for g in all_games if g["home_1h"] is not None]

    log("")
    rule("-")
    log(f"  {len(all_games)} games   {len(completed)} final   "
        f"{len(with_halves)} with first-half splits")

    # First-half averages need finished games. A season whose schedule is
    # published but unplayed has none, which is normal in September and must
    # not look like a failure -- or crash on max() of an empty sequence.
    played = sorted({g["season"] for g in all_games if g["completed"]})
    averages: Dict[str, Dict[str, Any]] = {}
    if played:
        prior = max(played)
        averages = first_half_averages(all_games, prior)
        log(f"  first-half averages: {len(averages)} teams from {prior}")
        if averages:
            sample = sorted(averages)[0]
            log(f"    e.g. {sample}: {averages[sample]['points_1h_for']} scored / "
                f"{averages[sample]['points_1h_against']} allowed per first half")
    else:
        log("  no completed games in this pull -- first-half averages unchanged")
    rule("-")

    if args.check:
        log("\n--check: nothing was written.")
        return

    existing = {g["game_id"]: g for g in load_schedule()}
    before = len(existing)
    existing.update({g["game_id"]: g for g in all_games})   # newer wins
    merged_games = sorted(existing.values(),
                          key=lambda g: (g["season"], g["week"], g["date"]))
    all_seasons = sorted({g["season"] for g in merged_games})

    write_atomic(SCHEDULE_PATH, json.dumps({
        "_generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "_source": "site.web.api.espn.com scoreboard",
        "_seasons": all_seasons,
        "games": merged_games,
    }, indent=2, ensure_ascii=False))
    log(f"\nWrote {SCHEDULE_PATH}  "
        f"({before} on disk + {len(all_games)} fetched -> {len(merged_games)} kept, "
        f"seasons {', '.join(str(s) for s in all_seasons)})")

    if averages:
        merged = merge_first_half(averages)
        log(f"Merged first-half averages into {merged} team(s) in {STATS_PATH.name}")
        if merged == 0:
            log("[WARN] 0 teams matched. The stats store keys and the schedule "
                "names disagree -- nothing was written.")

    if problems:
        log("\nWeeks that did not load: " + ", ".join(problems))
        log("The store was built from the ones that did. Re-run to fill gaps.")

    log("\nNext:")
    log("    venv/Scripts/python.exe data_guard.py --sport nfl")


if __name__ == "__main__":
    main()
