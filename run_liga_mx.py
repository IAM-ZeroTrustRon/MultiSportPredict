#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_liga_mx.py - Run Liga MX matches through the model and push to Discord

    python run_liga_mx.py
        Runs Club Leon vs Atlante with default lines.

    python run_liga_mx.py --match "Club Leon vs Atlante"
    python run_liga_mx.py --match "Toluca vs Pachuca" --match "Cruz Azul vs Necaxa"
    python run_liga_mx.py --match "Leon vs Atlante" --total 2.5 --line -0.5
    python run_liga_mx.py --no-discord          run without pushing
    python run_liga_mx.py --list-teams          what is in the store
    python run_liga_mx.py --dry-run             resolve names, predict nothing

NAME MATCHING
    The football-data feed spells clubs its own way -- "Club Leon", not "Leon";
    "Guadalajara Chivas", not "Chivas". The lookup is an exact name match, so a
    near-miss silently finds nothing. This script resolves what you type against
    the store first and tells you what it matched, so a typo shows up as a
    question rather than as a missing prediction.

BEFORE RUNNING
    Liga MX data must be in data/soccer_stats.json:
        python ingest_soccer_fd.py --countries mexico

A NOTE ON THE NUMBERS
    Liga MX rows carry xG estimated from goals (data_tier 2) because no
    reachable source publishes real xG. The season is also young. Both mean a
    recommendation here rests on thinner evidence than the same number would in
    a league with real xG and a full season behind it.
