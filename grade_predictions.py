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

PROFIT/LOSS uses the price that was actually on the board when one is recorded
in raw_json["market_odds"] (moneyline rows carry home_ml/away_ml today). A
bet with no recorded price -- every total row, because only the LINE is
stored, never a total price -- settles at the -110 convention (risk 1 to win
0.909) and is noted in grade_note as such. That is a modelling convention,
not a claim about what you were actually priced at -- treat the unit record
as directional.

PASS and INFO rows are NOT graded or counted. PASS is the model declining to
bet; INFO is a legacy recommendation string that names no side ('Over: 55.9% |
Under: 44.1%') and was never settleable in the first place. Both stay in the
database as calibration data (grade_note says why) but never appear in the
win/loss record. Duplicate fixtures -- the same (date, sport, teams, market)
seen twice, in either home/away orientation or from a slate re-run -- collapse
to their newest row; the older one is set aside with a note.

    python grade_predictions.py --regrade   un-grade PASS/INFO + re-settle
                                            existing grades at recorded prices
    python grade_predictions.py --report    the honest record
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import math
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

    Every sport in this project phrases a recommendation differently:
    soccer's plain "BET"/"PASS", tennis's "BET Home ML (edge: +11.3%)" and
    "SLIGHT LEAN Home ML (edge: +3.5%)", MLB's "LEAN St. Louis Cardinals ML
    (edge: +6.9%)", NFL's "BET HOME"/"BET AWAY", and baseball/NFL totals'
    bare "OVER"/"UNDER". This function used to only recognize soccer's exact
    strings via `== "BET"` -- every tennis and MLB moneyline recommendation,
    real bets included, silently fell through to "INFO". Any report built on
    this helper (win rate by tier, --pending's tier column) was undercounting
    real bets the whole time it existed. Matches on the BET/LEAN keyword
    itself now, wherever it sits in the string, so the sport-specific
    wrapping around it doesn't matter. Raw percentage readouts (the pre-fix
    baseball total bug -- "Over: 44.5% | Under: 55.5%") still correctly fall
    through to INFO: they don't contain the word BET or LEAN, which is
    exactly why they were ungradable-as-a-decision in the first place.
    """
    text = (recommendation or "").strip().upper()
    if not text:
        return "INFO"
    if text.startswith("STRONG BET") or " STRONG BET" in text:
        return "STRONG BET"
    if "NO BET" not in text and re.search(r"\bBET\b", text):
        return "BET"
    if re.search(r"\bLEAN\b", text):
        return "LEAN"
    if text in {"PASS", "NO BET"} or text.startswith("PASS "):
        return "PASS"
    if text in {"OVER", "UNDER"}:
        return "BET"  # a real directional pick; this sport's convention just has no BET/LEAN prefix
    return "INFO"


def normalise_team(name: str) -> str:
    # Strip a trailing season tag first. run_nfl.py stores "Arizona Cardinals
    # (2026)"; ESPN returns "Arizona Cardinals". Without this the tag survived
    # as "arizonacardinals2026", no NFL row could ever match a result, and all
    # 39 stored NFL predictions sat ungraded looking like "finals not in yet".
    name = DEDUP_TEAM_NOISE.sub("", name or "")
    return re.sub(r"[^a-z0-9]", "", name.lower())


DEDUP_TEAM_NOISE = re.compile(r"\s*\((?:19|20)\d{2}(?:[-/]\d{2,4})?\)\s*$")


def dedup_key(row: sqlite3.Row) -> Tuple[str, str, str, str]:
    """(date, sport, {teams} sorted, market) -- the identity of 'one bet'.

    The teams are an unordered pair, so 'A vs B' and 'B vs A' (both recorded
    orientations of the same fixture have been seen) collapse to one key. The
    season tag is stripped: NFL rows may store 'Buffalo Bills (2026)' one day
    and 'Buffalo Bills' the next, and the report must treat them as one team.

    NOTE: `game_date` belongs in the key because the same two clubs meet again
    and again (Lotte and KIA faced off three times inside one week in Aug
    2026). A matchup-pair-only key would settle every one of those meetings at
    a single night's score -- that is a fabricated result, not a grade.
    """
    def strip_season(name: str) -> str:
        return normalise_team(DEDUP_TEAM_NOISE.sub("", name or ""))

    home, away = strip_season(row["home_team"]), strip_season(row["away_team"])
    pair = f"{home}|{away}" if home <= away else f"{away}|{home}"
    return (
        str(row["game_date"] or ""),
        (row["sport"] or "").strip().lower(),
        pair,
        (row["market_type"] or "").strip().lower(),
    )


def is_excluded_tier(recommendation: Optional[str]) -> bool:
    """PASS and INFO rows are not bets: don't grade, don't count.

    PASS is the model declining to bet. INFO is a recommendation string that
    names no side ('Over: 55.9% | Under: 44.1%') -- it was never settleable,
    and tier_of() has classified it as INFO all along; grading ignored that.
    Both stay in the database as calibration data, but neither can be part of
    a betting record.
    """
    return tier_of(recommendation) in {"PASS", "INFO"}


def newest_per_fixture(rows: Sequence[sqlite3.Row]
                      ) -> Tuple[List[sqlite3.Row], List[sqlite3.Row]]:
    """Split rows into (kept, dropped) keeping the HIGHEST id per dedup key.

    'A vs B' and 'B vs A' orientations of the same game, re-runs of a slate,
    and one fixture with a second prediction after a line move are all the
    same bet -- the identities collapse under dedup_key(). The newest row (by
    id; ids are monotonic) is kept because a re-run of a slate produces a
    later row with the fresher line, so that is the one that reflects what
    would actually have been bet. Deterministic either way; newest chosen on
    that principle.
    """
    kept: Dict[str, sqlite3.Row] = {}
    order: List[str] = []
    for row in rows:
        key = dedup_key(row)
        existing = kept.get(key)
        if existing is None or row["id"] > existing["id"]:
            if existing is None:
                order.append(key)
            kept[key] = row
    kept_rows = [kept[key] for key in order]
    dropped_ids = {row["id"] for row in rows} - {row["id"] for row in kept_rows}
    dropped = [row for row in rows if row["id"] in dropped_ids]
    return kept_rows, dropped


def american_to_profit(odds: float) -> float:
    """Profit on a 1-unit win at American odds."""
    return (100.0 / abs(odds)) if odds < 0 else (odds / 100.0)


# ==========================================================================
# GRADING
# ==========================================================================

class Ungradable(Exception):
    pass


def _price(value: Any) -> Optional[float]:
    """An American price, or None. 0 and non-numbers are not prices."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v != 0 and math.isfinite(v) else None


def _recorded_prices(raw: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Every real price stored with a prediction, under one set of names.

    Standard location (written by universal_runner._store_prediction since
    2026-09-21): raw_json["market_odds"] with home_ml, away_ml, draw_ml,
    over, under, spread_home_price, spread_away_price.
    Older rows are read from where each runner used to put them:
      run_mlb.py    market_odds.home_ml / away_ml
      run_tennis.py auto_odds.home_ml / away_ml
      soccer        auto_odds.over_price / under_price / home_ml / away_ml
      moneyline     moneyline.market_home / market_away
    """
    out: Dict[str, Optional[float]] = {k: None for k in (
        "home_ml", "away_ml", "draw_ml", "over", "under",
        "spread_home_price", "spread_away_price")}
    sources = []
    for key in ("market_odds", "auto_odds"):
        if isinstance(raw.get(key), dict):
            sources.append(raw[key])
    ml = raw.get("moneyline")
    if isinstance(ml, dict):
        sources.append({"home_ml": ml.get("market_home") or ml.get("home_ml"),
                        "away_ml": ml.get("market_away") or ml.get("away_ml")})
    aliases = {"over": ("over", "over_price"), "under": ("under", "under_price")}
    for name in out:
        for src in sources:
            for k in aliases.get(name, (name,)):
                v = _price(src.get(k))
                if v is not None and out[name] is None:
                    out[name] = v
    return out


def _side_bet(row: sqlite3.Row, raw: Dict[str, Any]) -> Optional[str]:
    """HOME or AWAY as the recommendation actually said, or None.

    The moneyline side used to be taken from the win probability
    (>= 0.5 -> HOME). A value bet on an underdog -- "BET HOME ML" at a 35%
    home win probability -- was therefore settled as a bet on AWAY. Two tennis
    bets that lost were recorded as wins that way. The recommendation is what
    was bet; read it first.
    """
    text = str(row["recommendation"] or "").upper()
    if re.search(r"\bAWAY\b", text):
        return "AWAY"
    if re.search(r"\bHOME\b", text):
        return "HOME"
    squashed = normalise_team(text)
    home, away = normalise_team(row["home_team"]), normalise_team(row["away_team"])
    if home and home in squashed and not (away and away in squashed):
        return "HOME"
    if away and away in squashed and not (home and home in squashed):
        return "AWAY"
    stored = str(raw.get("_pick") or "").upper()
    if stored in ("HOME", "AWAY"):
        return stored
    return None


def grade_row(row: sqlite3.Row, home_score: float, away_score: float) -> Tuple[str, str, float, bool]:
    """Return (outcome, pick, profit_loss, priced) for one prediction.

    outcome is 'win' | 'loss' | 'push'. `priced` is True when the bet was
    settled at a real recorded price rather than the DEFAULT_ODDS convention.
    """
    market = (row["market_type"] or "").strip().lower()
    model_value = row["model_value"]
    market_value = row["market_value"]
    sport = (row["sport"] or "").strip().lower()
    total = home_score + away_score
    try:
        raw = json.loads(row["raw_json"]) if row["raw_json"] else {}
    except (json.JSONDecodeError, TypeError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    prices = _recorded_prices(raw)
    price_key: Optional[str] = None

    if market == "total":
        if model_value is None or market_value is None:
            raise Ungradable("total needs both a projection and a market line")
        text = str(row["recommendation"] or "").upper()
        if re.search(r"\bUNDER\b", text):
            pick = "UNDER"
        elif re.search(r"\bOVER\b", text):
            pick = "OVER"
        else:
            pick = "OVER" if model_value > market_value else "UNDER"
        if abs(total - market_value) < 1e-9:
            outcome = "push"
        elif (total > market_value) == (pick == "OVER"):
            outcome = "win"
        else:
            outcome = "loss"
        price_key = "over" if pick == "OVER" else "under"

    elif market == "moneyline":
        if model_value is None:
            raise Ungradable("moneyline needs a home win probability")
        pick = _side_bet(row, raw) or ("HOME" if model_value >= 0.5 else "AWAY")
        if home_score > away_score:
            winner = "HOME"
        elif away_score > home_score:
            winner = "AWAY"
        else:
            # Soccer settles a draw as a loss on a two-way price; the other
            # sports here cannot draw, so a tie means the data is wrong.
            if sport in {"soccer", "football"}:
                return "loss", pick, -1.0, True
            raise Ungradable(f"tie score in {sport}, which should not happen")
        outcome = "win" if pick == winner else "loss"
        price_key = "home_ml" if pick == "HOME" else "away_ml"

    elif market == "spread":
        # The line is not in a column: market_value holds 0.5 and model_value
        # the cover probability. It lives in raw_json["spread"], signed from
        # the home side (+2.5 = home gets 2.5). Every NFL spread bet was
        # ungradable until this branch existed.
        spread = raw.get("spread") if isinstance(raw.get("spread"), dict) else {}
        line = spread.get("market_spread")
        if line is None:
            raise Ungradable("spread line not recorded in raw_json['spread']")
        pick = (_side_bet(row, raw)
                or str(spread.get("pick") or "").upper() or None)
        if pick not in ("HOME", "AWAY"):
            raise Ungradable("spread bet does not say which side")
        cover = (home_score - away_score) + float(line)
        if abs(cover) < 1e-9:
            outcome = "push"
        else:
            outcome = "win" if (cover > 0) == (pick == "HOME") else "loss"
        price_key = "spread_home_price" if pick == "HOME" else "spread_away_price"

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

    odds = DEFAULT_ODDS
    priced = False
    if price_key and prices.get(price_key) is not None:
        odds = prices[price_key]
        priced = True
    for key in ("odds", "american_odds", "price"):      # legacy single-price rows
        if not priced and _price(raw.get(key)) is not None:
            odds = _price(raw[key])
            priced = True

    profit = {"win": american_to_profit(odds), "loss": -1.0, "push": 0.0}[outcome]
    return outcome, pick, round(profit, 4), priced


def apply_result(conn: sqlite3.Connection, row: sqlite3.Row,
                 home_score: float, away_score: float, source: str) -> Optional[str]:
    """Grade one row and write it back. Returns the outcome, or None if skipped.

    Rows whose recommendation is PASS or INFO are deliberately NOT graded: they
    are not bets. They keep their identity in the database (calibration data)
    but get a grade_note explaining why they were excluded rather than a score
    that would fake a settled bet.
    """
    if is_excluded_tier(row["recommendation"]):
        conn.execute(
            "UPDATE predictions SET result_outcome=NULL, profit_loss=NULL, "
            "actual_home_score=?, actual_away_score=?, graded_at=NULL, grade_note=? "
            "WHERE id=?",
            (home_score, away_score,
             f"excluded: {tier_of(row['recommendation'])} row is not a bet "
             f"(source: {source})", row["id"]),
        )
        return None

    try:
        outcome, pick, profit, priced = grade_row(row, home_score, away_score)
    except Ungradable as exc:
        conn.execute(
            "UPDATE predictions SET actual_home_score=?, actual_away_score=?, grade_note=? "
            "WHERE id=?",
            (home_score, away_score, f"ungradable: {exc}", row["id"]),
        )
        return None

    note = f"source: {source}"
    if not priced:
        note += f"; settled at default {DEFAULT_ODDS:.0f} (no real price recorded)"
    # Record the settlement price so the report counts truly-priced rows rather
    # than re-inferring it from raw_json["market_odds"] presence.
    try:
        raw = json.loads(row["raw_json"]) if row["raw_json"] else {}
    except (json.JSONDecodeError, TypeError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    raw["_settled_at_recorded_price"] = bool(priced)
    conn.execute(
        """UPDATE predictions
           SET result_outcome=?, profit_loss=?, pick=?, actual_home_score=?,
               actual_away_score=?, graded_at=?, grade_note=?, raw_json=?
           WHERE id=?""",
        (outcome, profit, pick, home_score, away_score,
         _dt.datetime.now().isoformat(timespec="seconds"), note, json.dumps(raw),
         row["id"]),
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


# One day per request. The old single range request (dates=START-END) failed
# with RuntimeError on every run, so the live feed never graded anything and
# only the nfl_schedule.json fallback worked. The per-day form is the one the
# NCAAF grader already uses successfully.
NFL_SCOREBOARD = ("https://site.web.api.espn.com/apis/site/v2/sports/football/"
                  "nfl/scoreboard?dates={date}&limit=400")


def fetch_nfl_results(start: str, end: str) -> Dict[Tuple[str, str, str], Tuple[float, float]]:
    """(date, home, away) -> (home_score, away_score) for finished NFL games.

    Reads ESPN's scoreboard, and falls back to data/nfl_schedule.json for any
    date the feed does not answer for -- the ingest already stores every final
    score, so a network hiccup does not have to leave a week ungraded.

    Home and away come from the explicit "homeAway" field, never from position
    in the array. Getting that backwards grades a bet as a win when it lost.

    Note site.WEB.api: site.api.espn.com (no "web") is Akamai-blocked here.
    """
    out: Dict[Tuple[str, str, str], Tuple[float, float]] = {}

    def add(date: str, home: str, away: str, hs: Any, ras: Any) -> None:
        if not (date and home and away) or hs is None or ras is None:
            return
        out[(date[:10], normalise_team(home), normalise_team(away))] = (
            float(hs), float(ras))

    failures: List[str] = []
    day = _dt.date.fromisoformat(start)
    last = _dt.date.fromisoformat(end)
    while day <= last:
        try:
            payload = _get_json(NFL_SCOREBOARD.format(date=day.strftime("%Y%m%d")))
            events = payload.get("events") or []
            for league in payload.get("leagues") or []:
                events = events or (league.get("events") or [])
            for event in events:
                competitions = event.get("competitions") or []
                if not competitions:
                    continue
                competition = competitions[0]
                status = ((competition.get("status") or {}).get("type") or {})
                if not status.get("completed"):
                    continue
                sides = {}
                for competitor in competition.get("competitors") or []:
                    which = str(competitor.get("homeAway", "")).lower()
                    if which in ("home", "away"):
                        team = competitor.get("team") or {}
                        sides[which] = (team.get("displayName") or team.get("name"),
                                        competitor.get("score"))
                if "home" in sides and "away" in sides:
                    # Key on the US date asked for, not event["date"]. That
                    # field is UTC, so every Sunday and Monday night game
                    # (8:15pm ET = 00:15Z next day) was filed under the wrong
                    # date and could never match its prediction.
                    add(day.isoformat(), sides["home"][0], sides["away"][0],
                        sides["home"][1], sides["away"][1])
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{day}: {exc}")
        day += _dt.timedelta(days=1)
    if failures:
        # Say what failed instead of a bare class name.
        log(f"[nfl] live scoreboard failed for {len(failures)} day(s), first: "
            f"{failures[0]} -- using data/nfl_schedule.json for those")

    schedule_path = ROOT / "data" / "nfl_schedule.json"
    if schedule_path.exists():
        try:
            stored = json.loads(schedule_path.read_text(encoding="utf-8-sig"))
            for game in stored.get("games", []):
                if not game.get("completed"):
                    continue
                if not (start <= str(game.get("date", "")) <= end):
                    continue
                key = (str(game["date"])[:10],
                       normalise_team(game["home_team"]),
                       normalise_team(game["away_team"]))
                if key not in out:      # the live feed wins where both have it
                    add(game["date"], game["home_team"], game["away_team"],
                        game.get("home_score"), game.get("away_score"))
        except (json.JSONDecodeError, KeyError) as exc:
            log(f"[nfl] could not read nfl_schedule.json: {exc}")

    return out


TENNIS_SCOREBOARD = "https://site.web.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard?dates={date}"


def fetch_tennis_results(start: str, end: str) -> Dict[Tuple[str, str, str], Tuple[float, float]]:
    """(date, home, away) -> (1.0, 0.0) if home won, (0.0, 1.0) if away won.

    There is no "score" for a tennis match the way there's a run/goal total,
    so a straight win/loss is encoded as (1,0)/(0,1) -- grade_row()'s generic
    moneyline branch only ever compares which side is larger, so this slots
    into the exact same grading path MLB/NFL/NCAAF use, no tennis-specific
    code needed there.

    ESPN's stored names are full names ("Roberto Carballes Baena"); this
    project's tennis store and every stored prediction use the surname/
    initial key run_tennis.py's own resolver produces ("Carballes Baena R.").
    Those two spellings don't line up under a plain squash the way two
    spellings of a team name usually do, so each ESPN competitor name is
    resolved against the SAME player store and the SAME resolver run_tennis.py
    uses for typed CLI input -- treating ESPN's name as if a person had typed
    it. An ambiguous or unresolved name is skipped, not guessed, consistent
    with every other resolver in this project.
    """
    out: Dict[Tuple[str, str, str], Tuple[float, float]] = {}

    from run_tennis import resolve as resolve_player, STORE as PLAYER_STORE_PATH
    try:
        player_store = json.loads(PLAYER_STORE_PATH.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        player_store = {}

    def resolved(name: str) -> Optional[str]:
        # resolve_player already returns (None, "ambiguous: ...") or
        # (None, "no match") for anything it won't commit to -- nothing extra
        # to check here, just pass the key through.
        key, _how = resolve_player(name, player_store)
        return key

    try:
        start_date = _dt.date.fromisoformat(start)
        end_date = _dt.date.fromisoformat(end)
    except ValueError:
        log(f"[tennis] could not parse date range {start}..{end}")
        return out

    day = start_date
    while day <= end_date:
        for tour in ("atp", "wta"):
            try:
                payload = _get_json(TENNIS_SCOREBOARD.format(tour=tour, date=day.strftime("%Y%m%d")))
            except Exception as exc:  # noqa: BLE001
                log(f"[tennis] {tour} {day.isoformat()} unavailable ({type(exc).__name__})")
                continue
            for event in payload.get("events") or []:
                for grouping in event.get("groupings") or []:
                    slug = ((grouping.get("grouping") or {}).get("slug") or "")
                    if "singles" not in slug:
                        continue
                    for competition in grouping.get("competitions") or []:
                        status = ((competition.get("status") or {}).get("type") or {})
                        if not status.get("completed"):
                            continue
                        competitors = competition.get("competitors") or []
                        if len(competitors) != 2:
                            continue
                        sides = {}
                        for competitor in competitors:
                            which = str(competitor.get("homeAway", "")).lower()
                            if which not in ("home", "away"):
                                continue
                            full_name = ((competitor.get("athlete") or {}).get("fullName")
                                        or (competitor.get("athlete") or {}).get("displayName"))
                            sides[which] = (full_name, bool(competitor.get("winner")))
                        if "home" not in sides or "away" not in sides:
                            continue
                        home_name, home_won = sides["home"]
                        away_name, away_won = sides["away"]
                        if not home_name or not away_name or home_won == away_won:
                            continue  # need a real name on both sides and exactly one winner
                        home_key = resolved(home_name)
                        away_key = resolved(away_name)
                        if not home_key or not away_key:
                            continue
                        out[(day.isoformat(), normalise_team(home_key), normalise_team(away_key))] = (
                            (1.0, 0.0) if home_won else (0.0, 1.0))
        day += _dt.timedelta(days=1)

    return out


NCAAF_SCOREBOARD = ("https://site.web.api.espn.com/apis/site/v2/sports/football/"
                    "college-football/scoreboard?dates={date}&groups=80&limit=400")


def fetch_ncaaf_results(start: str, end: str) -> Dict[Tuple[str, str, str], Tuple[float, float]]:
    """(date, home, away) -> (home_score, away_score) for finished FBS games.

    FBS only (ESPN groups=80) -- see ingest_ncaaf.py for why. Unlike
    fetch_nfl_results, this queries one date at a time: a date-RANGE query
    against this endpoint (dates=START-END) silently returns an incomplete
    set (confirmed: 68 of 71 known games for a 2-day span), where the NFL
    scoreboard's range query does not have that problem. Falls back to
    data/ncaaf_schedule.json (written by ingest_ncaaf.py) for any date the
    live feed does not answer for, same pattern as the NFL fetcher.
    """
    out: Dict[Tuple[str, str, str], Tuple[float, float]] = {}

    def add(date: str, home: str, away: str, hs: Any, ras: Any) -> None:
        if not (date and home and away) or hs is None or ras is None:
            return
        out[(date[:10], normalise_team(home), normalise_team(away))] = (
            float(hs), float(ras))

    try:
        start_date = _dt.date.fromisoformat(start)
        end_date = _dt.date.fromisoformat(end)
        day = start_date
        while day <= end_date:
            try:
                payload = _get_json(NCAAF_SCOREBOARD.format(date=day.strftime("%Y%m%d")))
                events = payload.get("events") or []
                for league in payload.get("leagues") or []:
                    events = events or (league.get("events") or [])
                for event in events:
                    competitions = event.get("competitions") or []
                    if not competitions:
                        continue
                    competition = competitions[0]
                    status = ((competition.get("status") or {}).get("type") or {})
                    if not status.get("completed"):
                        continue
                    sides = {}
                    for competitor in competition.get("competitors") or []:
                        which = str(competitor.get("homeAway", "")).lower()
                        if which in ("home", "away"):
                            team = competitor.get("team") or {}
                            sides[which] = (team.get("displayName") or team.get("name"),
                                            competitor.get("score"))
                    if "home" in sides and "away" in sides:
                        # Key by the queried calendar date, NOT event["date"]
                        # (ESPN's raw UTC timestamp) -- a Friday-night US game
                        # can carry a UTC date one day later, which stored the
                        # same completed game under two different date keys
                        # here (confirmed: 71 real games, 85 with duplicates,
                        # 14 late-night games double-counted) once merged with
                        # ingest_ncaaf.py's file, which keys by query date.
                        add(day.isoformat(), sides["home"][0], sides["away"][0],
                            sides["home"][1], sides["away"][1])
            except Exception as exc:  # noqa: BLE001
                log(f"[ncaaf] {day.isoformat()} unavailable ({type(exc).__name__})")
            day += _dt.timedelta(days=1)
    except ValueError:
        log(f"[ncaaf] could not parse date range {start}..{end}")

    schedule_path = ROOT / "data" / "ncaaf_schedule.json"
    if schedule_path.exists():
        try:
            stored = json.loads(schedule_path.read_text(encoding="utf-8-sig"))
            for game in stored.get("games", []):
                if not game.get("completed"):
                    continue
                if not (start <= str(game.get("date", "")) <= end):
                    continue
                key = (str(game["date"])[:10],
                       normalise_team(game["home_team"]),
                       normalise_team(game["away_team"]))
                if key not in out:      # the live feed wins where both have it
                    add(game["date"], game["home_team"], game["away_team"],
                        game.get("home_score"), game.get("away_score"))
        except (json.JSONDecodeError, KeyError) as exc:
            log(f"[ncaaf] could not read ncaaf_schedule.json: {exc}")

    return out


# --------------------------------------------------------------------------
# SOCCER
# --------------------------------------------------------------------------
# Stored soccer rows have no league (league was never written until 09-21), so
# this grader is league-agnostic: for each date a prediction was made it reads
# ESPN's cross-league scoreboard, then each league slug it knows, and matches
# on the team pair. Only the dates that have pending rows are fetched.
#
# Soccer markets settle on 90 minutes. ESPN's score for a cup tie that went to
# extra time includes the extra goals, so AET/penalty finishes are NOT graded;
# they stay pending with a note rather than settle on the wrong score.
SOCCER_SCOREBOARD = ("https://site.web.api.espn.com/apis/site/v2/sports/soccer/"
                     "{slug}/scoreboard?dates={date}&limit=500")
SOCCER_EXTRA_SLUGS = [
    "fifa.world", "fifa.friendly", "fifa.worldq.uefa", "fifa.worldq.conmebol",
    "fifa.worldq.concacaf", "fifa.worldq.caf", "fifa.worldq.afc",
    "uefa.europa", "uefa.europa.conf", "uefa.nations", "concacaf.leagues.cup",
    "concacaf.champions", "conmebol.libertadores", "conmebol.sudamericana",
    "eng.2", "esp.2", "ger.2", "ita.2", "fra.2", "por.1", "sco.1", "bel.1",
    "tur.1", "gre.1", "den.1", "den.2", "rou.1", "geo.1", "uru.1", "mar.1",
    "jpn.1", "chn.1", "aus.1", "col.1", "chi.1",
]
AET_MARKERS = ("AET", "PEN", "EXTRA", "SHOOTOUT")


def _soccer_slugs() -> List[str]:
    slugs: List[str] = []
    try:
        from ingest_soccer_espn import LEAGUES as _L
        slugs = [cfg["slug"] for cfg in _L.values() if cfg.get("slug")]
    except Exception:  # noqa: BLE001  (ingest module needs requests; grader does not)
        pass
    for slug in SOCCER_EXTRA_SLUGS:
        if slug not in slugs:
            slugs.append(slug)
    return slugs


def _soccer_events(payload: Any) -> List[Tuple[str, str, Any, Any, bool]]:
    """(home, away, home_score, away_score, settled_in_90) for finished games."""
    out = []
    events = payload.get("events") or []
    for event in events:
        comps = event.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        stype = ((comp.get("status") or event.get("status") or {}).get("type") or {})
        if not stype.get("completed"):
            continue
        label = " ".join(str(stype.get(k) or "") for k in ("name", "detail", "shortDetail")).upper()
        in_90 = not any(m in label for m in AET_MARKERS)
        sides = {}
        for c in comp.get("competitors") or []:
            which = str(c.get("homeAway", "")).lower()
            if which in ("home", "away"):
                team = c.get("team") or {}
                sides[which] = (team.get("displayName") or team.get("name") or "",
                                c.get("score"))
        if "home" in sides and "away" in sides:
            out.append((sides["home"][0], sides["away"][0],
                        sides["home"][1], sides["away"][1], in_90))
    return out


def fetch_soccer_results(start: str, end: str,
                         dates: Optional[List[str]] = None
                         ) -> Dict[Tuple[str, str, str], Tuple[float, float]]:
    """(date, home, away) -> 90-minute score, for every date that has a pending row.

    A prediction's game_date comes from when it was run, and kickoffs cross UTC
    midnight, so each date also reads the next day's scoreboard and files what
    it finds under both dates.
    """
    wanted = sorted(set(dates or [])) or [start]
    out: Dict[Tuple[str, str, str], Tuple[float, float]] = {}
    extra_time: List[str] = []
    fetched: Dict[str, List[Tuple[str, str, Any, Any, bool]]] = {}
    failures: List[str] = []
    slugs = _soccer_slugs()

    def day_events(day: _dt.date) -> List[Tuple[str, str, Any, Any, bool]]:
        key = day.isoformat()
        if key in fetched:
            return fetched[key]
        found: Dict[Tuple[str, str], Tuple[str, str, Any, Any, bool]] = {}
        for slug in ["all"] + slugs:
            try:
                payload = _get_json(SOCCER_SCOREBOARD.format(
                    slug=slug, date=day.strftime("%Y%m%d")))
            except Exception as exc:  # noqa: BLE001
                if slug == "all":
                    failures.append(f"{key} all: {exc}")
                continue
            for ev in _soccer_events(payload):
                found[(normalise_team(ev[0]), normalise_team(ev[1]))] = ev
            if slug == "all" and found:
                break          # the cross-league board answered; skip the loop
        fetched[key] = list(found.values())
        return fetched[key]

    for d in wanted:
        try:
            base = _dt.date.fromisoformat(d[:10])
        except ValueError:
            continue
        for day in (base, base + _dt.timedelta(days=1)):
            for home, away, hs, as_, in_90 in day_events(day):
                if hs is None or as_ is None:
                    continue
                if not in_90:
                    extra_time.append(f"{home} v {away} ({day})")
                    continue
                try:
                    score = (float(hs), float(as_))
                except (TypeError, ValueError):
                    continue
                for filed in (day.isoformat(), d[:10]):
                    out.setdefault((filed, normalise_team(home), normalise_team(away)), score)
    if failures:
        log(f"[soccer] cross-league board failed for {len(failures)} day(s), "
            f"first: {failures[0]} -- fell back to per-league boards")
    if extra_time:
        log(f"[soccer] {len(extra_time)} game(s) went to extra time/penalties "
            f"and were NOT graded (90-minute markets): {', '.join(extra_time[:5])}")
    return out


fetch_soccer_results.wants_dates = True   # type: ignore[attr-defined]


AUTO_SOURCES = {
    "mlb": fetch_mlb_results,
    "baseball": fetch_mlb_results,   # rows logged as 'baseball' that are MLB games
    "nfl": fetch_nfl_results,
    "ncaaf": fetch_ncaaf_results,
    "tennis": fetch_tennis_results,
    "soccer": fetch_soccer_results,
    "football": fetch_soccer_results,   # older rows logged as 'football'
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
    rows = list(conn.execute(query, params))
    # PASS and INFO rows are not bets, so they are not "awaiting a result" --
    # filtering here keeps them out of --pending, --auto and --manual alike,
    # while they remain in the database as calibration data.
    return [row for row in rows if not is_excluded_tier(row["recommendation"])]


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

    # A fixture can be logged twice (both orientations, or a slate re-run).
    # Grade only the newest row per (date, sport, {teams}, market), and never a
    # key that already has a settled result. The older duplicate rows stay in
    # the database, ungraded and noted, so the duplicate stays visible without
    # double-counting in the record.
    rows, dropped = newest_per_fixture(rows)
    graded_keys = {
        dedup_key(r) for r in conn.execute(
            "SELECT * FROM predictions WHERE result_outcome IS NOT NULL")}
    to_grade = [r for r in rows if dedup_key(r) not in graded_keys]
    skip_dupes = [r for r in rows if dedup_key(r) in graded_keys]
    if dropped or skip_dupes:
        for row in dropped + skip_dupes:
            conn.execute(
                "UPDATE predictions SET grade_note='duplicate fixture -- "
                "excluded from grading (newest row kept)' WHERE id=?",
                (row["id"],))
        conn.commit()

    by_sport: Dict[str, List[sqlite3.Row]] = {}
    for row in to_grade:
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
            if getattr(fetcher, "wants_dates", False):
                results = fetcher(dates[0], dates[-1], dates=dates)
            else:
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
                if sport_key in ("soccer", "football"):
                    log(f"    [no result] #{row['id']} {row['game_date']} "
                        f"{row['home_team']} vs {row['away_team']}")
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
    if dropped or skip_dupes:
        log(f"{len(dropped) + len(skip_dupes)} duplicate row(s) excluded "
            f"(newest per fixture kept).")
    if unmatched:
        log("Unmatched usually means the game was on a different day than the "
            "prediction timestamp, or the team name is spelled differently.")
    return 0


def cmd_manual(conn: sqlite3.Connection, path: Path) -> int:
    if not path.exists():
        raise SystemExit(f"No such file: {path}")
    with open(path, newline="", encoding="utf-8-sig") as handle:
        entries = list(csv.DictReader(handle))

    # Keyed by (game_date, home, away). The date belongs in the key because the
    # same two clubs meet again and again: Lotte and KIA appear on the 26th, the
    # 27th and the 29th of one week. Matching on the pair alone settled every
    # one of those meetings at a single night's score, which is not a grade --
    # it is a fabricated result wearing the same shape as one.
    lookup: Dict[Tuple[str, str, str], Tuple[float, float]] = {}
    incomplete = 0
    for entry in entries:
        try:
            home_score = float(entry["home_score"])
            away_score = float(entry["away_score"])
        except (KeyError, TypeError, ValueError):
            incomplete += 1
            continue
        lookup[(str(entry.get("game_date") or "").strip(),
                normalise_team(entry.get("home_team", "")),
                normalise_team(entry.get("away_team", "")))] = (home_score, away_score)

    if not lookup:
        raise SystemExit(f"{path.name} has no rows with both scores filled in.")

    def find(date, home, away):
        """Prefer the same-date row; fall back to a dateless one only if the CSV
        left the date blank. A prediction whose date matches no filled row stays
        pending rather than borrowing another night's score."""
        for key_date in (date, ""):
            hit = lookup.get((key_date, home, away))
            if hit is not None:
                return hit
            flipped = lookup.get((key_date, away, home))
            if flipped is not None:
                return (flipped[1], flipped[0])
        return None

    graded = skipped_dupes = 0
    pending, dropped = newest_per_fixture(ungraded(conn))
    graded_keys = {
        dedup_key(r) for r in conn.execute(
            "SELECT * FROM predictions WHERE result_outcome IS NOT NULL")}
    for row in pending:
        if dedup_key(row) in graded_keys:
            skipped_dupes += 1
            conn.execute(
                "UPDATE predictions SET grade_note='duplicate fixture -- "
                "excluded from grading (newest row kept)' WHERE id=?",
                (row["id"],))
            continue
        scores = find(str(row["game_date"] or "").strip(),
                      normalise_team(row["home_team"]),
                      normalise_team(row["away_team"]))
        if scores is None:
            continue
        outcome = apply_result(conn, row, scores[0], scores[1], f"manual:{path.name}")
        if outcome:
            graded += 1
            log(f"  #{row['id']:>4} {row['home_team']} vs {row['away_team']} "
                f"({row['market_type']}) -> {outcome.upper()}")
    for row in dropped:
        conn.execute(
            "UPDATE predictions SET grade_note='duplicate fixture -- "
            "excluded from grading (newest row kept)' WHERE id=?",
            (row["id"],))
    conn.commit()
    log(f"\nGraded {graded} prediction(s) from {path.name}."
        + (f" {incomplete} row(s) had no scores yet." if incomplete else "")
        + (f" {len(dropped) + skipped_dupes} duplicate row(s) excluded."
           if dropped or skipped_dupes else ""))
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

    # Deduplicate before anything is tallied. Both orientations of one game and
    # re-runs of a slate collapse to the same (date, sport, {teams}, market),
    # and the newest row per key is the one that reflects the fresher line.
    rows, dropped = newest_per_fixture(rows)

    total_logged = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    if not rows:
        log(f"No graded predictions yet ({total_logged} logged in total).")
        log("Start with:  python grade_predictions.py --auto")
        log("          or python grade_predictions.py --pending")
        return 0

    header = f"  {'':<26}{'W-L':<12}{'WIN%':>8}{'UNITS':>11}{'ROI':>10}"
    log("=" * 78)
    log(f"PREDICTION RECORD   ({len(rows)} graded of {total_logged} logged"
        + (f", last {days} days" if days else "") + ")"
        + (f", {len(dropped)} duplicate row(s) excluded" if dropped else ""))
    log("=" * 78)

    # PASS and INFO rows are not bets (see is_excluded_tier); they are not part
    # of the record, only of the calibration breakdown at the bottom. Everything
    # else -- BET, STRONG BET, LEAN -- is a real decision with money behind it.
    record_rows = [r for r in rows if not is_excluded_tier(r["recommendation"])]
    bets = [r for r in record_rows if tier_of(r["recommendation"]) in {"STRONG BET", "BET"}]
    log("\nACTUAL BETS (STRONG BET + BET only -- this is the record that matters)")
    log(header)
    log(_line("all bets", _tally(bets)) if bets else "  (none yet)")
    for tier in ("STRONG BET", "BET"):
        subset = [r for r in bets if tier_of(r["recommendation"]) == tier]
        if subset:
            log(_line(f"  {tier.lower()}", _tally(subset)))

    # LEAN is real intent, not noise -- tennis/MLB's "LEAN ... (edge: +5.0%)"
    # strings are a genuine, if softer, recommendation. tier_of() didn't even
    # have a LEAN category before this fix, so these rows used to disappear
    # into "informational" below. Reporting it as its own section rather than
    # folding it into "ACTUAL BETS" -- it's a real signal, just a weaker one
    # than what this project's own thresholds call worth a full bet.
    leans = [r for r in record_rows if tier_of(r["recommendation"]) == "LEAN"]
    if leans:
        log("\nLEANS (a real signal, below this project's own BET threshold)")
        log(header)
        log(_line("all leans", _tally(leans)))

    # Combined line: every non-PASS/INFO bet, LEANs included. This is the
    # decision-covering number; the ACTUAL BETS section above keeps the
    # strict subset for reference.
    log("\nALL DECISIONS (BET + LEAN -- the full betting record)")
    log(header)
    log(_line("all decisions", _tally(record_rows)) if record_rows else "  (none yet)")

    log("\nBY SPORT")
    log(header)
    for name in sorted({(r["sport"] or "?") for r in record_rows}):
        log(_line(name, _tally([r for r in record_rows if r["sport"] == name])))

    log("\nBY MARKET")
    log(header)
    for market in sorted({(r["market_type"] or "?") for r in record_rows}):
        log(_line(market, _tally([r for r in record_rows if r["market_type"] == market])))

    log("\nBY CONFIDENCE  (is a higher score actually more reliable?)")
    log(header)
    for bucket in ("75+", "65-74", "55-64", "<55", "unknown"):
        subset = [r for r in record_rows if _bucket(r["confidence"]) == bucket]
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

    overall = _tally(record_rows)
    if overall["win_pct"] is not None:
        log("\n" + "-" * 78)
        breakeven = 100.0 / (1.0 + american_to_profit(DEFAULT_ODDS))
        verdict = "above" if overall["win_pct"] > breakeven else "below"
        log(f"  Break-even at {DEFAULT_ODDS:.0f} is {breakeven:.1f}%. "
            f"You are {verdict} it on {overall['wins'] + overall['losses']} decided bets.")
        if overall["wins"] + overall["losses"] < 30:
            log("  Sample is small -- under about 30 settled bets this number moves a lot.")
    priced = 0
    for row in record_rows:
        try:
            blob = json.loads(row["raw_json"]) if row["raw_json"] else {}
            if blob.get("_settled_at_recorded_price"):
                priced += 1
        except (json.JSONDecodeError, TypeError):
            pass
    if priced:
        log(f"  {priced} of {len(record_rows)} decision row(s) settled at recorded prices; "
            f"the rest assumed {DEFAULT_ODDS:.0f}.")
    log("=" * 78)

    if push_discord:
        _push_record_to_discord(record_rows, bets, days)
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
# REGRADE
# ==========================================================================

def cmd_regrade(conn: sqlite3.Connection, sport: Optional[str]) -> int:
    """Reset grading artifacts and re-settle every graded row from its store.

    The first honestly-settled record requires the 38 PASS and 42 INFO rows
    that were graded as if they were bets to be un-graded, the duplicate
    fixtures to collapse to their newest row, and every remaining graded row
    to be re-settled at its recorded price. Nothing here is guessed: a graded
    row that lost its stored score is left ungraded with a note rather than
    fabricated from nothing.

    Ungraded rows are untouched -- they still await a result via --auto or
    --manual. --regrade re-settles what is already graded; it does not fetch.
    """
    clause = "WHERE result_outcome IS NOT NULL"
    params: List[Any] = []
    if sport:
        clause += " AND lower(sport) = ?"
        params.append(sport.lower())

    rows = list(conn.execute(f"SELECT * FROM predictions {clause}", params))

    excluded = [r for r in rows if is_excluded_tier(r["recommendation"])]
    for row in excluded:
        conn.execute(
            "UPDATE predictions SET result_outcome=NULL, profit_loss=NULL, "
            "graded_at=NULL, grade_note=? WHERE id=?",
            (f"excluded: {tier_of(row['recommendation'])} row is not a bet "
             f"(regrade 2026-09-20)", row["id"]),
        )
    log(f"Un-graded {len(excluded)} PASS/INFO row(s) -- they are not bets.")

    keep, dropped = newest_per_fixture(
        [r for r in rows if not is_excluded_tier(r["recommendation"])])
    for row in dropped:
        conn.execute(
            "UPDATE predictions SET result_outcome=NULL, profit_loss=NULL, "
            "graded_at=NULL, grade_note='duplicate fixture -- excluded "
            "(newest row kept)' WHERE id=?",
            (row["id"],),
        )
    log(f"Dropped {len(dropped)} duplicate fixture row(s) (newest per fixture kept).")

    # Re-settle the surviving rows from the scores already stored in the row.
    regraded = ungradable = 0
    for row in keep:
        home = row["actual_home_score"]
        away = row["actual_away_score"]
        if home is None or away is None:
            conn.execute(
                "UPDATE predictions SET result_outcome=NULL, profit_loss=NULL, "
                "graded_at=NULL, grade_note='regrade: no stored score -- "
                "left pending' WHERE id=?",
                (row["id"],),
            )
            ungradable += 1
            continue
        try:
            outcome, pick, profit, priced = grade_row(row, float(home), float(away))
        except Ungradable as exc:
            conn.execute(
                "UPDATE predictions SET grade_note='regrade ungradable: %s' "
                "WHERE id=?" % exc,
                (row["id"],),
            )
            ungradable += 1
            continue
        try:
            raw = json.loads(row["raw_json"]) if row["raw_json"] else {}
        except (json.JSONDecodeError, TypeError):
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        raw["_settled_at_recorded_price"] = bool(priced)
        conn.execute(
            "UPDATE predictions SET result_outcome=?, profit_loss=?, pick=?, "
            "graded_at=?, raw_json=? WHERE id=?",
            (outcome, profit, pick,
             _dt.datetime.now().isoformat(timespec="seconds"), json.dumps(raw),
             row["id"]),
        )
        regraded += 1
    conn.commit()

    log(f"Re-settled {regraded} graded row(s) from stored scores "
        f"({ungradable} left pending -- no score recorded).")
    log("Run --report to see the honest record, then --auto to fetch the "
        "remaining results.")
    return 0


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
    parser.add_argument("--regrade", action="store_true",
                        help="Un-grade PASS/INFO rows, drop duplicate fixtures, and "
                             "re-settle every graded bet from its stored score at its "
                             "recorded price. Does not fetch new results.")
    parser.add_argument("--report", action="store_true", help="Print the win-rate record.")
    parser.add_argument("--push-discord", action="store_true",
                        help="Post the record to Discord (uses DISCORD_RESULTS_WEBHOOK_URL, "
                             "falling back to DISCORD_WEBHOOK_URL).")
    parser.add_argument("--sport", default=None, help="Limit to one sport.")
    parser.add_argument("--days", type=int, default=None,
                        help="Limit to the last N days (auto-grading defaults to 14).")
    args = parser.parse_args()

    if not any((args.auto, args.manual, args.pending, args.report, args.regrade)):
        parser.error("Pick at least one of --auto, --manual, --pending, --report, --regrade.")

    conn = open_db()
    added = ensure_schema(conn)
    if added:
        log(f"[schema] added column(s): {', '.join(added)}\n")

    try:
        if args.pending:
            cmd_pending(conn, args.sport, args.days)
        if args.regrade:
            cmd_regrade(conn, args.sport)
        if args.auto:
            cmd_auto(conn, args.sport, args.days or 14)
        if args.manual:
            cmd_manual(conn, args.manual)
        if args.report:
            if args.auto or args.manual or args.regrade:
                log("")
            cmd_report(conn, args.sport, args.days, args.push_discord)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
