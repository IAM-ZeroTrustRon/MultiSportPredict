#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ingest_soccer_espn.py - Soccer team metrics from ESPN (Liga MX and friends)

WHY THIS EXISTS
    The existing soccer pipeline (ingest_soccer.py -> soccerdata -> FBref) is
    dead on this machine: FBref returns HTTP 403 to automated clients, which is
    why data/soccer_stats.json has never been created and why soccer has been
    running entirely off the hand-seeded store. ESPN publishes the same leagues
    through a public JSON API with no key and no bot wall.

WHAT YOU GIVE UP
    ESPN does not publish expected goals. FBref did. So xG here is ESTIMATED
    FROM GOALS and tagged as such -- the same Tier 2 convention
    ingest_soccer_global.py already uses for leagues without xG coverage.
    Every record says so in its `source` field. Do not read these as real xG.

USAGE
    python ingest_soccer_espn.py --leagues liga_mx
    python ingest_soccer_espn.py --leagues liga_mx --fixtures
    python ingest_soccer_espn.py --list
    python ingest_soccer_espn.py --leagues liga_mx --check     # write nothing
    python ingest_soccer_espn.py --leagues liga_mx --debug     # dump structure

SELF-DIAGNOSING
    Every raw ESPN response is saved to data/cache/probe/ before parsing. If
    the parser finds nothing, it says exactly which file to look at instead of
    failing with a shrug. That file is readable by whoever is helping you fix it.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUT = DATA / "soccer_stats.json"
FIXTURES = DATA / "soccer_fixtures.json"
PROBE = DATA / "cache" / "probe"

TIMEOUT = 30
TODAY = _dt.date.today()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

try:
    import requests
except ImportError:
    sys.exit("requests is required:  pip install requests")

# ESPN league slugs. Add a line here and the league is supported.
LEAGUES: Dict[str, Dict[str, str]] = {
    "liga_mx":        {"slug": "mex.1", "name": "Liga MX"},
    "liga_expansion": {"slug": "mex.2", "name": "Liga de Expansion MX"},
    "epl":            {"slug": "eng.1", "name": "Premier League"},
    "la_liga":        {"slug": "esp.1", "name": "La Liga"},
    "bundesliga":     {"slug": "ger.1", "name": "Bundesliga"},
    "serie_a":        {"slug": "ita.1", "name": "Serie A"},
    "ligue_1":        {"slug": "fra.1", "name": "Ligue 1"},
    "eredivisie":     {"slug": "ned.1", "name": "Eredivisie"},
    "eerste_divisie": {"slug": "ned.2", "name": "Eerste Divisie"},
    "mls":            {"slug": "usa.1", "name": "MLS"},
    "champions":      {"slug": "uefa.champions", "name": "UEFA Champions League"},
    "brasileirao":    {"slug": "bra.1", "name": "Brasileirao"},
    "argentina":      {"slug": "arg.1", "name": "Liga Profesional Argentina"},
}

STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/soccer/{slug}/standings"
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard"

DEBUG = False


def log(message: str = "") -> None:
    print(message, flush=True)


def debug(message: str) -> None:
    if DEBUG:
        log(f"    [debug] {message}")


