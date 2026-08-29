#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_mlb.py - Run any MLB matchup through the model and push to Discord

    python run_mlb.py --match "Phillies vs Angels" --match "Giants vs Diamondbacks"
    python run_mlb.py --match "Phillies vs Angels" --total 8.5
    python run_mlb.py --match "Giants vs Diamondbacks" --odds
    python run_mlb.py --no-discord
    python run_mlb.py --dry-run
    python run_mlb.py --list-teams
    python run_mlb.py --today            every game on today's schedule

WHY THIS EXISTS INSTEAD OF ANOTHER HARDCODED SLATE
    run_tonight.py has one specific evening's games baked in. This takes any
    matchup, so it keeps working tomorrow -- and from a phone, where editing a
    file is miserable.

HOME AND AWAY ARE NOT TAKEN FROM WHAT YOU TYPE
    "Phillies vs Angels" does not say who is at home, and getting it backwards
    is worth roughly half a run before anything else is considered. So the
    schedule feed decides: both clubs are looked up in data/mlb_probables.json
    and the real orientation is used, whichever order you typed. If the game
    is not in the feed, the script says so rather than guessing silently.

STARTING PITCHERS come from that same feed with their season ERA and K/9, so
nothing here goes stale the moment a starter is scratched.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import difflib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

PROBABLES = ROOT / "data" / "mlb_probables.json"
STORE = ROOT / "data" / "baseball_stats.json"
TODAY = _dt.date.today().isoformat()

DEFAULT_TOTAL = 8.5          # placeholder; see the note printed after a run
MARKETS = ["nrfi", "strikeouts", "home_runs"]


def log(message: str = "") -> None:
    print(message, flush=True)


def rule(char: str = "=") -> None:
    log(char * 78)


# ==========================================================================
# TEAMS
# ==========================================================================

