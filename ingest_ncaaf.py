#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ingest_ncaaf.py - NCAAF (college football) results, FBS only

    python ingest_ncaaf.py                       this past Saturday + Sunday
    python ingest_ncaaf.py --dates 2026-09-05 2026-09-06
    python ingest_ncaaf.py --check                fetch and report, write nothing

WHAT IT WRITES
    data/ncaaf_schedule.json   one row per game: id, date, home, away, final
                                scores, status -- same shape ingest_nfl_schedule.py
                                writes to data/nfl_schedule.json.

RESULTS ONLY -- NOT A PREDICTOR
    This ingests finished games so grading has something to settle against.
    It does not build team stats, does not feed a model, and there is no
    NCAAF predictor in this project. Building one is a separate decision.
    grade_predictions.py's AUTO_SOURCES["ncaaf"] used to alias
    fetch_nfl_results -- the NFL endpoint, which returns zero or wrong games
    for NCAAF fixtures. This ingest, plus the matching fetch_ncaaf_results()
    added to grade_predictions.py, replace that placeholder.

WHY FBS ONLY
    Full NCAAF (FBS + FCS + D2 + D3) is several hundred games a weekend, most
    of them for teams this project has no other data on and nobody will ever
    grade a prediction against. ESPN's `groups=80` parameter is FBS only --
    same 130-some teams that show up in any real slate. Scope this
    deliberately; widen it later only if something actually needs FCS.

SOURCE
    site.web.api.espn.com. Note the "web": site.api.espn.com (no "web") is
    Akamai-blocked from this machine and returns 403 -- same note as
    ingest_nfl_schedule.py, same host.

HOME AND AWAY COME FROM THE FEED
    ESPN marks each competitor with an explicit "homeAway" field. Position in
    the array is not reliable -- see ingest_nfl_schedule.py's docstring for
    the incident that made this the rule everywhere in this project.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SCHEDULE_PATH = DATA / "ncaaf_schedule.json"

BASE = ("https://site.web.api.espn.com/apis/site/v2/sports/football/"
        "college-football/scoreboard?dates={date}&groups=80&limit=400")
UA = {"User-Agent": "Mozilla/5.0 (MultiSportPredict NCAAF results ingest)"}

FBS_GROUP = 80  # ESPN's grouping id for FBS. 81 is FCS -- deliberately excluded.


def log(message: str = "") -> None:
    print(message, flush=True)


def rule(char: str = "=") -> None:
    log(char * 78)


# ==========================================================================
# FETCH
# ==========================================================================

def fetch(url: str, timeout: int = 60, attempts: int = 3) -> Dict[str, Any]:
    """Retry a timeout, never a 404. A missing date answers immediately."""
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

def parse_event(event: Dict[str, Any], date: str) -> Optional[Dict[str, Any]]:
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    competition = competitions[0]
    competitors = competition.get("competitors") or []
    if len(competitors) != 2:
        return None

    sides: Dict[str, Dict[str, Any]] = {}
    for competitor in competitors:
        # Explicit field, not array position. See module docstring.
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
            # ESPN uses 99 as the "unranked" sentinel here, not null/absent --
            # every unranked team in the feed still carries curatedRank.current
            # == 99, so treating any present value as "ranked" marked all 130+
            # FBS teams ranked. Only 1-25 is a real AP/CFP-style rank.
            "rank": (lambda r: r if isinstance(r, int) and 1 <= r <= 25 else None)(
                competitor.get("curatedRank", {}).get("current")
                if isinstance(competitor.get("curatedRank"), dict) else None),
        }

    status = ((competition.get("status") or {}).get("type") or {})
    return {
        "game_id": str(event.get("id")),
        "date": date,
        "status": status.get("name", "unknown"),
        "completed": bool(status.get("completed")),
        "home_team": sides["home"]["team"],
        "away_team": sides["away"]["team"],
        "home_abbr": sides["home"]["abbr"],
        "away_abbr": sides["away"]["abbr"],
        "home_score": sides["home"]["score"],
        "away_score": sides["away"]["score"],
        "home_rank": sides["home"]["rank"],
        "away_rank": sides["away"]["rank"],
    }


