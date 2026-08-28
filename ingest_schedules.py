#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ingest_schedules.py - Today's soccer and MLB schedules

Answers "what is on today, and who is starting?" and writes it somewhere the
rest of the pipeline can read.

    python ingest_schedules.py                 today, both sports
    python ingest_schedules.py --days 2        today and tomorrow
    python ingest_schedules.py --sport mlb     just baseball
    python ingest_schedules.py --odds          also pull betting lines
    python ingest_schedules.py --list-leagues  what soccer keys are available

SOURCES
    MLB     statsapi.mlb.com  - official, free, unlimited, includes probable
                               starting pitchers with their season ERA and K/9.
    Soccer  The Odds API      - FBref is Cloudflare-blocked here, so fixtures
                               come from the odds feed instead. Your key is
                               already in .env as ODDS_API_KEY.

ABOUT YOUR ODDS API QUOTA
    Fixtures come from the /events endpoint, which is FREE - it does not count
    against your monthly request allowance. Only --odds costs credits, and it
    costs one credit per league per market. Nine leagues with three markets is
    27 credits, so a daily habit of that is ~810 a month. The script prints
    your remaining balance whenever the API reports it.

OUTPUT
    data/schedule_today.json   full detail, for other scripts
    data/schedule_today.csv    open this one in Excel
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JSON_OUT = DATA / "schedule_today.json"
CSV_OUT = DATA / "schedule_today.csv"

TIMEOUT = 30
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

try:
    import requests
except ImportError:
    sys.exit("requests is required:  pip install requests")

# Load ODDS_API_KEY out of .env without needing python-dotenv installed.
def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env()

# Soccer leagues to check by default. Trimmed to the ones that actually run in
# late August; the full list is available with --list-leagues.
DEFAULT_SOCCER_LEAGUES = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_germany_bundesliga",
    "soccer_italy_serie_a",
    "soccer_france_ligue_one",
    "soccer_netherlands_eredivisie",
    "soccer_uefa_champs_league",
    "soccer_usa_mls",
]

ODDS_BASE = "https://api.the-odds-api.com/v4"
MLB_SCHEDULE = ("https://statsapi.mlb.com/api/v1/schedule"
                "?sportId=1&startDate={start}&endDate={end}"
                "&hydrate=probablePitcher,team,venue")


def log(message: str = "") -> None:
    print(message, flush=True)


def get_json(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    response = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=TIMEOUT)
    remaining = response.headers.get("x-requests-remaining")
    used = response.headers.get("x-requests-used")
    if remaining is not None:
        log(f"    [odds api quota] {remaining} remaining, {used} used this month")
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
    return response.json()


def to_local(iso_timestamp: str) -> str:
    """UTC timestamp from a feed -> readable local time."""
    if not iso_timestamp:
        return ""
    try:
        moment = _dt.datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        return moment.astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_timestamp


# ==========================================================================
# MLB
# ==========================================================================

