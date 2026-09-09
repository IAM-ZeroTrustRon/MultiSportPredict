#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_nfl.py - Run NFL games through the model, review, then push

    python run_nfl.py --match "Kansas City Chiefs vs Buffalo Bills"
    python run_nfl.py --match "Chiefs vs Bills" --odds
    python run_nfl.py --week 1 --odds                 the whole slate from the schedule
    python run_nfl.py --match "A vs B" --spread -2.5 --total 47.5 --home-ml -135 --away-ml 115
    python run_nfl.py --push 1 3                      push after reading the table
    python run_nfl.py --list-teams
    python run_nfl.py --dry-run

HOME TEAM FIRST -- BUT THE SCHEDULE OVERRULES YOU
    Type "Chiefs vs Bills" and the fixture check looks the game up in
    data/nfl_schedule.json. If the feed says Buffalo is home, it uses that and
    says so. Typed matchups have been logged backwards in this project before,
    which grades correctly and applies home-field advantage to the wrong team.

    A matchup that is not on the schedule is REFUSED. Nine predictions were
    once produced here for games nobody had scheduled, each with a confidence
    score and a Discord embed, and nothing downstream could tell them apart
    from real ones.

NOTHING IS PUSHED UNTIL YOU SAY SO
    Games are predicted, stored and printed. --push takes line numbers.

ODDS
    --odds pulls h2h, spreads and totals from The Odds API for
    americanfootball_nfl. Without a line there is no ATS and no total, and a
    moneyline with no price produces a PASS at ~50 that reads as "no opinion"
    when the model has one. Hand-passed values always win over the feed.

BEFORE THE FIRST RUN
    python ingest_nfl.py --season 2025           team stats
    python ingest_nfl_schedule.py --season 2025  schedule + first-half splits
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

REVIEW = ROOT / "data" / "nfl_review.json"
SPORT_KEY = "americanfootball_nfl"


def log(message: str = "") -> None:
    print(message, flush=True)


def rule(char: str = "=", width: int = 96) -> None:
    log(char * width)


def parse_match(text: str) -> Tuple[str, str]:
    for separator in (" vs ", " VS ", " v ", " @ ", " at ", " - "):
        if separator in text:
            first, second = text.split(separator, 1)
            return first.strip(), second.strip()
    raise ValueError(f'Could not read "{text}". Use: "Home vs Away"')


# ==========================================================================
# ODDS
# ==========================================================================

from ingest_nfl_schedule import norm_team as _norm   # strips a "(2025)" suffix


def fetch_odds() -> Dict[str, Dict[str, Optional[float]]]:
    """(home|away) -> {spread, total, home_ml, away_ml}. Empty on any failure.

    The spread is stored from the HOME side, which is how the model wants it:
    -3 means the home team lays three.
    """
    try:
        from OddsApiIngestor import OddsApiIngestor
    except ImportError:
        log("[odds] OddsApiIngestor not importable -- no lines fetched.")
        return {}
    try:
        events = OddsApiIngestor(markets="h2h,spreads,totals").fetch_live_odds(
            SPORT_KEY, days=8)
    except Exception as exc:                            # noqa: BLE001
        log(f"[odds] failed ({type(exc).__name__}) -- no lines fetched.")
        return {}
    if not events:
        log("[odds] no events returned.")
        return {}

    out: Dict[str, Dict[str, Optional[float]]] = {}
    for event in events:
        home, away = event.get("home_team"), event.get("away_team")
        if not home or not away:
            continue
        entry: Dict[str, Optional[float]] = {
            "spread": None, "total": None, "home_ml": None, "away_ml": None}
        for book in event.get("bookmakers", []):
            for market in book.get("markets", []):
                kind, outcomes = market.get("key"), market.get("outcomes", [])
                prices = {o.get("name"): o for o in outcomes}
                if kind == "spreads" and entry["spread"] is None:
                    if home in prices and prices[home].get("point") is not None:
                        entry["spread"] = float(prices[home]["point"])
                elif kind == "totals" and entry["total"] is None:
                    for outcome in outcomes:
                        if outcome.get("point") is not None:
                            entry["total"] = float(outcome["point"])
                            break
                elif kind == "h2h" and entry["home_ml"] is None:
                    if (prices.get(home, {}).get("price") is not None
                            and prices.get(away, {}).get("price") is not None):
                        entry["home_ml"] = float(prices[home]["price"])
                        entry["away_ml"] = float(prices[away]["price"])
            if all(v is not None for v in entry.values()):
                break
        out[f"{_norm(home)}|{_norm(away)}"] = entry

    found = sum(1 for e in out.values() if e["spread"] is not None)
    log(f"[odds] {len(out)} game(s), {found} with a spread")
    return out


