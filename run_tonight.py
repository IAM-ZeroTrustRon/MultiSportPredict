#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_tonight.py - Run tonight's slate through the model and push to Discord

    python run_tonight.py                 run everything below
    python run_tonight.py --no-discord    run but do not push
    python run_tonight.py --odds          pull live totals from The Odds API
    python run_tonight.py --dry-run       show what would run, touch nothing

TONIGHT'S SLATE (2026-08-28)
    Texas Rangers      @ Milwaukee Brewers
    Boston Red Sox     @ New York Yankees
    Los Angeles Dodgers@ Detroit Tigers
    Club Leon vs Atlante  (Liga MX)

HOME AND AWAY MATTER, so they were taken from the MLB schedule feed rather
than from the order the matchups were written down. Two of the three are the
reverse of how they were listed:
    "Milwaukee Brewers vs Texas Rangers" -> Milwaukee is HOME
    "NY Yankees vs Boston Red Sox"       -> Yankees is HOME
    "LA Dodgers vs Detroit Tigers"       -> DETROIT is home, not the Dodgers
Getting that backwards moves the line by roughly half a run before anything
else is considered.

STARTING PITCHERS are read live out of data/mlb_probables.json, so this script
does not carry a hardcoded ERA that goes stale the moment a starter changes.
If that file is older than today, refresh it first:

    python ingest_all_sports.py --only mlb-probables

ABOUT CLUB LEON vs ATLANTE
    Both clubs come from data/soccer_stats.json, populated by:
        python ingest_soccer_fd.py --countries mexico
    The feed spells them "Club Leon" and "Atlante" -- the names below match it
    exactly, because the lookup is a name match and "Leon" would miss.
    (An earlier note here claimed Atlante plays in Liga de Expansion. The
    football-data feed lists it in Liga MX for 2026/2027, so that was wrong.)
    If either club is missing, the run skips rather than falling back to
    league averages, and prints the command that fixes it.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

PROBABLES = ROOT / "data" / "mlb_probables.json"
TODAY = _dt.date.today().isoformat()

# --------------------------------------------------------------------------
# MARKET LINES
# These are the book's numbers, not the model's. They are placeholders until
# you either edit them or pass --odds to fetch live ones. A total you invented
# will produce an "edge" that is really just the gap between your guess and
# reality, so treat any recommendation below as provisional until these are real.
# --------------------------------------------------------------------------
DEFAULT_MLB_TOTAL = 8.5
DEFAULT_SOCCER_TOTAL = 2.5

SLATE: List[Dict[str, Any]] = [
    {
        "sport": "baseball", "league": "MLB",
        "home": "Milwaukee Brewers", "away": "Texas Rangers",
        "market_total": DEFAULT_MLB_TOTAL,
        "markets": ["nrfi", "strikeouts", "home_runs"],
    },
    {
        "sport": "baseball", "league": "MLB",
        "home": "New York Yankees", "away": "Boston Red Sox",
        "market_total": DEFAULT_MLB_TOTAL,
        "markets": ["nrfi", "strikeouts", "home_runs"],
    },
    {
        "sport": "baseball", "league": "MLB",
        "home": "Detroit Tigers", "away": "Los Angeles Dodgers",
        "market_total": DEFAULT_MLB_TOTAL,
        "markets": ["nrfi", "strikeouts", "home_runs"],
    },
    {
        "sport": "soccer", "league": "Liga MX",
        "home": "Club Leon", "away": "Atlante",
        "market_total": DEFAULT_SOCCER_TOTAL,
        "market_line": 0.0,
    },
]


def log(message: str = "") -> None:
    print(message, flush=True)


def rule(char: str = "=") -> None:
    log(char * 78)


# ==========================================================================
# PROBABLE PITCHERS
# ==========================================================================

def load_probables() -> Dict[str, Dict[str, Any]]:
    """(home, away) -> the scheduled game, for today only."""
    if not PROBABLES.exists():
        log(f"[warn] {PROBABLES.name} not found. Run:  "
            f"python ingest_all_sports.py --only mlb-probables")
        return {}
    payload = json.loads(PROBABLES.read_text(encoding="utf-8-sig"))
    generated = payload.get("generated", "")
    if generated and not str(generated).startswith(TODAY):
        log(f"[warn] {PROBABLES.name} was generated {generated}, not today. "
            f"Starters may be stale -- refresh with: "
            f"python ingest_all_sports.py --only mlb-probables")
    out: Dict[str, Dict[str, Any]] = {}
    for game in payload.get("games", []):
        if game.get("game_date") != TODAY:
            continue
        key = f"{game.get('home_team')}|{game.get('away_team')}"
        out.setdefault(key, game)      # first game of a doubleheader
    return out