def fetch_mlb(days: int) -> List[Dict[str, Any]]:
    start = _dt.date.today()
    end = start + _dt.timedelta(days=max(days - 1, 0))
    log(f"[MLB] statsapi.mlb.com  {start} .. {end}")
    payload = get_json(MLB_SCHEDULE.format(start=start.isoformat(), end=end.isoformat()))

    # Season pitcher lines, so a probable arrives with real numbers attached.
    pitchers: Dict[int, Dict[str, Any]] = {}
    try:
        stats = get_json(
            "https://statsapi.mlb.com/api/v1/stats",
            {"stats": "season", "group": "pitching", "season": start.year,
             "sportId": 1, "limit": 2000, "playerPool": "All"},
        )
        for block in stats.get("stats", []):
            for split in block.get("splits", []):
                pid = (split.get("player") or {}).get("id")
                if pid is not None:
                    pitchers[int(pid)] = split.get("stat", {}) or {}
    except Exception as exc:  # noqa: BLE001
        log(f"    [warn] could not attach pitcher ERA/K9: {type(exc).__name__}")

    games: List[Dict[str, Any]] = []
    for day in payload.get("dates", []):
        for game in day.get("games", []):
            teams = game.get("teams", {}) or {}
            entry: Dict[str, Any] = {
                "sport": "mlb",
                "league": "MLB",
                "date": day.get("date"),
                "start_local": to_local(game.get("gameDate", "")),
                "status": (game.get("status") or {}).get("detailedState"),
                "venue": (game.get("venue") or {}).get("name"),
                "game_id": game.get("gamePk"),
            }
            for side in ("home", "away"):
                block = teams.get(side, {}) or {}
                entry[f"{side}_team"] = (block.get("team") or {}).get("name")
                probable = block.get("probablePitcher") or {}
                entry[f"{side}_pitcher"] = probable.get("fullName")
                stat = pitchers.get(int(probable["id"])) if probable.get("id") else None
                if stat:
                    entry[f"{side}_pitcher_era"] = stat.get("era")
                    entry[f"{side}_pitcher_k9"] = stat.get("strikeoutsPer9Inn")
            games.append(entry)

    named = sum(1 for g in games if g.get("home_pitcher") and g.get("away_pitcher"))
    log(f"    {len(games)} game(s), {named} with both starters announced")
    return games


# ==========================================================================
# SOCCER
# ==========================================================================

def list_soccer_leagues(api_key: str) -> None:
    """The /sports endpoint is free and does not count against the quota."""
    data = get_json(f"{ODDS_BASE}/sports", {"apiKey": api_key})
    soccer = [s for s in data if str(s.get("key", "")).startswith("soccer_")]
    log(f"\n{len(soccer)} soccer league(s) currently listed as in season:\n")
    for sport in sorted(soccer, key=lambda s: s["key"]):
        active = "in season" if sport.get("active") else "off season"
        log(f"  {sport['key']:<42} {sport.get('title', '')}  ({active})")
    log("\nPass any of these with --leagues.")


def fetch_soccer(api_key: str, leagues: List[str], days: int,
                 with_odds: bool) -> List[Dict[str, Any]]:
    cutoff = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=days)
    fixtures: List[Dict[str, Any]] = []

    for league in leagues:
        try:
            if with_odds:
                # Costs quota: 1 credit per market per region.
                payload = get_json(f"{ODDS_BASE}/sports/{league}/odds", {
                    "apiKey": api_key, "regions": "us",
                    "markets": "h2h,totals", "oddsFormat": "american",
                })
            else:
                # Free endpoint -- fixtures only, no quota consumed.
                payload = get_json(f"{ODDS_BASE}/sports/{league}/events",
                                   {"apiKey": api_key})
        except Exception as exc:  # noqa: BLE001
            log(f"  [{league}] failed: {exc}")
            continue

        count = 0
        for event in payload:
            commence = event.get("commence_time", "")
            try:
                kickoff = _dt.datetime.fromisoformat(commence.replace("Z", "+00:00"))
            except ValueError:
                continue
            if kickoff > cutoff:
                continue

            entry: Dict[str, Any] = {
                "sport": "soccer",
                "league": league.replace("soccer_", "").replace("_", " ").title(),
                "league_key": league,
                "date": kickoff.astimezone().strftime("%Y-%m-%d"),
                "start_local": to_local(commence),
                "home_team": event.get("home_team"),
                "away_team": event.get("away_team"),
                "game_id": event.get("id"),
            }

            if with_odds:
                entry.update(_best_lines(event))
            fixtures.append(entry)
            count += 1
        log(f"  [{league:<32}] {count} fixture(s) in the next {days} day(s)")

    return fixtures