# ==========================================================================
# RUN
# ==========================================================================

def run_one(home: str, away: str, lines: Dict[str, Optional[float]],
            neutral: bool, push: bool) -> Dict[str, Any]:
    from universal_runner import run_nfl
    return run_nfl(
        home, away,
        market_spread=lines.get("spread"), market_total=lines.get("total"),
        market_home_ml=lines.get("home_ml"), market_away_ml=lines.get("away_ml"),
        neutral_site=neutral, store_to_db=True, push_discord=push,
    )


def show_review(rows: List[Dict[str, Any]]) -> None:
    log("")
    rule("=", 110)
    log("📋  REVIEW  —  model vs market.  Nothing has been pushed.")
    rule("=", 110)
    header = (
        f"  {'#':>2}  {'🏈 GAME':<46}{'📐 SPREAD':>20}{'📊 TOTAL':>18}  🏆 ML"
    )
    log(header)
    log("  " + "-" * 110)
    for index, row in enumerate(rows, start=1):
        spread, total, ml = row["spread"], row["total"], row["moneyline"]
        spread_text = (f"{spread.get('edge_points', 0):+.1f} {spread.get('pick', '-')}"
                       if spread.get("market_spread") is not None else "🚫 no line")
        total_text = (f"{total.get('edge_points', 0):+.1f} {total.get('pick', '-')}"
                      if total.get("market_total") is not None else "🚫 no line")
        ml_text = (f"{ml.get('edge_pct', 0):+.1f} {ml.get('recommendation', '-')}"
                   if ml.get("market_home_prob") is not None else "🚫 no price")
        log(f"  {index:>2}  {row['away'] + ' at ' + row['home']:<46}"
            f"{spread_text:>20}{total_text:>18}  {ml_text}")
    rule("-", 110)
    log("  💡  Push the ones you want:")
    log("      venv/Scripts/python.exe run_nfl.py --push 1 3")
    log("")
    if rows and rows[0]["prior_blend"]["current_season_weight"] < 0.5:
        log("  ⚠️   These are running on LAST SEASON, regressed toward the mean. A")
        log("      large disagreement with the market right now means the model is")
        log("      wrong, not the market -- it has no 2026 games, no roster changes")
        log("      and no idea who is starting at quarterback.")
        log("")
    log("  ℹ️   NFL margins pile up on 3 and 7. An edge under 1.5 points beside one")
    log("      of those is noise, and is passed automatically.")
    rule("=", 110)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--match", action="append", metavar='"HOME vs AWAY"')
    parser.add_argument("--week", type=int, help="Run a whole week from the schedule.")
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--odds", action="store_true", help="Fetch live lines.")
    parser.add_argument("--spread", type=float, action="append")
    parser.add_argument("--total", type=float, action="append")
    parser.add_argument("--home-ml", type=float, action="append")
    parser.add_argument("--away-ml", type=float, action="append")
    parser.add_argument("--neutral-site", action="store_true")
    parser.add_argument("--push", nargs="+", type=int, metavar="N")
    parser.add_argument("--no-fixture-check", action="store_true",
                        help="Run a matchup that is not on the schedule. Say why to yourself first.")
    parser.add_argument("--list-teams", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from models.nfl_predictor import load_store, resolve_team, MissingTeam

    try:
        store = load_store()
    except MissingTeam as exc:
        rule(); log(str(exc)); rule(); sys.exit(1)

    if args.list_teams:
        log(f"{len(store)} team(s):\n")
        for name in sorted(store):
            record = store[name]
            log(f"  {name:<34} {record.get('points_for')} PF/g  "
                f"{record.get('points_against')} PA/g  "
                f"({record.get('games')} games, {record.get('season')})"
                + ("" if record.get("points_1h_for") is not None
                   else "   <- no 1H data"))
        return

    # ---- push from a saved review ----
    if args.push:
        if not REVIEW.exists():
            log("Nothing to push -- no review on file. Run the games first.")
            sys.exit(1)
        saved = json.loads(REVIEW.read_text(encoding="utf-8-sig"))
        rows = saved.get("rows", [])
        for number in args.push:
            if not 1 <= number <= len(rows):
                log(f"  [skip] {number} is not a line (1..{len(rows)})")
                continue
            row = rows[number - 1]
            log(f"  pushing {number}. {row['away']} at {row['home']}")
            run_one(row["home"], row["away"], row.get("lines", {}),
                    row.get("neutral_site", False), push=True)
        return

    # ---- build the card ----
    from ingest_nfl_schedule import home_away, load_schedule

    requested: List[Tuple[str, str]] = []
    if args.week:
        season = args.season or _dt.date.today().year
        games = [g for g in load_schedule()
                 if g["week"] == args.week and g["season"] == season]
        if not games:
            log(f"No week {args.week} games for {season} in the schedule.")
            log("    venv/Scripts/python.exe ingest_nfl_schedule.py --season "
                f"{season}")
            sys.exit(1)
        requested = [(g["home_team"], g["away_team"]) for g in games]
        log(f"[schedule] week {args.week} of {season}: {len(requested)} games")
    else:
        for text in args.match or []:
            try:
                requested.append(parse_match(text))
            except ValueError as exc:
                log(str(exc)); sys.exit(1)
    if not requested:
        parser.error('Give --match "Home vs Away" or --week N')

    # ---- resolve names, then verify the fixture ----
    resolved: List[Tuple[str, str]] = []
    problems: List[str] = []
    for typed_home, typed_away in requested:
        try:
            home = resolve_team(typed_home, store)
            away = resolve_team(typed_away, store)
        except MissingTeam as exc:
            problems.append(str(exc))
            continue

        if not args.no_fixture_check:
            feed_home, feed_away, note = home_away(home, away)
            if feed_home is None:
                problems.append(f"{home} vs {away}: {note}")
                continue
            if _norm(feed_home) != _norm(home):
                log(f"[home/away] schedule says {feed_away} at {feed_home} "
                    f"-- using that, not the order typed")
                home, away = feed_home, feed_away
            else:
                log(f"[fixture] {away} at {home}  ({note})")
        resolved.append((home, away))

    if problems:
        rule()
        log("NOTHING WAS RUN")
        rule()
        for problem in problems:
            log(f"  {problem}")
        log("\nA prediction for a game nobody is playing looks exactly like a real")
        log("one. If you are certain the fixture exists and the schedule is stale,")
        log("refresh it -- or pass --no-fixture-check deliberately.")
        sys.exit(1)

    lines_by_game: Dict[str, Dict[str, Optional[float]]] = fetch_odds() if args.odds else {}

    def lines_for(index: int, home: str, away: str) -> Dict[str, Optional[float]]:
        entry = dict(lines_by_game.get(f"{_norm(home)}|{_norm(away)}",
                                       {"spread": None, "total": None,
                                        "home_ml": None, "away_ml": None}))
        # Hand-passed values win over the feed.
        for key, values in (("spread", args.spread), ("total", args.total),
                            ("home_ml", args.home_ml), ("away_ml", args.away_ml)):
            if values and index < len(values):
                entry[key] = values[index]
        return entry

    rule()
    log(f"NFL  -  {len(resolved)} game(s)   Discord: OFF")
    rule()

    rows: List[Dict[str, Any]] = []
    for index, (home, away) in enumerate(resolved):
        lines = lines_for(index, home, away)
        if args.dry_run:
            log(f"  [dry-run] {away} at {home}   lines={lines}")
            continue
        try:
            result = run_one(home, away, lines, args.neutral_site, push=False)
            result["lines"] = lines
            result["neutral_site"] = args.neutral_site
            rows.append(result)
        except Exception as exc:                        # noqa: BLE001
            log(f"  [FAILED] {away} at {home}: {type(exc).__name__}: {exc}")

    if args.dry_run or not rows:
        return

    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    REVIEW.write_text(json.dumps(
        {"generated": _dt.datetime.now().isoformat(timespec="seconds"),
         "rows": rows}, indent=2, default=str), encoding="utf-8")
    show_review(rows)


if __name__ == "__main__":
    main()