def load_mlb_teams() -> Dict[str, Dict[str, Any]]:
    if not STORE.exists():
        return {}
    try:
        store = json.loads(STORE.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        log(f"[error] {STORE.name} is not valid JSON.")
        return {}
    return {
        name: record for name, record in store.items()
        if not name.startswith("_") and isinstance(record, dict)
        and str(record.get("league", "")).upper() == "MLB"
    }


def squash(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def resolve(typed: str, teams: Dict[str, Dict[str, Any]]) -> Tuple[Optional[str], str]:
    """Resolve a typed name to a store name, refusing rather than guessing.

    "Angels" -> "Los Angeles Angels". But "Los Angeles" is genuinely ambiguous
    (Angels and Dodgers) and must not be resolved to whichever happens to sort
    first -- a prediction on the wrong club is worse than no prediction.
    """
    if not typed:
        return None, "empty"
    if typed in teams:
        return typed, "exact"

    target = squash(typed)
    squashed = {squash(name): name for name in teams}
    if target in squashed:
        return squashed[target], "case/punctuation"

    contains = [real for flat, real in squashed.items()
                if target and (target in flat or flat in target)]
    if len(contains) == 1:
        return contains[0], "partial"
    if len(contains) > 1:
        return None, f"ambiguous: {', '.join(sorted(contains))}"

    close = difflib.get_close_matches(target, list(squashed), n=3, cutoff=0.72)
    if len(close) == 1:
        return squashed[close[0]], "fuzzy"
    if close:
        return None, f"ambiguous: {', '.join(squashed[c] for c in close)}"
    return None, "no match"


def parse_match(text: str) -> Tuple[str, str]:
    for separator in (" vs. ", " vs ", " VS ", " v ", " @ ", " at ", " - "):
        if separator in text:
            first, second = text.split(separator, 1)
            return first.strip(), second.strip()
    raise ValueError(f'Could not read "{text}". Use the form: "Team vs Team"')


# ==========================================================================
# SCHEDULE
# ==========================================================================

def load_probables() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    if not PROBABLES.exists():
        return [], None
    payload = json.loads(PROBABLES.read_text(encoding="utf-8-sig"))
    games = [g for g in payload.get("games", []) if g.get("game_date") == TODAY]
    return games, payload.get("generated")


def find_game(a: str, b: str, games: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find today's game between two clubs, in whichever orientation it exists."""
    for game in games:
        home, away = game.get("home_team"), game.get("away_team")
        if {home, away} == {a, b}:
            return game
    return None


def pitcher_args(game: Optional[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    if not game:
        return dict(home_sp_era=None, home_sp_k=None, away_sp_era=None, away_sp_k=None)
    return {
        "home_sp_era": game.get("home_pitcher_era"),
        "home_sp_k": game.get("home_pitcher_k9"),
        "away_sp_era": game.get("away_pitcher_era"),
        "away_sp_k": game.get("away_pitcher_k9"),
    }


# ==========================================================================
# LIVE TOTALS (optional, costs Odds API quota)
# ==========================================================================

def fetch_live_totals() -> Dict[str, float]:
    key = os.environ.get("ODDS_API_KEY", "").strip()
    if not key:
        env = ROOT / ".env"
        if env.exists():
            for raw in env.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                if raw.strip().startswith("ODDS_API_KEY"):
                    key = raw.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        log("[odds] ODDS_API_KEY not found -- keeping the default total.")
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
                found = False
                for market in book.get("markets", []):
                    if market.get("key") != "totals":
                        continue
                    for outcome in market.get("outcomes", []):
                        if outcome.get("point") is not None:
                            totals[f"{home}|{away}"] = float(outcome["point"])
                            found = True
                            break
                    break
                if found:
                    break
        log(f"[odds] totals for {len(totals)} game(s)")
        return totals
    except Exception as exc:  # noqa: BLE001
        log(f"[odds] failed ({type(exc).__name__}) -- keeping defaults.")
        return {}




def pair_values(values: Optional[List[Any]], count: int, name: str) -> List[Any]:
    """One value applies to every game; N values pair with N games in order."""
    if not values:
        return [None] * count
    if len(values) == 1:
        return list(values) * count
    if len(values) != count:
        raise SystemExit(
            f"Got {len(values)} --{name} value(s) for {count} game(s). "
            f"Pass one (applies to all) or exactly {count}, in the same order "
            f"as the --match arguments."
        )
    return list(values)


def record_market_odds(home: str, away: str, total: float,
                       home_ml: Optional[int], away_ml: Optional[int]) -> int:
    """Attach the real prices to the rows just written, for honest P/L.

    grade_predictions.py assumes -110 when it finds no odds. That is a fine
    default but it is not what you were actually priced at, so the unit record
    drifts from reality. Writing the real numbers into raw_json lets grading
    settle each bet at the price that was on the board.
    """
    import sqlite3
    database = ROOT / "multisport_history.db"
    if not database.exists():
        return 0
    odds: Dict[str, Any] = {"market_total": total}
    if home_ml is not None:
        odds["home_ml"] = home_ml
    if away_ml is not None:
        odds["away_ml"] = away_ml
    if len(odds) == 1:
        return 0

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    rows = list(cursor.execute(
        "SELECT id, raw_json FROM predictions "
        "WHERE home_team=? AND away_team=? AND date(timestamp)=date('now','localtime')",
        (home, away)))
    updated = 0
    for row in rows:
        try:
            blob = json.loads(row["raw_json"]) if row["raw_json"] else {}
        except (json.JSONDecodeError, TypeError):
            blob = {}
        if not isinstance(blob, dict):
            continue
        blob["market_odds"] = odds
        cursor.execute("UPDATE predictions SET raw_json=? WHERE id=?",
                       (json.dumps(blob), row["id"]))
        updated += 1
    connection.commit()
    connection.close()
    return updated


# ==========================================================================
# RUN
# ==========================================================================

def run_one(home: str, away: str, game: Optional[Dict[str, Any]], total: float,
            total_source: str, push_discord: bool, dry_run: bool,
            home_ml: Optional[int] = None,
            away_ml: Optional[int] = None) -> Dict[str, Any]:
    rule()
    log(f"MLB:  {away}  @  {home}")
    rule("-")

    arguments = pitcher_args(game)
    if game:
        log(f"  Starters   {game.get('away_pitcher') or 'TBD'} "
            f"(ERA {arguments['away_sp_era']}, K/9 {arguments['away_sp_k']})")
        log(f"             {game.get('home_pitcher') or 'TBD'} "
            f"(ERA {arguments['home_sp_era']}, K/9 {arguments['home_sp_k']})")
    else:
        log("  [warn] Not found on today's schedule. Home/away is the order you")
        log("         typed, and no starter data is available -- the model will")
        log("         use its defaults for the pitchers.")
    log(f"  Total      {total}  [{total_source}]")
    if home_ml is not None or away_ml is not None:
        def fmt(value: Optional[int]) -> str:
            return "n/a" if value is None else (f"+{value}" if value > 0 else str(value))
        log(f"  Moneyline  {away} {fmt(away_ml)}  |  {home} {fmt(home_ml)}")

    if dry_run:
        return {"status": "dry-run", "home": home, "away": away}

    from universal_runner import run_baseball
    result = run_baseball(home, away, league="MLB", markets=MARKETS,
                          market_total=total, store_to_db=True,
                          push_discord=push_discord, **arguments)

    tagged = record_market_odds(home, away, total, home_ml, away_ml)
    if tagged:
        log(f"  [odds] real prices attached to {tagged} stored row(s)")
    return {"status": "ok", "home": home, "away": away, "result": result}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--match", action="append", metavar='"TEAM vs TEAM"',
                        help="Repeatable. Order does not matter.")
    parser.add_argument("--today", action="store_true",
                        help="Run every game on today's schedule.")
    parser.add_argument("--total", type=float, action="append", metavar="N",
                        help="Market total. Repeat to give one per --match, or "
                             "pass once to use the same for all.")
    parser.add_argument("--home-ml", type=int, action="append", metavar="ODDS",
                        help="Home moneyline in American odds, e.g. -120.")
    parser.add_argument("--away-ml", type=int, action="append", metavar="ODDS",
                        help="Away moneyline, e.g. +105.")
    parser.add_argument("--odds", action="store_true",
                        help="Fetch live totals from The Odds API (uses quota).")
    parser.add_argument("--no-discord", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-teams", action="store_true")
    args = parser.parse_args()

    teams = load_mlb_teams()
    if not teams:
        rule()
        log("No MLB teams in data/baseball_stats.json.")
        rule()
        log("\nPull them first:")
        log("    venv/Scripts/python.exe ingest_all_sports.py --only mlb")
        sys.exit(1)

    if args.list_teams:
        log(f"{len(teams)} MLB team(s) in the store:\n")
        for name in sorted(teams):
            record = teams[name]
            log(f"  {name:<24} {record.get('runs')} R/g  "
                f"{record.get('runs_allowed')} RA/g  ERA {record.get('era')}")
        return

    games, generated = load_probables()
    if generated and not str(generated).startswith(TODAY):
        log(f"[warn] mlb_probables.json is from {generated}, not today.")
        log("       Refresh it so starters and orientation are current:")
        log("       venv/Scripts/python.exe ingest_all_sports.py --only mlb-probables\n")
    elif not games:
        log("[warn] No games for today in mlb_probables.json. Refresh it:")
        log("       venv/Scripts/python.exe ingest_all_sports.py --only mlb-probables\n")

    # ---- work out what to run -------------------------------------------
    pairs: List[Tuple[str, str, Optional[Dict[str, Any]]]] = []
    problems: List[str] = []

    if args.today:
        for game in games:
            home, away = game.get("home_team"), game.get("away_team")
            if home in teams and away in teams:
                pairs.append((home, away, game))
        if not pairs:
            log("Nothing on today's schedule to run.")
            sys.exit(1)
    else:
        requested = args.match or []
        if not requested:
            parser.error('Give at least one --match "Team vs Team", or use --today.')
        for text in requested:
            try:
                typed_a, typed_b = parse_match(text)
            except ValueError as exc:
                problems.append(str(exc))
                continue
            first, how_a = resolve(typed_a, teams)
            second, how_b = resolve(typed_b, teams)
            for typed, matched, how in ((typed_a, first, how_a), (typed_b, second, how_b)):
                if matched is None:
                    problems.append(f'"{typed}" -> {how}')
                elif how != "exact":
                    log(f'[name] "{typed}" -> "{matched}"  ({how})')
            if not (first and second):
                continue

            # The schedule decides home and away, not the typed order.
            game = find_game(first, second, games)
            if game:
                home, away = game["home_team"], game["away_team"]
                if (home, away) != (first, second):
                    log(f"[home/away] schedule says {away} @ {home} "
                        f"-- using that, not the order typed")
                pairs.append((home, away, game))
            else:
                pairs.append((first, second, None))

    if problems:
        rule()
        log("COULD NOT RESOLVE THESE NAMES")
        rule()
        for problem in problems:
            log(f"  {problem}")
        log("\nTeams in the store:")
        for name in sorted(teams):
            log(f"  {name}")
        log("\nNothing was run.")
        sys.exit(1)

    # ---- discord ---------------------------------------------------------
    push_discord = not args.no_discord and not args.dry_run
    if push_discord and not os.environ.get("DISCORD_WEBHOOK_URL"):
        env = ROOT / ".env"
        if env.exists():
            for raw in env.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                if raw.strip().startswith("DISCORD_WEBHOOK_URL"):
                    os.environ["DISCORD_WEBHOOK_URL"] = \
                        raw.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if push_discord and not os.environ.get("DISCORD_WEBHOOK_URL"):
        log("[warn] DISCORD_WEBHOOK_URL not set -- will predict but not push.")

    live_totals = fetch_live_totals() if args.odds else {}

    rule()
    log(f"MLB  -  {len(pairs)} game(s)   Discord: {'ON' if push_discord else 'OFF'}")
    rule()

    try:
        from data_guard import guard_teams
        involved = [name for home, away, _ in pairs for name in (home, away)]
        safe, note = guard_teams(teams, "baseball", involved)
        if not safe:
            rule()
            log("STALE DATA -- nothing was run")
            rule()
            for line in note.splitlines():
                log(f"  {line}")
            log("\n  Refresh before predicting:")
            log("      venv/Scripts/python.exe ingest_all_sports.py --only mlb")
            sys.exit(1)
        if note != "data age OK":
            log(f"[age] {note.splitlines()[0]}")
    except ImportError:
        pass

    totals = pair_values(args.total, len(pairs), "total")
    home_mls = pair_values(args.home_ml, len(pairs), "home-ml")
    away_mls = pair_values(args.away_ml, len(pairs), "away-ml")

    outcomes: List[Dict[str, Any]] = []
    for index, (home, away, game) in enumerate(pairs):
        key = f"{home}|{away}"
        if key in live_totals:
            total, source = live_totals[key], "live odds"
        elif totals[index] is not None:
            total, source = float(totals[index]), "the line you gave"
        else:
            total, source = DEFAULT_TOTAL, "DEFAULT placeholder"
        try:
            outcomes.append(run_one(home, away, game, total, source,
                                    push_discord, args.dry_run,
                                    home_ml=home_mls[index], away_ml=away_mls[index]))
        except Exception as exc:  # noqa: BLE001
            log(f"  [FAILED] {type(exc).__name__}: {exc}")
            outcomes.append({"status": "failed", "home": home, "away": away,
                             "error": f"{type(exc).__name__}: {exc}"})

    log("")
    rule()
    log("SUMMARY")
    rule()
    for outcome in outcomes:
        marker = {"ok": "OK     ", "failed": "FAILED ",
                  "dry-run": "DRY-RUN"}.get(outcome["status"], "?")
        log(f"  [{marker}] {outcome['away']} @ {outcome['home']}")
        if outcome.get("error"):
            log(f"             {outcome['error']}")
    rule()

    if any(o["status"] == "ok" for o in outcomes):
        if not live_totals and not args.total:
            log(f"\nThe total ({DEFAULT_TOTAL}) was a placeholder. An edge measured")
            log("against a made-up line is just the gap between that guess and the")
            log("book. Use --odds or --total for a real number.")
        log("\nStored to multisport_history.db. Grade tomorrow once they are final:")
        log("    venv/Scripts/python.exe grade_predictions.py --auto --report")


if __name__ == "__main__":
    main()
