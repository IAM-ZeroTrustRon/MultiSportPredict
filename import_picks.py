#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
import_picks.py - Load someone else's pick sheet as informational rows

    python import_picks.py sheet.csv --check          parse and report, write nothing
    python import_picks.py sheet.csv --source lalfredo
    python import_picks.py --report --source lalfredo does the star rating predict?

WHAT THIS IS FOR
    A friend sends a CSV of plays. You want to know whether they win, without
    their record contaminating yours and without betting them to find out.

    Every row lands with recommendation "INFO" and source_kind "external", so
    grade_predictions.py counts them as calibration, never as your bets. Your
    own record stays your own.

WHAT IT KEEPS AND WHAT IT IGNORES
    Kept: game, date, market, side, line, odds, the tipster's confidence, the
    reasoning text, and every source URL.

    Kept but never used as a signal: gematria columns. They ride along in
    raw_json so that if a pattern ever shows up in the graded results you can
    find it. Nothing reads them to make a decision, because in the sheet this
    was built from they did not vary with the ratings -- the same player
    carried the same cipher value on 5-star, 4-star and 3-star plays.

THE CORRELATION WARNING IS THE POINT
    The sheet that prompted this had 39 rows on ONE game. Team total over,
    quarterback attempts over, receiver yards over and game total under all
    resolve on the same script. Counted as 39 plays that is a diversified card;
    it is actually one position in 39 costumes. The importer counts rows per
    game and says so, because a star rating cannot tell you that.

WHAT CAN AND CANNOT BE GRADED
    Game-level markets -- spread, moneyline, game total, team total -- grade
    from a scoreboard.

    Player props cannot. No reachable feed publishes whether a receiver went
    over 47.5 yards. They import, they are marked needs_manual, and they wait
    for a score you type in. Pretending otherwise would create a record built
    on ungraded rows, which is worse than no record.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "multisport_history.db"

GAME_MARKETS = {"spread", "moneyline", "game total", "team total", "total"}

# Column names seen in the wild. Matching is case- and space-insensitive.
ALIASES = {
    "game": ("game", "matchup", "match"),
    "date": ("date", "game date", "gamedate"),
    "market": ("market", "market type", "bet type"),
    "pick": ("pick", "selection", "play", "bet"),
    "odds": ("odds / line", "odds", "price", "line"),
    "stars": ("star rating", "stars", "confidence", "rating"),
    "team": ("team",),
    "player": ("player",),
    "reason": ("market / model signal", "reasoning", "notes", "signal"),
    "sport_type": ("type",),
}


def log(message: str = "") -> None:
    print(message, flush=True)


def rule(char: str = "=") -> None:
    log(char * 78)


def pick_col(row: Dict[str, Any], key: str) -> Optional[str]:
    lookup = {str(k).strip().lower(): v for k, v in row.items() if k}
    for name in ALIASES[key]:
        value = lookup.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def split_game(text: str) -> Tuple[Optional[str], Optional[str]]:
    """'#19 SMU @ Florida State' -> ('Florida State', 'SMU'). Home is second."""
    if not text:
        return None, None
    cleaned = re.sub(r"#\d+\s*", "", text).strip()
    for separator in (" @ ", " at ", " vs ", " v "):
        if separator in cleaned:
            first, second = [p.strip() for p in cleaned.split(separator, 1)]
            if separator in (" @ ", " at "):
                return second, first          # "A @ B" -> B is home
            return first, second              # "A vs B" -> A is home
    return None, None


def parse_odds(text: Optional[str]) -> Optional[float]:
    """First American price in a string like '-115 to -122' or '+127 to +140'.

    A range is a range; taking the first number records what was available at
    the better end. It is written down either way, so a settlement can use the
    real number rather than assuming -110.
    """
    if not text:
        return None
    match = re.search(r"([+-]\d{3,5})", text)
    if match:
        return float(match.group(1))
    match = re.search(r"\b(\d{3,5})\b", text)
    return -float(match.group(1)) if match else None


def parse_line(text: Optional[str]) -> Optional[float]:
    """The number being bet: 'Over 53.5 / 54.5' -> 53.5, 'SMU -2.5' -> -2.5."""
    if not text:
        return None
    match = re.search(r"([+-]?\d+(?:\.\d+)?)", text)
    return float(match.group(1)) if match else None


