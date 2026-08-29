#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
grade_predictions.py - Close the loop on every prediction pushed to Discord
============================================================================

multisport_history.db has logged 104 predictions and graded zero of them. The
schema always had result_outcome and profit_loss columns, and
core/historical_storage.py has always had update_prediction_outcome() -- but
nothing ever called it. This is the piece that calls it, so you get a real
win-rate record instead of a pile of ungraded forecasts.

    python grade_predictions.py --pending            what still needs a result
    python grade_predictions.py --auto               fetch results and grade
    python grade_predictions.py --manual results.csv grade from a filled-in sheet
    python grade_predictions.py --report             the win-rate record
    python grade_predictions.py --report --push-discord

TYPICAL DAILY USE (after the previous day's games have finished):

    python grade_predictions.py --auto --report

WHAT "GRADED" MEANS HERE
    total     : OVER if the model's projected total beat the market line, else
                UNDER. Compared against the actual combined score.
    moneyline : HOME if the model gave the home side better than even odds,
                else AWAY. A draw is a loss in soccer and a push elsewhere.
    btts      : YES above even odds, else NO. Compared against both teams
                having scored.
    spread    : left ungraded. The stored model_value does not record which
                side the number belongs to, so grading it would be guesswork.
                Fix that at the point predictions are written, not here.

Nothing is graded from a guess. A prediction with no matching final score
stays ungraded and shows up in --pending forever until a result arrives.

PROFIT/LOSS uses -110 pricing (risk 1 to win 0.909) unless the prediction's
raw_json carries real odds. That is a modelling convention, not a claim about
what you were actually priced at -- treat the unit record as directional.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import os
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "multisport_history.db"
PENDING_CSV = ROOT / "pending_results.csv"

DEFAULT_ODDS = -110.0
HTTP_TIMEOUT = 30
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


def log(message: str = "") -> None:
    print(message, flush=True)


# ==========================================================================
# SCHEMA
# ==========================================================================

EXTRA_COLUMNS = {
    "game_date": "TEXT",            # the day the game was played
    "league": "TEXT",
    "pick": "TEXT",                 # OVER / UNDER / HOME / AWAY / YES / NO
    "actual_home_score": "REAL",
    "actual_away_score": "REAL",
    "graded_at": "TEXT",
    "grade_note": "TEXT",
}


def ensure_schema(conn: sqlite3.Connection) -> List[str]:
    """Add the columns grading needs. Safe to run repeatedly."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(predictions)")}
    added: List[str] = []
    for column, column_type in EXTRA_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE predictions ADD COLUMN {column} {column_type}")
            added.append(column)
    # A prediction is almost always made on the day of the game or the evening
    # before. Backfilling from the timestamp is an assumption, so it is recorded
    # as one -- rows fixed later by a real result will overwrite it.
    conn.execute("""
        UPDATE predictions
        SET game_date = date(timestamp)
        WHERE game_date IS NULL AND timestamp IS NOT NULL
    """)
    conn.commit()
    return added


# ==========================================================================
# NORMALISATION
# ==========================================================================

def tier_of(recommendation: Optional[str]) -> str:
    """Collapse the messy recommendation strings into a decision tier.

    Some rows hold clean values ('BET'), others hold raw model output like
    'Over: 44.5% | Under: 55.5%'. Only the first kind represents a decision to
    place a bet; the rest are informational and are reported separately rather
    than being counted as wagers.
    """
    text = (recommendation or "").strip().upper()
    if text.startswith("STRONG BET"):
        return "STRONG BET"
    if text == "BET":
        return "BET"
    if text in {"PASS", "NO BET"}:
        return "PASS"
    return "INFO"


def normalise_team(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def american_to_profit(odds: float) -> float:
    """Profit on a 1-unit win at American odds."""
    return (100.0 / abs(odds)) if odds < 0 else (odds / 100.0)


# ==========================================================================
# GRADING
# ==========================================================================

class Ungradable(Exception):
    pass


def grade_row(row: sqlite3.Row, home_score: float, away_score: float) -> Tuple[str, str, float]:
    """Return (outcome, pick, profit_loss) for one prediction.

    outcome is 'win' | 'loss' | 'push' -- the three values
    update_prediction_outcome() already expects.
    """
    market = (row["market_type"] or "").strip().lower()
    model_value = row["model_value"]
    market_value = row["market_value"]
    sport = (row["sport"] or "").strip().lower()
    total = home_score + away_score

    if market == "total":
        if model_value is None or market_value is None:
            raise Ungradable("total needs both a projection and a market line")
        pick = "OVER" if model_value > market_value else "UNDER"
        if abs(total - market_value) < 1e-9:
            outcome = "push"
        elif (total > market_value) == (pick == "OVER"):
            outcome = "win"
        else:
            outcome = "loss"

    elif market == "moneyline":
        if model_value is None:
            raise Ungradable("moneyline needs a home win probability")
        pick = "HOME" if model_value >= 0.5 else "AWAY"
        if home_score > away_score:
            winner = "HOME"
        elif away_score > home_score:
            winner = "AWAY"
        else:
            # Soccer settles a draw as a loss on a two-way price; the other
            # sports here cannot draw, so a tie means the data is wrong.
            if sport in {"soccer", "football"}:
                return "loss", pick, -1.0
            raise Ungradable(f"tie score in {sport}, which should not happen")
        outcome = "win" if pick == winner else "loss"

    elif market == "btts":
        if model_value is None:
            raise Ungradable("btts needs a probability")
        pick = "YES" if model_value >= 0.5 else "NO"
        both_scored = home_score > 0 and away_score > 0
        outcome = "win" if (both_scored == (pick == "YES")) else "loss"

    else:
        raise Ungradable(
            f"market '{market}' is not gradable from the stored columns -- "
            f"model_value does not say which side the number belongs to"
        )

    # Settle at the price that was actually on the board when it can be found.
    # DEFAULT_ODDS is only a stand-in, and a unit record built on a stand-in
    # drifts from what the bets were really worth.
    odds = DEFAULT_ODDS
    try:
        raw = json.loads(row["raw_json"]) if row["raw_json"] else {}
    except (json.JSONDecodeError, TypeError):
        raw = {}
    if isinstance(raw, dict):
        recorded = raw.get("market_odds")
        if isinstance(recorded, dict):
            if market == "moneyline":
                side = "home_ml" if pick == "HOME" else "away_ml"
                value = recorded.get(side)
                if isinstance(value, (int, float)):
                    odds = float(value)
            else:
                value = recorded.get("total_price")
                if isinstance(value, (int, float)):
                    odds = float(value)
        for key in ("odds", "american_odds", "price"):
            if isinstance(raw.get(key), (int, float)):
                odds = float(raw[key])
                break

    profit = {"win": american_to_profit(odds), "loss": -1.0, "push": 0.0}[outcome]
    return outcome, pick, round(profit, 4)


def apply_result(conn: sqlite3.Connection, row: sqlite3.Row,
                 home_score: float, away_score: float, source: str) -> Optional[str]:
    """Grade one row and write it back. Returns the outcome, or None if skipped."""
    try:
        outcome, pick, profit = grade_row(row, home_score, away_score)
    except Ungradable as exc:
        conn.execute(
            "UPDATE predictions SET actual_home_score=?, actual_away_score=?, grade_note=? "
            "WHERE id=?",
            (home_score, away_score, f"ungradable: {exc}", row["id"]),
        )
        return None

    conn.execute(
        """UPDATE predictions
           SET result_outcome=?, profit_loss=?, pick=?, actual_home_score=?,
               actual_away_score=?, graded_at=?, grade_note=?
           WHERE id=?""",
        (outcome, profit, pick, home_score, away_score,
         _dt.datetime.now().isoformat(timespec="seconds"), f"source: {source}", row["id"]),
    )
    return outcome


# ==========================================================================
# RESULT SOURCES
# ==========================================================================

MLB_SCHEDULE = ("https://statsapi.mlb.com/api/v1/schedule"
                "?sportId=1&startDate={start}&endDate={end}")


def _get_json(url: str) -> Any:
    if _HAS_REQUESTS:
        response = requests.get(url, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT)
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code} from {url}")
        return response.json()
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def fetch_mlb_results(start: str, end: str) -> Dict[Tuple[str, str, str], Tuple[float, float]]:
    """(date, home, away) -> (home_score, away_score) for finished MLB games."""
    payload = _get_json(MLB_SCHEDULE.format(start=start, end=end))
    out: Dict[Tuple[str, str, str], Tuple[float, float]] = {}
    for day in payload.get("dates", []):
        date = day.get("date")
        for game in day.get("games", []):
            state = ((game.get("status") or {}).get("abstractGameState") or "").lower()
            if state != "final":
                continue
            teams = game.get("teams") or {}
            home, away = teams.get("home") or {}, teams.get("away") or {}
            home_name = ((home.get("team") or {}).get("name") or "").strip()
            away_name = ((away.get("team") or {}).get("name") or "").strip()
            if home.get("score") is None or away.get("score") is None:
                continue
            out[(date, normalise_team(home_name), normalise_team(away_name))] = (
                float(home["score"]), float(away["score"])
            )
    return out


AUTO_SOURCES = {
    "mlb": fetch_mlb_results,
    "baseball": fetch_mlb_results,   # rows logged as 'baseball' that are MLB games
}


# ==========================================================================
# COMMANDS
# ==========================================================================

def open_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise SystemExit(f"No database at {DB_PATH}. Run a prediction first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ungraded(conn: sqlite3.Connection, sport: Optional[str] = None,
             days: Optional[int] = None) -> List[sqlite3.Row]:
    query = "SELECT * FROM predictions WHERE result_outcome IS NULL"
    params: List[Any] = []
    if sport:
        query += " AND lower(sport) = ?"
        params.append(sport.lower())
    if days:
        cutoff = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
        query += " AND game_date >= ?"
        params.append(cutoff)
    query += " ORDER BY game_date DESC, id DESC"
    return list(conn.execute(query, params))


def cmd_pending(conn: sqlite3.Connection, sport: Optional[str], days: Optional[int]) -> int:
    rows = ungraded(conn, sport, days)
    if not rows:
        log("Nothing pending -- every prediction in range has a result.")
        return 0

    log(f"{len(rows)} prediction(s) awaiting a result:\n")
    log(f"  {'id':>4}  {'date':<11}{'sport':<11}{'matchup':<44}{'market':<11}{'tier'}")
    log("  " + "-" * 88)
    for row in rows[:40]:
        matchup = f"{row['home_team']} vs {row['away_team']}"
        log(f"  {row['id']:>4}  {str(row['game_date'] or '?'):<11}{row['sport']:<11}"
            f"{matchup[:42]:<44}{row['market_type']:<11}{tier_of(row['recommendation'])}")
    if len(rows) > 40:
        log(f"  ... and {len(rows) - 40} more")

    # One row per distinct game, so scores are entered once rather than per market.
    games: Dict[Tuple[str, str, str], Dict[str, str]] = {}
    for row in rows:
        key = (str(row["game_date"] or ""), row["home_team"], row["away_team"])
        games.setdefault(key, {
            "game_date": key[0], "sport": row["sport"],
            "home_team": key[1], "away_team": key[2],
            "home_score": "", "away_score": "",
        })
    with open(PENDING_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "game_date", "sport", "home_team", "away_team", "home_score", "away_score"])
        writer.writeheader()
        writer.writerows(games.values())

    log(f"\nWrote {len(games)} game(s) to {PENDING_CSV.name}.")
    log("Fill in the two score columns in Excel, save, then run:")
    log(f"    python grade_predictions.py --manual {PENDING_CSV.name} --report")
    return 0


def cmd_auto(conn: sqlite3.Connection, sport: Optional[str], days: int) -> int:
    rows = ungraded(conn, sport, days)
    if not rows:
        log("Nothing to grade.")
        return 0

    by_sport: Dict[str, List[sqlite3.Row]] = {}
    for row in rows:
        by_sport.setdefault((row["sport"] or "").lower(), []).append(row)

    graded = skipped = unmatched = 0
    for sport_key, sport_rows in sorted(by_sport.items()):
        fetcher = AUTO_SOURCES.get(sport_key)
        if fetcher is None:
            log(f"[skip] {sport_key}: no automatic results source wired up yet "
                f"({len(sport_rows)} pending). Use --pending then --manual.")
            skipped += len(sport_rows)
            continue

        dates = sorted({str(r["game_date"]) for r in sport_rows if r["game_date"]})
        if not dates:
            log(f"[skip] {sport_key}: no game dates recorded.")
            skipped += len(sport_rows)
            continue

        log(f"[{sport_key}] fetching results for {dates[0]} .. {dates[-1]} ...")
        try:
            results = fetcher(dates[0], dates[-1])
        except Exception as exc:  # noqa: BLE001
            log(f"[FAILED] {sport_key}: {type(exc).__name__}: {exc}")
            skipped += len(sport_rows)
            continue

        for row in sport_rows:
            key = (str(row["game_date"]), normalise_team(row["home_team"]),
                   normalise_team(row["away_team"]))
            scores = results.get(key)
            if scores is None:
                # Try the reversed orientation -- home/away is sometimes logged
                # the other way round from how the feed reports it.
                flipped = results.get((key[0], key[2], key[1]))
                if flipped is not None:
                    scores = (flipped[1], flipped[0])
            if scores is None:
                unmatched += 1
                continue
            outcome = apply_result(conn, row, scores[0], scores[1], f"{sport_key} feed")
            if outcome:
                graded += 1
                log(f"    #{row['id']:>4} {row['home_team']} vs {row['away_team']} "
                    f"({row['market_type']}) -> {outcome.upper()} "
                    f"[{scores[0]:.0f}-{scores[1]:.0f}]")
    conn.commit()

    log(f"\nGraded {graded}. Unmatched {unmatched}. Skipped {skipped} "
        f"(no automatic source or no date).")
    if unmatched:
        log("Unmatched usually means the game was on a different day than the "
            "prediction timestamp, or the team name is spelled differently.")
    return 0


def cmd_manual(conn: sqlite3.Connection, path: Path) -> int:
    if not path.exists():
        raise SystemExit(f"No such file: {path}")
    with open(path, newline="", encoding="utf-8-sig") as handle:
        entries = list(csv.DictReader(handle))

    lookup: Dict[Tuple[str, str], Tuple[float, float]] = {}
    incomplete = 0
    for entry in entries:
        try:
            home_score = float(entry["home_score"])
            away_score = float(entry["away_score"])
        except (KeyError, TypeError, ValueError):
            incomplete += 1
            continue
        lookup[(normalise_team(entry.get("home_team", "")),
                normalise_team(entry.get("away_team", "")))] = (home_score, away_score)

    if not lookup:
        raise SystemExit(f"{path.name} has no rows with both scores filled in.")

    graded = 0
    for row in ungraded(conn):
        key = (normalise_team(row["home_team"]), normalise_team(row["away_team"]))
        scores = lookup.get(key)
        if scores is None:
            flipped = lookup.get((key[1], key[0]))
            scores = (flipped[1], flipped[0]) if flipped else None
        if scores is None:
            continue
        outcome = apply_result(conn, row, scores[0], scores[1], f"manual:{path.name}")
        if outcome:
            graded += 1
            log(f"  #{row['id']:>4} {row['home_team']} vs {row['away_team']} "
                f"({row['market_type']}) -> {outcome.upper()}")
    conn.commit()
    log(f"\nGraded {graded} prediction(s) from {path.name}."
        + (f" {incomplete} row(s) had no scores yet." if incomplete else ""))
    return 0


# ==========================================================================
# REPORTING
# ==========================================================================

def _bucket(confidence: Optional[float]) -> str:
    if confidence is None:
        return "unknown"
    if confidence >= 75:
        return "75+"
    if confidence >= 65:
        return "65-74"
    if confidence >= 55:
        return "55-64"
    return "<55"


def _tally(rows: Sequence[sqlite3.Row]) -> Dict[str, Any]:
    wins = sum(1 for r in rows if r["result_outcome"] == "win")
    losses = sum(1 for r in rows if r["result_outcome"] == "loss")
    pushes = sum(1 for r in rows if r["result_outcome"] == "push")
    decided = wins + losses
    units = sum((r["profit_loss"] or 0.0) for r in rows)
    return {
        "n": len(rows), "wins": wins, "losses": losses, "pushes": pushes,
        "win_pct": (wins / decided * 100.0) if decided else None,
        "units": units,
        "roi": (units / decided * 100.0) if decided else None,
    }


def _line(label: str, stats: Dict[str, Any]) -> str:
    win_pct = f"{stats['win_pct']:.1f}%" if stats["win_pct"] is not None else "   -  "
    roi = f"{stats['roi']:+.1f}%" if stats["roi"] is not None else "   -  "
    record = f"{stats['wins']}-{stats['losses']}" + (f"-{stats['pushes']}" if stats["pushes"] else "")
    return f"  {label:<26}{record:<12}{win_pct:>8}{stats['units']:>10.2f}u{roi:>10}"


def cmd_report(conn: sqlite3.Connection, sport: Optional[str], days: Optional[int],
               push_discord: bool) -> int:
    query = "SELECT * FROM predictions WHERE result_outcome IS NOT NULL"
    params: List[Any] = []
    if sport:
        query += " AND lower(sport) = ?"
        params.append(sport.lower())
    if days:
        query += " AND game_date >= ?"
        params.append((_dt.date.today() - _dt.timedelta(days=days)).isoformat())
    rows = list(conn.execute(query, params))

    total_logged = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    if not rows:
        log(f"No graded predictions yet ({total_logged} logged in total).")
        log("Start with:  python grade_predictions.py --auto")
        log("          or python grade_predictions.py --pending")
        return 0

    header = f"  {'':<26}{'W-L':<12}{'WIN%':>8}{'UNITS':>11}{'ROI':>10}"
    log("=" * 78)
    log(f"PREDICTION RECORD   ({len(rows)} graded of {total_logged} logged"
        + (f", last {days} days" if days else "") + ")")
    log("=" * 78)

    bets = [r for r in rows if tier_of(r["recommendation"]) in {"STRONG BET", "BET"}]
    log("\nACTUAL BETS (STRONG BET + BET only -- this is the record that matters)")
    log(header)
    log(_line("all bets", _tally(bets)) if bets else "  (none yet)")
    for tier in ("STRONG BET", "BET"):
        subset = [r for r in bets if tier_of(r["recommendation"]) == tier]
        if subset:
            log(_line(f"  {tier.lower()}", _tally(subset)))

    log("\nBY SPORT")
    log(header)
    for name in sorted({(r["sport"] or "?") for r in rows}):
        log(_line(name, _tally([r for r in rows if r["sport"] == name])))

    log("\nBY MARKET")
    log(header)
    for market in sorted({(r["market_type"] or "?") for r in rows}):
        log(_line(market, _tally([r for r in rows if r["market_type"] == market])))

    log("\nBY CONFIDENCE  (is a higher score actually more reliable?)")
    log(header)
    for bucket in ("75+", "65-74", "55-64", "<55", "unknown"):
        subset = [r for r in rows if _bucket(r["confidence"]) == bucket]
        if subset:
            log(_line(bucket, _tally(subset)))

    informational = [r for r in rows if tier_of(r["recommendation"]) == "INFO"]
    passes = [r for r in rows if tier_of(r["recommendation"]) == "PASS"]
    if passes or informational:
        log("\nNOT BETS  (model calibration only -- no money was risked on these)")
        log(header)
        if passes:
            log(_line("passes", _tally(passes)))
        if informational:
            log(_line("informational", _tally(informational)))

    overall = _tally(bets)
    if overall["win_pct"] is not None:
        log("\n" + "-" * 78)
        breakeven = 100.0 / (1.0 + american_to_profit(DEFAULT_ODDS))
        verdict = "above" if overall["win_pct"] > breakeven else "below"
        log(f"  Break-even at {DEFAULT_ODDS:.0f} is {breakeven:.1f}%. "
            f"You are {verdict} it on {overall['wins'] + overall['losses']} decided bets.")
        if overall["wins"] + overall["losses"] < 30:
            log("  Sample is small -- under about 30 settled bets this number moves a lot.")
    priced = 0
    for row in rows:
        try:
            blob = json.loads(row["raw_json"]) if row["raw_json"] else {}
            if isinstance(blob, dict) and isinstance(blob.get("market_odds"), dict):
                priced += 1
        except (json.JSONDecodeError, TypeError):
            pass
    if priced:
        log(f"  {priced} of {len(rows)} graded row(s) settled at recorded prices; "
            f"the rest assumed {DEFAULT_ODDS:.0f}.")
    log("=" * 78)

    if push_discord:
        _push_record_to_discord(rows, bets, days)
    return 0


def _push_record_to_discord(rows: Sequence[sqlite3.Row], bets: Sequence[sqlite3.Row],
                            days: Optional[int]) -> None:
    webhook = os.getenv("DISCORD_RESULTS_WEBHOOK_URL") or os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        log("\n[discord] DISCORD_WEBHOOK_URL is not set -- record not posted.")
        return
    if not _HAS_REQUESTS:
        log("\n[discord] requests is not installed -- record not posted.")
        return

    overall = _tally(bets)
    fields = []
    for name in sorted({(r["sport"] or "?") for r in rows}):
        stats = _tally([r for r in rows if r["sport"] == name])
        if stats["win_pct"] is None:
            continue
        fields.append({
            "name": name.upper(),
            "value": f"{stats['wins']}-{stats['losses']} ({stats['win_pct']:.1f}%) "
                     f"| {stats['units']:+.2f}u",
            "inline": True,
        })

    win_pct = f"{overall['win_pct']:.1f}%" if overall["win_pct"] is not None else "n/a"
    embed = {
        "title": "Prediction Record",
        "description": (f"**{overall['wins']}-{overall['losses']}** on graded bets "
                        f"({win_pct}) | **{overall['units']:+.2f} units**"
                        + (f"\nLast {days} days" if days else "\nAll time")),
        "color": 3066993 if (overall["units"] or 0) >= 0 else 15158332,
        "fields": fields[:24],
        "footer": {"text": "MultiSportPredict | graded results only"},
        "timestamp": _dt.datetime.utcnow().isoformat(),
    }
    try:
        response = requests.post(webhook, json={"embeds": [embed]}, timeout=20)
        ok = response.status_code in (200, 204)
        log(f"\n[discord] record {'posted' if ok else f'failed ({response.status_code})'}")
    except Exception as exc:  # noqa: BLE001
        log(f"\n[discord] post failed: {type(exc).__name__}: {exc}")


# ==========================================================================
# MAIN
# ==========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grade logged predictions against real results and report the record.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Daily use after games finish:  python grade_predictions.py --auto --report",
    )
    parser.add_argument("--auto", action="store_true",
                        help="Fetch final scores and grade (MLB wired up today).")
    parser.add_argument("--manual", type=Path, metavar="CSV",
                        help="Grade from a CSV of final scores.")
    parser.add_argument("--pending", action="store_true",
                        help="List ungraded predictions and write pending_results.csv.")
    parser.add_argument("--report", action="store_true", help="Print the win-rate record.")
    parser.add_argument("--push-discord", action="store_true",
                        help="Post the record to Discord (uses DISCORD_RESULTS_WEBHOOK_URL, "
                             "falling back to DISCORD_WEBHOOK_URL).")
    parser.add_argument("--sport", default=None, help="Limit to one sport.")
    parser.add_argument("--days", type=int, default=None,
                        help="Limit to the last N days (auto-grading defaults to 14).")
    args = parser.parse_args()

    if not any((args.auto, args.manual, args.pending, args.report)):
        parser.error("Pick at least one of --auto, --manual, --pending, --report.")

    conn = open_db()
    added = ensure_schema(conn)
    if added:
        log(f"[schema] added column(s): {', '.join(added)}\n")

    try:
        if args.pending:
            cmd_pending(conn, args.sport, args.days)
        if args.auto:
            cmd_auto(conn, args.sport, args.days or 14)
        if args.manual:
            cmd_manual(conn, args.manual)
        if args.report:
            if args.auto or args.manual:
                log("")
            cmd_report(conn, args.sport, args.days, args.push_discord)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