def get_json(url: str, params: Optional[Dict[str, Any]] = None,
             save_as: Optional[str] = None) -> Any:
    response = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=TIMEOUT)
    if save_as:
        PROBE.mkdir(parents=True, exist_ok=True)
        (PROBE / f"{save_as}.json").write_text(response.text, encoding="utf-8",
                                               errors="replace")
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code} from {response.url}")
    return response.json()


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text in {"", "-", "--", "N/A"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


# ==========================================================================
# PARSING
# ==========================================================================

def walk_entries(node: Any) -> Iterable[Dict[str, Any]]:
    """Find every standings entry anywhere in the payload.

    ESPN nests standings differently depending on whether a competition has
    conferences, groups or a single table -- Liga MX has changed shape more
    than once. Walking the tree for anything that looks like an entry is more
    durable than hardcoding a path that works for exactly one league today.
    """
    if isinstance(node, dict):
        if "entries" in node and isinstance(node["entries"], list):
            for entry in node["entries"]:
                if isinstance(entry, dict) and "team" in entry and "stats" in entry:
                    yield entry
        for value in node.values():
            yield from walk_entries(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_entries(item)


def stat_lookup(entry: Dict[str, Any]) -> Dict[str, float]:
    """ESPN stats arrive as a list of {name, value, displayValue, abbreviation}."""
    out: Dict[str, float] = {}
    for stat in entry.get("stats", []):
        if not isinstance(stat, dict):
            continue
        value = to_float(stat.get("value"))
        if value is None:
            value = to_float(stat.get("displayValue"))
        if value is None:
            continue
        for key in ("name", "abbreviation", "shortDisplayName", "type"):
            label = stat.get(key)
            if label:
                out[str(label).strip().lower()] = value
    return out


def pick(stats: Dict[str, float], *names: str) -> Optional[float]:
    for name in names:
        value = stats.get(name.lower())
        if value is not None:
            return value
    return None


def parse_standings(payload: Any, league_name: str, season: Any) -> Dict[str, Dict[str, Any]]:
    records: Dict[str, Dict[str, Any]] = {}
    incomplete: List[str] = []

    for entry in walk_entries(payload):
        team_block = entry.get("team") or {}
        team = (team_block.get("displayName") or team_block.get("name")
                or team_block.get("shortDisplayName") or "").strip()
        if not team:
            continue

        stats = stat_lookup(entry)
        debug(f"{team}: {sorted(stats)}")

        games = pick(stats, "gamesplayed", "gp", "games")
        # ESPN labels soccer goals as points in the standings feed.
        goals_for = pick(stats, "pointsfor", "goalsfor", "gf", "for")
        goals_against = pick(stats, "pointsagainst", "goalsagainst", "ga", "against")

        if not games or goals_for is None or goals_against is None:
            incomplete.append(team)
            continue

        per_game_for = round(goals_for / games, 3)
        per_game_against = round(goals_against / games, 3)

        record: Dict[str, Any] = {
            "league": league_name,
            "season": season,
            "games": int(games),
            "goals_for": per_game_for,
            "goals_against": per_game_against,
            # ESPN publishes no xG. Goals stand in, tagged so nothing downstream
            # mistakes this for a real expected-goals number.
            "xg_for": per_game_for,
            "xg_against": per_game_against,
            "data_tier": 2,
            "source": "espn (xG estimated from goals -- ESPN publishes no xG)",
            "updated": TODAY.isoformat(),
        }
        for key, names in (("wins", ("wins", "w")), ("draws", ("ties", "d", "draws")),
                           ("losses", ("losses", "l")), ("points", ("points", "pts"))):
            value = pick(stats, *names)
            if value is not None:
                record[key] = int(value)
        records[team] = record

    if incomplete:
        log(f"    [warn] {len(incomplete)} row(s) lacked games/goals and were skipped: "
            f"{', '.join(incomplete[:6])}")
    return records


def parse_fixtures(payload: Any, league_name: str) -> List[Dict[str, Any]]:
    fixtures: List[Dict[str, Any]] = []
    for event in payload.get("events", []) or []:
        competitions = event.get("competitions") or []
        if not competitions:
            continue
        competition = competitions[0]
        entry: Dict[str, Any] = {
            "league": league_name,
            "event_id": event.get("id"),
            "date_utc": event.get("date"),
            "name": event.get("name"),
            "status": (((event.get("status") or {}).get("type")) or {}).get("description"),
        }
        for competitor in competition.get("competitors", []) or []:
            side = competitor.get("homeAway")
            if side not in ("home", "away"):
                continue
            team = competitor.get("team") or {}
            entry[f"{side}_team"] = team.get("displayName") or team.get("name")
            score = to_float(competitor.get("score"))
            if score is not None:
                entry[f"{side}_score"] = score
        if entry.get("home_team") and entry.get("away_team"):
            fixtures.append(entry)
    return fixtures


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
    existing.update(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)


# ==========================================================================
# MAIN
# ==========================================================================

def ingest_league(key: str, check: bool, want_fixtures: bool,
                  season: Optional[int]) -> Tuple[int, int]:
    config = LEAGUES[key]
    slug, name = config["slug"], config["name"]
    log(f"\n[{name}]  espn slug '{slug}'")

    params: Dict[str, Any] = {}
    if season:
        params["season"] = season

    payload = get_json(STANDINGS_URL.format(slug=slug), params or None,
                       save_as=f"espn_standings_{slug}")
    season_used = season or payload.get("season") or TODAY.year
    records = parse_standings(payload, name, season_used)

    if not records:
        raise RuntimeError(
            f"No teams parsed for {name}. The raw response was saved to "
            f"data/cache/probe/espn_standings_{slug}.json -- that file shows "
            f"exactly what ESPN returned, so the parser can be corrected "
            f"against it rather than guessed at again."
        )

    log(f"    {len(records)} team(s) parsed")
    sample = list(records)[:3]
    for team in sample:
        row = records[team]
        log(f"      {team:<28} GF/g {row['goals_for']:<6} GA/g {row['goals_against']:<6} "
            f"({row['games']} games)")

    fixture_count = 0
    if want_fixtures:
        scoreboard = get_json(SCOREBOARD_URL.format(slug=slug),
                              {"dates": TODAY.strftime("%Y%m%d")},
                              save_as=f"espn_scoreboard_{slug}")
        fixtures = parse_fixtures(scoreboard, name)
        fixture_count = len(fixtures)
        log(f"    {fixture_count} fixture(s) today")
        for fixture in fixtures:
            log(f"      {fixture['away_team']} @ {fixture['home_team']}  "
                f"[{fixture.get('status')}]")
        if fixtures and not check:
            existing: List[Dict[str, Any]] = []
            if FIXTURES.exists():
                try:
                    existing = json.loads(FIXTURES.read_text(encoding="utf-8-sig")).get("fixtures", [])
                except (json.JSONDecodeError, AttributeError):
                    existing = []
            seen = {f.get("event_id") for f in fixtures}
            merged = fixtures + [f for f in existing if f.get("event_id") not in seen]
            FIXTURES.parent.mkdir(parents=True, exist_ok=True)
            FIXTURES.write_text(json.dumps(
                {"generated": TODAY.isoformat(), "fixtures": merged}, indent=2,
                ensure_ascii=False) + "\n", encoding="utf-8")

    if check:
        log("    (check mode -- nothing written)")
    else:
        merge_store(records, OUTPUT)
        log(f"    merged into {OUTPUT.relative_to(ROOT)}")

    return len(records), fixture_count


def main() -> None:
    global DEBUG
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--leagues", nargs="+", default=["liga_mx"],
                        help="League keys (see --list). Default: liga_mx")
    parser.add_argument("--all", action="store_true", help="Every league in the table.")
    parser.add_argument("--fixtures", action="store_true", help="Also fetch today's fixtures.")
    parser.add_argument("--season", type=int, default=None, help="Force a season year.")
    parser.add_argument("--check", action="store_true", help="Fetch and report, write nothing.")
    parser.add_argument("--debug", action="store_true", help="Print every stat key found.")
    parser.add_argument("--list", action="store_true", help="List league keys and exit.")
    args = parser.parse_args()
    DEBUG = args.debug

    if args.list:
        log("Available league keys:\n")
        for key, config in LEAGUES.items():
            log(f"  {key:<18} {config['slug']:<18} {config['name']}")
        log("\nAdd more by putting the ESPN slug in the LEAGUES table at the top of this file.")
        return

    selected = list(LEAGUES) if args.all else args.leagues
    unknown = [key for key in selected if key not in LEAGUES]
    if unknown:
        parser.error(f"Unknown league key(s): {', '.join(unknown)}. Try --list")

    log("=" * 74)
    log(f"ESPN soccer ingestion  -  {TODAY}"
        + ("  (CHECK, nothing written)" if args.check else ""))
    log("=" * 74)

    teams_total = fixtures_total = 0
    failures: List[str] = []
    for key in selected:
        try:
            teams, fixtures = ingest_league(key, args.check, args.fixtures, args.season)
            teams_total += teams
            fixtures_total += fixtures
        except Exception as exc:  # noqa: BLE001
            log(f"    [FAILED] {type(exc).__name__}: {exc}")
            failures.append(key)

    log("\n" + "=" * 74)
    log(f"{teams_total} team(s), {fixtures_total} fixture(s) across "
        f"{len(selected) - len(failures)}/{len(selected)} league(s)")
    if failures:
        log(f"Failed: {', '.join(failures)}")
    if teams_total and not args.check:
        log(f"\nWritten to {OUTPUT.relative_to(ROOT)}.")
        log("Reminder: xG in these rows is ESTIMATED FROM GOALS (Tier 2). ESPN")
        log("publishes no expected goals. Every record says so in its source field.")
    log("=" * 74)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