def side_of(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    lowered = text.lower()
    for word in ("over", "under", "yes", "no"):
        if re.search(rf"\b{word}\b", lowered):
            return word.upper()
    return None


def normalise_market(text: Optional[str]) -> str:
    return (text or "unknown").strip().lower()


# ==========================================================================
# PARSE
# ==========================================================================

def parse_sheet(path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        raw_rows = [r for r in csv.DictReader(handle) if any(
            str(v).strip() for v in r.values())]

    picks: List[Dict[str, Any]] = []
    problems: List[str] = []

    for index, row in enumerate(raw_rows, start=2):
        game = pick_col(row, "game")
        market = normalise_market(pick_col(row, "market"))
        selection = pick_col(row, "pick")
        if not game or not selection:
            problems.append(f"line {index}: missing game or pick -- skipped")
            continue

        home, away = split_game(game)
        if not home or not away:
            problems.append(f"line {index}: cannot read '{game}' -- skipped")
            continue

        stars = pick_col(row, "stars")
        try:
            star_value = float(re.sub(r"[^\d.]", "", stars or "")) or None
        except ValueError:
            star_value = None

        is_prop = market not in GAME_MARKETS and bool(pick_col(row, "player"))
        picks.append({
            "game": game, "home": home, "away": away,
            "date": pick_col(row, "date"),
            "market": market, "selection": selection,
            "player": pick_col(row, "player"),
            "line": parse_line(selection), "side": side_of(selection),
            "odds": parse_odds(pick_col(row, "odds")),
            "stars": star_value,
            "reason": pick_col(row, "reason"),
            "gradable": not is_prop,
            "raw": {k: v for k, v in row.items() if k and str(v).strip()},
        })
    return picks, problems


# ==========================================================================
# STORE
# ==========================================================================

def store(picks: List[Dict[str, Any]], source: str, sport: str) -> Tuple[int, int]:
    conn = sqlite3.connect(DB_PATH)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    inserted = skipped = 0
    for pick in picks:
        existing = conn.execute(
            "SELECT id FROM predictions WHERE sport=? AND home_team=? AND "
            "away_team=? AND market_type=? AND game_date IS ? AND "
            "raw_json LIKE ?",
            (sport, pick["home"], pick["away"], pick["market"], pick["date"],
             f'%"selection": "{pick["selection"]}"%')).fetchone()
        if existing:
            skipped += 1
            continue

        payload = {
            "source_kind": "external",
            "tipster": source,
            "selection": pick["selection"],
            "player": pick["player"],
            "line": pick["line"],
            "side": pick["side"],
            "odds": pick["odds"],
            "stars": pick["stars"],
            "reasoning": pick["reason"],
            "gradable_from_scoreboard": pick["gradable"],
            # Carried, never consulted. If a pattern ever shows in the graded
            # results, the numbers are here to find it with.
            "tipster_metadata": {k: v for k, v in pick["raw"].items()
                                 if any(t in k.lower() for t in
                                        ("gematria", "ordinal", "reduction",
                                         "date keys", "birthday", "jersey"))},
            "market_odds": {"price": pick["odds"]} if pick["odds"] else None,
        }
        conn.execute(
            "INSERT INTO predictions (sport, home_team, away_team, market_type, "
            "model_value, market_value, edge, confidence, recommendation, "
            "timestamp, raw_json, game_date, league, pick) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sport, pick["home"], pick["away"], pick["market"],
             None, pick["line"], None,
             (pick["stars"] * 20.0) if pick["stars"] else None,
             # INFO, never BET. grade_predictions.py splits on this, so these
             # can never be counted inside your own betting record.
             "INFO",
             now, json.dumps(payload), pick["date"],
             sport.upper(), pick["selection"][:120]))
        inserted += 1
    conn.commit()
    conn.close()
    return inserted, skipped


# ==========================================================================
# REPORT
# ==========================================================================

def report(source: str, sport: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = [r for r in conn.execute(
        "SELECT * FROM predictions WHERE sport=? AND recommendation='INFO'",
        (sport,)) if f'"tipster": "{source}"' in (r["raw_json"] or "")]
    conn.close()

    if not rows:
        log(f"No imported picks from '{source}'.")
        return

    graded = [r for r in rows if r["result_outcome"] in ("win", "loss")]
    rule()
    log(f"IMPORTED PICKS  -  {source}   {len(rows)} logged, {len(graded)} graded")
    rule()

    if not graded:
        log("\nNothing graded yet, so there is nothing to conclude. That is the")
        log("honest state -- a sheet of predictions is not a record.")
        log("\nGame-level markets grade with:")
        log("    venv/Scripts/python.exe grade_predictions.py --auto")
        log("Player props need scores typed in:")
        log("    venv/Scripts/python.exe grade_predictions.py --pending")
        rule()
        return

    log(f"\n{'STARS':<8}{'W-L':>10}{'WIN%':>9}{'n':>6}")
    log("  " + "-" * 30)
    by_star: Dict[Any, List[str]] = defaultdict(list)
    for row in graded:
        stars = json.loads(row["raw_json"] or "{}").get("stars")
        by_star[stars].append(row["result_outcome"])
    for stars in sorted(by_star, key=lambda s: (s is None, s), reverse=True):
        outcomes = by_star[stars]
        wins = outcomes.count("win")
        label = f"{int(stars)}-star" if stars else "unrated"
        log(f"{label:<8}{f'{wins}-{len(outcomes)-wins}':>10}"
            f"{wins/len(outcomes):>8.1%}{len(outcomes):>6}")

    log("\nWhat to look for: do 5-star plays beat 3-star plays, by more than")
    log("noise? Under about 30 settled bets per tier, they will not separate")
    log("no matter what is true. Give it a season before concluding anything.")
    rule()


# ==========================================================================
# MAIN
# ==========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_file", nargs="?", type=Path)
    parser.add_argument("--source", default="external",
                        help="Who sent it. Keeps their record separate.")
    parser.add_argument("--sport", default="ncaaf")
    parser.add_argument("--check", action="store_true",
                        help="Parse and report, write nothing.")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    if args.report:
        report(args.source, args.sport)
        return
    if not args.csv_file:
        parser.error("Give a CSV file, or --report")
    if not args.csv_file.exists():
        parser.error(f"No such file: {args.csv_file}")

    picks, problems = parse_sheet(args.csv_file)
    rule()
    log(f"IMPORT  -  {args.csv_file.name}   source '{args.source}'")
    rule()
    if problems:
        for problem in problems[:8]:
            log(f"  {problem}")
    if not picks:
        log("\nNothing readable in that file. Nothing was written.")
        sys.exit(1)

    by_game = Counter(p["game"] for p in picks)
    gradable = [p for p in picks if p["gradable"]]
    stars = Counter(p["stars"] for p in picks)

    log(f"\n  {len(picks)} picks across {len(by_game)} game(s)")
    log(f"  {len(gradable)} grade from a scoreboard, "
        f"{len(picks) - len(gradable)} are player props needing manual scores")
    log("  stars: " + ", ".join(
        f"{int(s)}★ x{n}" for s, n in sorted(stars.items(), reverse=True) if s))

    biggest, count = by_game.most_common(1)[0]
    if count >= 5:
        log("")
        log(f"  CORRELATION WARNING")
        log(f"  {count} of these {len(picks)} picks are the same game:")
        log(f"      {biggest}")
        log(f"  Bets on one game do not settle independently. A team total")
        log(f"  over, a quarterback attempts over and a game total under all")
        log(f"  live or die on the same script. Sized as {count} separate")
        log(f"  plays this is far more exposure than the star ratings suggest.")

    if args.check:
        log("\n--check: nothing was written.")
        return

    inserted, skipped = store(picks, args.source, args.sport)
    log(f"\n  Stored {inserted} new, skipped {skipped} already present.")
    log(f"  All logged as recommendation='INFO' -- they can never be counted")
    log(f"  inside your own betting record.")
    log("\nNext:")
    log(f"    venv/Scripts/python.exe grade_predictions.py --auto --sport {args.sport}")
    log(f"    venv/Scripts/python.exe import_picks.py --report --source {args.source}")


if __name__ == "__main__":
    main()