def collect(dates: List[str]) -> tuple[List[Dict[str, Any]], List[str]]:
    games: List[Dict[str, Any]] = []
    problems: List[str] = []
    for date in dates:
        compact = date.replace("-", "")
        url = BASE.format(date=compact)
        try:
            payload = fetch(url)
        except Exception as exc:                        # noqa: BLE001
            problems.append(f"{date}: {type(exc).__name__}")
            continue
        events = payload.get("events") or []
        if not events:
            for league in payload.get("leagues") or []:
                events = league.get("events") or events
        parsed = [g for g in (parse_event(e, date) for e in events) if g]
        games.extend(parsed)
        done = sum(1 for g in parsed if g["completed"])
        log(f"  {date}  {len(parsed):>3} FBS game(s)   {done:>3} final")
    return games, problems


# ==========================================================================
# WRITE
# ==========================================================================

def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_schedule() -> List[Dict[str, Any]]:
    if not SCHEDULE_PATH.exists():
        return []
    try:
        payload = json.loads(SCHEDULE_PATH.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return []
    return payload.get("games", []) if isinstance(payload, dict) else []


def default_weekend() -> List[str]:
    """Most recent Saturday and Sunday, inclusive of today if today is one."""
    today = _dt.date.today()
    # Monday=0 .. Sunday=6. Walk back to the Saturday on or before today.
    days_since_saturday = (today.weekday() - 5) % 7
    saturday = today - _dt.timedelta(days=days_since_saturday)
    sunday = saturday + _dt.timedelta(days=1)
    return [saturday.isoformat(), sunday.isoformat()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dates", nargs="+", metavar="YYYY-MM-DD",
                        help="Explicit dates to pull. Default: this past Sat + Sun.")
    parser.add_argument("--check", action="store_true",
                        help="Fetch and report, write nothing.")
    args = parser.parse_args()

    dates = args.dates or default_weekend()

    rule()
    log(f"NCAAF RESULTS INGEST (FBS only, groups={FBS_GROUP})  -  {', '.join(dates)}")
    rule()

    games, problems = collect(dates)

    if not games:
        rule()
        log("Nothing was ingested. The existing schedule, if any, is untouched.")
        if problems:
            log("Failed: " + ", ".join(problems))
        rule()
        sys.exit(1)

    games.sort(key=lambda g: (g["date"], g["game_id"]))
    completed = [g for g in games if g["completed"]]
    ranked = [g for g in games if g["home_rank"] or g["away_rank"]]

    log("")
    rule("-")
    log(f"  {len(games)} FBS game(s)   {len(completed)} final   {len(ranked)} involving a ranked team")
    rule("-")

    if args.check:
        log("\n--check: nothing was written.")
        return

    existing = {g["game_id"]: g for g in load_schedule()}
    before = len(existing)
    existing.update({g["game_id"]: g for g in games})   # newer wins
    merged_games = sorted(existing.values(), key=lambda g: (g["date"], g["game_id"]))

    write_atomic(SCHEDULE_PATH, json.dumps({
        "_generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "_source": "site.web.api.espn.com scoreboard, groups=80 (FBS only)",
        "_scope": "FBS only -- FCS/D2/D3 deliberately excluded, see module docstring",
        "games": merged_games,
    }, indent=2, ensure_ascii=False))
    log(f"\nWrote {SCHEDULE_PATH.relative_to(ROOT)}  "
        f"({before} on disk + {len(games)} fetched -> {len(merged_games)} kept)")

    if problems:
        log("\nDates that did not load: " + ", ".join(problems))
        log("The store was built from the ones that did. Re-run to fill gaps.")

    log("\nThis is results only -- there is no NCAAF predictor in this project.")
    log("grade_predictions.py's AUTO_SOURCES['ncaaf'] reads this file as a")
    log("fallback the same way it reads data/nfl_schedule.json for NFL.")


if __name__ == "__main__":
    main()