def pitcher_args(game: Optional[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    if not game:
        return {"home_sp_era": None, "home_sp_k": None,
                "away_sp_era": None, "away_sp_k": None}
    return {
        "home_sp_era": game.get("home_pitcher_era"),
        "home_sp_k": game.get("home_pitcher_k9"),
        "away_sp_era": game.get("away_pitcher_era"),
        "away_sp_k": game.get("away_pitcher_k9"),
    }


# ==========================================================================
# OPTIONAL: LIVE TOTALS
# ==========================================================================

def fetch_live_totals() -> Dict[str, float]:
    """MLB game totals from The Odds API. Costs quota (~1 credit)."""
    key = os.environ.get("ODDS_API_KEY", "").strip()
    if not key:
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                if line.strip().startswith("ODDS_API_KEY"):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        log("[odds] ODDS_API_KEY not found -- keeping the default totals.")
        return {}

    try:
        import requests
        response = requests.get(
            "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds",
            params={"apiKey": key, "regions": "us", "markets": "totals",
                    "oddsFormat": "american"}, timeout=30)
        remaining = response.headers.get("x-requests-remaining")
        if remaining:
            log(f"[odds] quota remaining: {remaining}")
        if response.status_code != 200:
            log(f"[odds] HTTP {response.status_code} -- keeping defaults.")
            return {}
        totals: Dict[str, float] = {}
        for event in response.json():
            home, away = event.get("home_team"), event.get("away_team")
            for book in event.get("bookmakers", []):
                for market in book.get("markets", []):
                    if market.get("key") != "totals":
                        continue
                    for outcome in market.get("outcomes", []):
                        if outcome.get("point") is not None:
                            totals[f"{home}|{away}"] = float(outcome["point"])
                            break
                    break
                if f"{home}|{away}" in totals:
                    break
        log(f"[odds] fetched totals for {len(totals)} MLB game(s)")
        return totals
    except Exception as exc:  # noqa: BLE001
        log(f"[odds] failed ({type(exc).__name__}) -- keeping defaults.")
        return {}


# ==========================================================================
# RUNNERS
# ==========================================================================

def check_soccer_teams(home: str, away: str, league: str) -> List[str]:
    from team_stats_provider import get_soccer_team_stats
    missing = []
    for team in (home, away):
        if get_soccer_team_stats(team, league) is None:
            missing.append(team)
    return missing


def run_one(game: Dict[str, Any], probables: Dict[str, Dict[str, Any]],
            live_totals: Dict[str, float], push_discord: bool,
            dry_run: bool) -> Dict[str, Any]:
    home, away = game["home"], game["away"]
    sport, league = game["sport"], game["league"]
    outcome: Dict[str, Any] = {"matchup": f"{away} @ {home}", "league": league}

    rule()
    log(f"{league}:  {away}  @  {home}")
    rule("-")

    if sport == "baseball":
        scheduled = probables.get(f"{home}|{away}")
        arguments = pitcher_args(scheduled)
        if scheduled:
            log(f"  Starters   {scheduled.get('away_pitcher') or 'TBD'} "
                f"(ERA {arguments['away_sp_era']}, K/9 {arguments['away_sp_k']})")
            log(f"             {scheduled.get('home_pitcher') or 'TBD'} "
                f"(ERA {arguments['home_sp_era']}, K/9 {arguments['home_sp_k']})")
        else:
            log("  [warn] No scheduled game found in the probables file for this "
                "matchup today. Running without starter data -- the model will "
                "fall back to defaults for the pitchers.")

        total = live_totals.get(f"{home}|{away}", game["market_total"])
        source = "live odds" if f"{home}|{away}" in live_totals else "DEFAULT (edit or use --odds)"
        log(f"  Total      {total}  [{source}]")

        if dry_run:
            outcome["status"] = "dry-run"
            return outcome

        from universal_runner import run_baseball
        result = run_baseball(
            home, away, league=league, markets=game["markets"], market_total=total,
            store_to_db=True, push_discord=push_discord, **arguments,
        )
        outcome["status"] = "ok"
        outcome["result"] = result
        return outcome

    if sport == "soccer":
        missing = check_soccer_teams(home, away, league)
        if missing:
            log(f"  [SKIPPED] No stats for: {', '.join(missing)}")
            log( "  This is not a crash -- the model refuses to run on teams it has")
            log( "  no data for, because the alternative is silently using league")
            log( "  averages and presenting the result as a real prediction.")
            outcome["status"] = "skipped"
            outcome["missing"] = missing
            return outcome

        if dry_run:
            outcome["status"] = "dry-run"
            return outcome

        from universal_runner import run_soccer
        result = run_soccer(
            home, away, league=league,
            market_line=game.get("market_line", 0.0),
            market_total=game["market_total"],
            store_to_db=True, push_discord=push_discord,
        )
        outcome["status"] = "ok"
        outcome["result"] = result
        return outcome

    outcome["status"] = "unsupported"
    return outcome


# ==========================================================================
# MAIN
# ==========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-discord", action="store_true", help="Do not push to Discord.")
    parser.add_argument("--odds", action="store_true",
                        help="Fetch live MLB totals from The Odds API (uses quota).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would run without predicting or pushing.")
    args = parser.parse_args()

    push_discord = not args.no_discord and not args.dry_run
    if push_discord and not os.environ.get("DISCORD_WEBHOOK_URL"):
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                if line.strip().startswith("DISCORD_WEBHOOK_URL"):
                    os.environ["DISCORD_WEBHOOK_URL"] = \
                        line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if push_discord and not os.environ.get("DISCORD_WEBHOOK_URL"):
        log("[warn] DISCORD_WEBHOOK_URL is not set -- predictions will run but not push.\n")

    rule()
    log(f"TONIGHT'S SLATE  -  {TODAY}")
    log(f"Discord push: {'ON' if push_discord else 'OFF'}"
        + ("   (dry run)" if args.dry_run else ""))
    rule()

    probables = load_probables()
    live_totals = fetch_live_totals() if args.odds else {}

    outcomes: List[Dict[str, Any]] = []
    for game in SLATE:
        try:
            outcomes.append(run_one(game, probables, live_totals, push_discord, args.dry_run))
        except Exception as exc:  # noqa: BLE001
            log(f"  [FAILED] {type(exc).__name__}: {exc}")
            if os.environ.get("DEBUG"):
                traceback.print_exc()
            outcomes.append({"matchup": f"{game['away']} @ {game['home']}",
                             "league": game["league"], "status": "failed",
                             "error": f"{type(exc).__name__}: {exc}"})

    log("")
    rule()
    log("SUMMARY")
    rule()
    for outcome in outcomes:
        marker = {"ok": "OK     ", "skipped": "SKIPPED", "failed": "FAILED ",
                  "dry-run": "DRY-RUN", "unsupported": "N/A    "}.get(outcome["status"], "?")
        log(f"  [{marker}] {outcome['league']:<10} {outcome['matchup']}")
        if outcome.get("error"):
            log(f"             {outcome['error']}")
        if outcome.get("missing"):
            log(f"             missing stats: {', '.join(outcome['missing'])}")
    rule()

    skipped = [o for o in outcomes if o["status"] == "skipped"]
    if skipped:
        log("\nTO RUN THE SKIPPED SOCCER MATCH")
        log("Pull the league, then re-run this script:")
        log("    venv/Scripts/python.exe ingest_soccer_fd.py --countries mexico")
        log("")
        log("If a club is still missing after that, check the exact spelling in")
        log("data/soccer_stats.json -- the lookup matches on name, so 'Leon' will")
        log("not find a team the feed calls 'Club Leon'.")

    ran = [o for o in outcomes if o["status"] == "ok"]
    if ran and not args.dry_run:
        log(f"\n{len(ran)} prediction(s) stored to multisport_history.db.")
        log("Grade them tomorrow once the games are final:")
        log("  venv/Scripts/python.exe grade_predictions.py --auto --report")


if __name__ == "__main__":
    main()