def _best_lines(event: Dict[str, Any]) -> Dict[str, Any]:
    """Pull a representative moneyline and total out of the bookmaker list."""
    out: Dict[str, Any] = {}
    for bookmaker in event.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            key = market.get("key")
            if key == "h2h" and "home_ml" not in out:
                for outcome in market.get("outcomes", []):
                    if outcome.get("name") == event.get("home_team"):
                        out["home_ml"] = outcome.get("price")
                    elif outcome.get("name") == event.get("away_team"):
                        out["away_ml"] = outcome.get("price")
                    else:
                        out["draw_ml"] = outcome.get("price")
                out["odds_book"] = bookmaker.get("title")
            elif key == "totals" and "market_total" not in out:
                for outcome in market.get("outcomes", []):
                    if outcome.get("point") is not None:
                        out["market_total"] = outcome.get("point")
                        break
    return out


# ==========================================================================
# OUTPUT
# ==========================================================================

def write_outputs(rows: List[Dict[str, Any]]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "count": len(rows),
        "games": rows,
    }
    JSON_OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    columns: List[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def print_table(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        log("\nNothing scheduled in that window.")
        return
    log("\n" + "=" * 92)
    log("TODAY'S SCHEDULE")
    log("=" * 92)
    for sport in sorted({r["sport"] for r in rows}):
        subset = [r for r in rows if r["sport"] == sport]
        log(f"\n{sport.upper()}  ({len(subset)} game(s))")
        log(f"  {'start':<17}{'matchup':<48}{'extra'}")
        log("  " + "-" * 88)
        for row in sorted(subset, key=lambda r: r.get("start_local") or ""):
            matchup = f"{row.get('away_team')} @ {row.get('home_team')}"
            if sport == "mlb":
                home = row.get("home_pitcher") or "TBD"
                away = row.get("away_pitcher") or "TBD"
                extra = f"{away} vs {home}"
            else:
                extra = row.get("league", "")
                if row.get("market_total") is not None:
                    extra += f"  | total {row['market_total']}"
            log(f"  {str(row.get('start_local'))[:16]:<17}{matchup[:46]:<48}{extra[:40]}")
    log("\n" + "=" * 92)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch today's soccer and MLB schedules.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sport", choices=["both", "mlb", "soccer"], default="both")
    parser.add_argument("--days", type=int, default=1,
                        help="1 = today only (default), 2 = today and tomorrow.")
    parser.add_argument("--leagues", nargs="+", default=DEFAULT_SOCCER_LEAGUES,
                        help="Odds API soccer keys. See --list-leagues.")
    parser.add_argument("--odds", action="store_true",
                        help="Also fetch betting lines. COSTS QUOTA - see the notes at "
                             "the top of this file.")
    parser.add_argument("--list-leagues", action="store_true",
                        help="List available soccer league keys and exit (free).")
    args = parser.parse_args()

    api_key = os.environ.get("ODDS_API_KEY", "").strip()

    if args.list_leagues:
        if not api_key:
            sys.exit("ODDS_API_KEY is not set in .env")
        list_soccer_leagues(api_key)
        return

    rows: List[Dict[str, Any]] = []

    if args.sport in ("both", "mlb"):
        try:
            rows.extend(fetch_mlb(args.days))
        except Exception as exc:  # noqa: BLE001
            log(f"[MLB] FAILED: {type(exc).__name__}: {exc}")

    if args.sport in ("both", "soccer"):
        if not api_key:
            log("\n[soccer] ODDS_API_KEY is not set in .env -- skipping soccer.")
        else:
            mode = "with odds (uses quota)" if args.odds else "fixtures only (free)"
            log(f"\n[Soccer] The Odds API, {mode}")
            try:
                rows.extend(fetch_soccer(api_key, args.leagues, args.days, args.odds))
            except Exception as exc:  # noqa: BLE001
                log(f"[Soccer] FAILED: {type(exc).__name__}: {exc}")

    print_table(rows)

    if rows:
        write_outputs(rows)
        log(f"\nSaved {len(rows)} game(s) to:")
        log(f"  {JSON_OUT}")
        log(f"  {CSV_OUT}   <- open this one in Excel")
    else:
        log("\nNothing written.")


if __name__ == "__main__":
    main()