"""

from __future__ import annotations

import argparse
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

STORE = ROOT / "data" / "soccer_stats.json"
LEAGUE = "Liga MX"

DEFAULT_TOTAL = 2.5     # placeholder -- see the warning printed at runtime
DEFAULT_LINE = 0.0


def log(message: str = "") -> None:
    print(message, flush=True)


def rule(char: str = "=") -> None:
    log(char * 78)


# ==========================================================================
# TEAM NAME RESOLUTION
# ==========================================================================

def load_liga_mx_teams() -> Dict[str, Dict[str, Any]]:
    if not STORE.exists():
        return {}
    try:
        store = json.loads(STORE.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        log(f"[error] {STORE.name} is not valid JSON.")
        return {}
    return {
        name: record for name, record in store.items()
        if not name.startswith("_")
        and isinstance(record, dict)
        and str(record.get("league", "")).lower() == LEAGUE.lower()
    }


def squash(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def resolve(typed: str, teams: Dict[str, Dict[str, Any]]) -> Tuple[Optional[str], str]:
    """Return (matched_name, how). Never guesses past a clear best match."""
    if not typed:
        return None, "empty"
    if typed in teams:
        return typed, "exact"

    target = squash(typed)
    squashed = {squash(name): name for name in teams}

    if target in squashed:
        return squashed[target], "case/punctuation"

    # "Leon" should find "Club Leon"; "Chivas" should find "Guadalajara Chivas".
    contains = [real for flat, real in squashed.items()
                if target and (target in flat or flat in target)]
    if len(contains) == 1:
        return contains[0], "partial"
    if len(contains) > 1:
        return None, f"ambiguous: {', '.join(sorted(contains))}"

    close = difflib.get_close_matches(target, list(squashed), n=3, cutoff=0.75)
    if len(close) == 1:
        return squashed[close[0]], "fuzzy"
    if close:
        return None, f"ambiguous: {', '.join(squashed[c] for c in close)}"
    return None, "no match"


def parse_match(text: str) -> Tuple[str, str]:
    for separator in (" vs ", " VS ", " v ", " @ ", " - "):
        if separator in text:
            home, away = text.split(separator, 1)
            return home.strip(), away.strip()
    raise ValueError(f'Could not read "{text}". Use the form: "Home vs Away"')


# ==========================================================================
# RUN
# ==========================================================================

def run_match(home: str, away: str, total: float, line: float,
              push_discord: bool, dry_run: bool) -> Dict[str, Any]:
    rule()
    log(f"{LEAGUE}:  {home}  vs  {away}")
    rule("-")

    teams = load_liga_mx_teams()
    for label, record in (("home", teams.get(home)), ("away", teams.get(away))):
        if record:
            games = record.get("games", "?")
            log(f"  {label:<5} {record.get('goals_for')} GF/g, "
                f"{record.get('goals_against')} GA/g over {games} game(s)"
                + (f", form {record.get('form_last5_ppg')} ppg"
                   if record.get("form_last5_ppg") is not None else ""))

    log(f"  total {total}   line {line}")

    if dry_run:
        log("  (dry run -- nothing predicted, nothing pushed)")
        return {"status": "dry-run", "home": home, "away": away}

    from universal_runner import run_soccer
    result = run_soccer(
        home, away, league=LEAGUE,
        market_line=line, market_total=total,
        store_to_db=True, push_discord=push_discord,
    )
    return {"status": "ok", "home": home, "away": away, "result": result}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--match", action="append", metavar='"HOME vs AWAY"',
                        help="Repeatable. Defaults to Club Leon vs Atlante.")
    parser.add_argument("--total", type=float, default=DEFAULT_TOTAL,
                        help=f"Market total (default {DEFAULT_TOTAL}, a placeholder).")
    parser.add_argument("--line", type=float, default=DEFAULT_LINE,
                        help=f"Market line / handicap (default {DEFAULT_LINE}).")
    parser.add_argument("--no-discord", action="store_true", help="Do not push.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Resolve names and show the data, predict nothing.")
    parser.add_argument("--list-teams", action="store_true",
                        help="List the Liga MX teams currently in the store.")
    args = parser.parse_args()

    teams = load_liga_mx_teams()

    if not teams:
        rule()
        log("No Liga MX teams in data/soccer_stats.json.")
        rule()
        log("\nPull the league first:")
        log("    venv/Scripts/python.exe ingest_soccer_fd.py --countries mexico")
        log("\n(If you ran that with --check, it downloaded but wrote nothing by design.)")
        sys.exit(1)

    if args.list_teams:
        log(f"{len(teams)} Liga MX team(s) in the store:\n")
        for name in sorted(teams):
            record = teams[name]
            log(f"  {name:<24} {record.get('goals_for')} GF/g  "
                f"{record.get('goals_against')} GA/g  ({record.get('games')} games)")
        return

    requested = args.match or ["Club Leon vs Atlante"]

    # Resolve every name before predicting anything, so a typo is caught up
    # front rather than halfway through a slate.
    resolved: List[Tuple[str, str]] = []
    problems: List[str] = []
    for text in requested:
        try:
            typed_home, typed_away = parse_match(text)
        except ValueError as exc:
            problems.append(str(exc))
            continue
        home, home_how = resolve(typed_home, teams)
        away, away_how = resolve(typed_away, teams)
        for typed, matched, how in ((typed_home, home, home_how),
                                    (typed_away, away, away_how)):
            if matched is None:
                problems.append(f'"{typed}" -> {how}')
            elif how != "exact":
                log(f"[name] \"{typed}\" -> \"{matched}\"  ({how})")
        if home and away:
            resolved.append((home, away))

    if problems:
        rule()
        log("COULD NOT RESOLVE THESE NAMES")
        rule()
        for problem in problems:
            log(f"  {problem}")
        log("\nTeams in the store:")
        for name in sorted(teams):
            log(f"  {name}")
        log("\nNothing was run. Fix the names and try again -- the alternative is")
        log("a prediction built on the wrong club, which is worse than no prediction.")
        sys.exit(1)

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

    rule()
    log(f"LIGA MX  -  {len(resolved)} match(es)   "
        f"Discord: {'ON' if push_discord else 'OFF'}")
    rule()

    outcomes: List[Dict[str, Any]] = []
    for home, away in resolved:
        try:
            outcomes.append(run_match(home, away, args.total, args.line,
                                      push_discord, args.dry_run))
        except Exception as exc:  # noqa: BLE001
            log(f"  [FAILED] {type(exc).__name__}: {exc}")
            outcomes.append({"status": "failed", "home": home, "away": away,
                             "error": f"{type(exc).__name__}: {exc}"})

    log("")
    rule()
    log("SUMMARY")
    rule()
    for outcome in outcomes:
        marker = {"ok": "OK     ", "failed": "FAILED ", "dry-run": "DRY-RUN"}.get(
            outcome["status"], "?")
        log(f"  [{marker}] {outcome['home']} vs {outcome['away']}")
        if outcome.get("error"):
            log(f"             {outcome['error']}")
    rule()

    if any(o["status"] == "ok" for o in outcomes):
        log(f"\nThe total ({args.total}) and line ({args.line}) are placeholders unless")
        log("you passed real ones. An edge measured against a made-up line is just")
        log("the gap between that guess and the book.")
        log("\nStored to multisport_history.db. Grade it once the match is final:")
        log("    venv/Scripts/python.exe grade_predictions.py --pending")


if __name__ == "__main__":
    main()
