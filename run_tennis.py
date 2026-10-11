#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_tennis.py - Run tennis matches through the Elo model

    python run_tennis.py --match "Carlos Alcaraz vs Jannik Sinner"
    python run_tennis.py --match "Alcaraz C. vs Sinner J." --surface hard
    python run_tennis.py --match "Sabalenka A. vs Gauff C." --p1-ml -180 --p2-ml +150
    python run_tennis.py --match "A vs B" --match "C vs D"      a whole day's card
    python run_tennis.py --push 1 3                             push after reviewing
    python run_tennis.py --list Alcaraz                         who is in the store
    python run_tennis.py --dry-run                              resolve names only

YOU CAN TYPE REAL NAMES
    The feed spells players "Alcaraz C.". You can type that, or "Carlos
    Alcaraz", or just "Alcaraz". The resolver works backwards from the stored
    key -- surname, then initial -- so "Roberto Carballes Baena" finds
    "Carballes Baena R." and a bare "Fritz" finds "Fritz T.".

    When a surname belongs to two players it says so and stops. Tennis has
    brothers, and a prediction attributed to the wrong Zverev is worse than no
    prediction.

BEST OF THREE OR FIVE IS NOT A GUESS
    Men play five sets at a Slam, women three. The tour is read from the store,
    not assumed, and a match between an ATP player and a WTA player is refused
    rather than run with a made-up format.

NOTHING IS PUSHED UNTIL YOU SAY SO
    Matches are predicted, stored and printed in a review table. --push takes
    the line numbers you want.

BEFORE RUNNING
    python ingest_tennis.py
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Ensure UTF-8 output on Windows consoles (cp1252 can't encode emoji)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

STORE = ROOT / "data" / "tennis" / "players.json"
MATCHES_CSV = ROOT / "data" / "tennis" / "matches.csv"
REVIEW = ROOT / "data" / "tennis_review.json"

MIN_MATCHES = 8         # below this the rating is mostly the starting constant
MAX_IDLE_DAYS = 400     # a player last seen longer ago than this is not current


def log(message: str = "") -> None:
    print(message, flush=True)


def rule(char: str = "=", width: int = 96) -> None:
    log(char * width)


# ==========================================================================
# NAME RESOLUTION
# ==========================================================================

KEY_PATTERN = re.compile(r"^(?P<surname>.+?)\s+(?P<initials>(?:[A-Z]\.)+)$")


def squash(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def split_key(key: str) -> Tuple[str, str]:
    """'Carballes Baena R.' -> ('carballes baena', 'r').

    The surname can be several words, so the split works from the RIGHT: the
    trailing run of single letters followed by dots is the initials, and
    everything before it is the surname. Splitting from the left would make
    'Carballes' the surname and lose every player with a compound name.
    """
    match = KEY_PATTERN.match(key.strip())
    if not match:
        tokens = key.strip().split()
        return " ".join(tokens[1:]).lower(), tokens[0][:1].lower() if tokens else ""
    surname = match.group("surname").strip().lower()
    initials = match.group("initials").replace(".", "").strip().lower()
    return surname, initials


def resolve(typed: str, store: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """Return (stored_key, how). Never picks between two equally good matches."""
    typed = typed.strip()
    if not typed:
        return None, "empty"

    if typed in store:
        return typed, "exact"

    flat = {squash(k): k for k in store}
    if squash(typed) in flat:
        return flat[squash(typed)], "case/punctuation"

    # Accept legacy surname-initial keys when a CSV source supplies full names.
    if KEY_PATTERN.match(typed):
        surname, initials = split_key(typed)
        hits = [k for k in store if split_key(k) == (surname, initials)]
        if len(hits) == 1:
            return hits[0], "legacy name"
        if len(hits) > 1:
            return None, "ambiguous: " + ", ".join(hits)

    by_surname: Dict[str, List[str]] = {}
    for key in store:
        surname, _ = split_key(key)
        by_surname.setdefault(squash(surname), []).append(key)

    tokens = [t for t in re.split(r"\s+", typed) if t]
    candidates: List[str] = []

    # Try every way of reading the typed name as [first names...] [surname...].
    # "Carlos Alcaraz" -> first='carlos', surname='alcaraz'
    # "Roberto Carballes Baena" -> first='roberto', surname='carballes baena'
    # "Alcaraz" -> no first name, surname='alcaraz'
    for split_at in range(len(tokens)):
        surname = squash(" ".join(tokens[split_at:]))
        matches = by_surname.get(surname, [])
        if not matches:
            continue
        given = tokens[:split_at]
        if not given:
            candidates.extend(matches)
            continue
        initial = squash(given[0])[:1]
        narrowed = [k for k in matches if split_key(k)[1].startswith(initial)]
        candidates.extend(narrowed or matches)

    unique = sorted(set(candidates))
    if len(unique) == 1:
        return unique[0], "name"
    if len(unique) > 1:
        return None, "ambiguous: " + ", ".join(unique)

    near = sorted(k for k in store if squash(typed) in squash(k))
    if len(near) == 1:
        return near[0], "partial"
    if near:
        return None, "ambiguous: " + ", ".join(near[:6])
    return None, "no match"


def parse_match(text: str) -> Tuple[str, str]:
    for separator in (" vs. ", " vs ", " VS ", " v. ", " v ", " - ", " @ "):
        if separator in text:
            first, second = text.split(separator, 1)
            return first.strip(), second.strip()
    raise ValueError(f'Could not read "{text}". Use the form: "Player A vs Player B"')


# ==========================================================================
# GUARD
# ==========================================================================

TOUR_MAX_LAG_DAYS = 45      # a tour whose newest match is older than this
                            # is a season that failed to download, not a quiet week


def tour_lag(store: Dict[str, Any], tour: str) -> Optional[int]:
    """Days between today and the most recent match ANY player on this tour played."""
    seen = [str(r.get("last_seen") or "")[:10] for r in store.values()
            if str(r.get("tour", "")).lower() == tour.lower()]
    seen = [s for s in seen if s]
    if not seen:
        return None
    try:
        return (_dt.date.today() - _dt.date.fromisoformat(max(seen))).days
    except ValueError:
        return None


def guard(store: Dict[str, Any], names: List[str]) -> Tuple[bool, List[str]]:
    """Refuse a player whose rating is not built on enough recent tennis.

    The per-player checks below catch one stale player. They do not catch a
    whole season failing to download -- which is the more dangerous case,
    because every rating on that tour is then equally and invisibly out of
    date. So the tour is checked first, against the calendar rather than
    against the other players in the same stale file.
    """
    today = _dt.date.today()
    problems: List[str] = []

    for tour in sorted({str(store.get(n, {}).get("tour", "")).lower()
                        for n in names} - {""}):
        lag = tour_lag(store, tour)
        if lag is not None and lag > TOUR_MAX_LAG_DAYS:
            problems.append(
                f"{tour.upper()}: the newest match in the store is {lag} days old. "
                f"That is a season that did not download, not a quiet week -- "
                f"every {tour.upper()} rating is frozen at that date. "
                f"Re-run: venv/Scripts/python.exe ingest_tennis.py")
    for name in names:
        record = store.get(name) or {}
        played = int(record.get("matches") or 0)
        if played < MIN_MATCHES:
            problems.append(
                f"{name}: only {played} match(es) in the store, need {MIN_MATCHES} "
                f"before an Elo means anything")
        last = str(record.get("last_seen") or "")[:10]
        if not last:
            problems.append(f"{name}: no match dates recorded")
            continue
        try:
            idle = (today - _dt.date.fromisoformat(last)).days
        except ValueError:
            problems.append(f"{name}: unreadable last-match date {last!r}")
            continue
        if idle > MAX_IDLE_DAYS:
            problems.append(f"{name}: last seen {last} ({idle} days ago) -- "
                            f"the rating is stale, not current form")
    return (not problems), problems


def american_to_prob(odds: Optional[float]) -> Optional[float]:
    if odds is None:
        return None
    value = float(odds)
    return (-value) / ((-value) + 100.0) if value < 0 else 100.0 / (value + 100.0)


def no_vig(p1: Optional[float], p2: Optional[float]) -> Optional[float]:
    """Strip the book's margin so the edge is a real disagreement.

    Two prices on a two-way market sum to more than 1. Comparing a model number
    against the raw implied probability shows an edge on whichever side you
    look at first, which is worse than showing none.
    """
    if p1 is None or p2 is None:
        return None
    total = p1 + p2
    return p1 / total if total else None


def _price_text(value: Any) -> Optional[str]:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return f"{price:+g}" if math.isfinite(price) else None


def _probability_text(value: Any) -> str:
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return "unavailable"
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        return "unavailable"
    return f"{probability:.1%}"


def _line_text(value: Any) -> str:
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return "unavailable"


def _market_origin(item: Dict[str, Any], custom_markets: List[Dict[str, Any]]) -> str:
    source = str(item.get("line_origin") or item.get("market_origin")
                 or item.get("source") or "").lower()
    if "live" in source:
        return "Live Market Line"
    if any(token in source for token in ("user", "manual", "custom")):
        return "User-Supplied / Manual Line"
    for custom in custom_markets:
        if custom.get("kind") == item.get("kind"):
            try:
                if float(custom.get("line")) == float(item.get("line")):
                    return "User-Supplied / Manual Line"
            except (TypeError, ValueError):
                continue
    return "Model Baseline Line (no market prices)"


def _tennis_action(row: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[float]]:
    model = row.get("model_prob")
    market = row.get("market_prob")
    p1_price, p2_price = _price_text(row.get("p1_ml")), _price_text(row.get("p2_ml"))
    if model is None or market is None or p1_price is None or p2_price is None:
        return "👉 ACTION: PASS — No priced moneyline market supplied", None, None
    try:
        model_prob, market_prob = float(model), float(market)
    except (TypeError, ValueError):
        return "👉 ACTION: PASS — Moneyline probabilities unavailable", None, None
    if not all(math.isfinite(value) and 0 <= value <= 1
               for value in (model_prob, market_prob)):
        return "👉 ACTION: PASS — Moneyline probabilities unavailable", None, None

    edge_p1 = model_prob - market_prob
    player, price = ((row["p1"], p1_price) if edge_p1 >= 0
                     else (row["p2"], p2_price))
    edge = abs(edge_p1) * 100
    if edge >= 5.0 - 1e-9:
        verdict = "BET"
    elif edge >= 2.0 - 1e-9:
        verdict = "LEAN"
    else:
        return "👉 ACTION: PASS — Market is efficient", player, edge
    return f"👉 ACTION: {verdict} {player} ML ({price}) (Edge: +{edge:.1f}%)", player, edge


def _ev_text(side: str, value: Any, price: Any) -> str:
    if value is None or _price_text(price) is None:
        return f"{side} Price: None — No EV calculated (PASS)"
    try:
        ev = float(value)
    except (TypeError, ValueError):
        ev = math.nan
    if not math.isfinite(ev):
        return f"{side} Price: None — No EV calculated (PASS)"
    return f"{side} {ev * 100:+.1f}% EV"


def _alternative_market_lines(item: Dict[str, Any], p1: str, p2: str,
                              custom_markets: List[Dict[str, Any]]) -> List[str]:
    kind = str(item.get("kind") or "")
    if kind not in {"games_total", "sets_total", "games_spread", "sets_spread"}:
        return []
    line = item.get("line")
    line_label = _line_text(line)
    unit = "Games" if kind.startswith("games_") else "Sets"
    origin = _market_origin(item, custom_markets)
    price_a, price_b = _price_text(item.get("price_a")), _price_text(item.get("price_b"))
    prob_a = _probability_text(item.get("prob_a"))
    prob_b = _probability_text(item.get("prob_b"))
    ev_a, ev_b = item.get("ev_a"), item.get("ev_b")

    if kind.endswith("total"):
        title = f"📊 TOTAL {unit.upper()} (OVER / UNDER {line_label})"
        price_line = (f"• Market Line: {line_label} {unit} @ Over {price_a or 'None'} / "
                      f"Under {price_b or 'None'} ({origin})")
        projection_line = f"• Model Projection: Over {prob_a} | Under {prob_b}"
        ev_line = f"• Expected Value: {_ev_text('Over', ev_a, item.get('price_a'))} | " \
                  f"{_ev_text('Under', ev_b, item.get('price_b'))}"
        action_sides = (("OVER", p1, None, item.get("price_a"), ev_a),
                        ("UNDER", p2, None, item.get("price_b"), ev_b))
    else:
        try:
            signed_line = float(line)
        except (TypeError, ValueError):
            return []
        line_a = f"{signed_line:+g}"
        line_b = f"{-signed_line:+g}"
        title = f"⚖️ {unit.upper()} SPREAD (HANDICAP +/- {abs(signed_line):g})"
        price_line = (f"• Market Line: {p1} {line_a} ({price_a or 'None'}) vs "
                      f"{p2} {line_b} ({price_b or 'None'}) ({origin})")
        projection_line = (f"• Model Cover: {p1} ({line_a}) {prob_a} | "
                           f"{p2} ({line_b}) {prob_b}")
        ev_line = (f"• Expected Value: "
                   f"{_ev_text(f'{p1} ({line_a})', ev_a, item.get('price_a'))} | "
                   f"{_ev_text(f'{p2} ({line_b})', ev_b, item.get('price_b'))}")
        action_sides = ((p1, p1, line_a, item.get("price_a"), ev_a),
                        (p2, p2, line_b, item.get("price_b"), ev_b))

    candidates = []
    for side, player, handicap, price, ev in action_sides:
        if price is None or ev is None:
            continue
        try:
            numeric_ev = float(ev)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numeric_ev) and numeric_ev > 0:
            candidates.append((numeric_ev, side, player, handicap, _price_text(price)))
    if candidates:
        ev, side, player, handicap, price = max(candidates)
        if kind.endswith("total"):
            action = f"👉 ACTION: BET {side} {line_label} {unit} ({price}) (EV: {ev * 100:+.1f}%)"
        else:
            action = (f"👉 ACTION: BET {player} {handicap} {unit} ({price}) "
                      f"(EV: {ev * 100:+.1f}%)")
    elif price_a is None or price_b is None:
        action = "👉 ACTION: PASS — No EV available for every side without prices"
    else:
        action = "👉 ACTION: PASS — No positive expected value"

    output = [title, price_line, projection_line, ev_line, action]
    if item.get("bookmaker"):
        output.insert(2, f"• Sportsbook: {item['bookmaker']} | Updated: {item.get('last_update') or 'unknown'}")
    return output


def format_tennis_review(row: Dict[str, Any]) -> List[str]:
    """Create an explicitly priced, named market review for a novice bettor."""
    tournament = row.get("tournament") or "Tennis"
    best_of = 5 if row.get("best_of_5") else 3
    heading = (f"🎾 {str(tournament).upper()} | {row['p1']} vs {row['p2']} "
               f"({str(row.get('surface') or 'unknown').title()}, Best of {best_of})")
    lines = [heading, "", "🏆 MONEYLINE (MATCH WINNER)"]
    p1_odds = _price_text(row.get("p1_ml"))
    p2_odds = _price_text(row.get("p2_ml"))
    market_prob = row.get("market_prob")
    model_prob = row.get("model_prob")
    source = row.get("market_source")
    if p1_odds is not None and p2_odds is not None and market_prob is not None:
        source_label = "Live" if source == "live" else "User-Supplied"
        p1_market = _probability_text(market_prob)
        try:
            p2_market = _probability_text(1.0 - float(market_prob))
        except (TypeError, ValueError):
            p2_market = "unavailable"
        lines.append(f"• Market Odds ({source_label}): {row['p1']} {p1_odds} ({p1_market}) | "
                     f"{row['p2']} {p2_odds} ({p2_market})")
    else:
        lines.append("• Market Odds: Prices or no-vig probabilities unavailable")
    if model_prob is not None:
        try:
            model_p1 = float(model_prob)
            model_p2 = 1.0 - model_p1
            lines.append(f"• Model Projection: {row['p1']} {_probability_text(model_p1)} | "
                         f"{row['p2']} {_probability_text(model_p2)}")
        except (TypeError, ValueError):
            lines.append("• Model Projection: probabilities unavailable")
    else:
        lines.append("• Model Projection: probabilities unavailable")
    action, edge_player, edge = _tennis_action(row)
    lines.append(f"• Edge: +{edge:.1f}% on {edge_player}" if edge is not None
                 else "• Edge: unavailable — no priced market")
    lines.append(action)

    custom_markets = row.get("custom_markets") or []
    for item in row.get("alternative_markets") or []:
        market_lines = _alternative_market_lines(item, row["p1"], row["p2"], custom_markets)
        if market_lines:
            lines.extend(["", *market_lines])
    if any(str(item.get("kind", "")).startswith("games_")
           for item in row.get("alternative_markets") or []):
        lines.extend(["", "⚠️ Note: Simulation uses baseline 75% serve-hold rate (uncalibrated)"])
    return lines


# ==========================================================================
# RUN
# ==========================================================================

def run_one(p1: str, p2: str, store: Dict[str, Any], surface: str,
            tournament: str, round_name: str, best_of_5: bool,
            p1_ml: Optional[float], p2_ml: Optional[float],
            push_discord: bool, custom_markets: Optional[List[Dict[str, Any]]] = None,
            player_context: Optional[Dict[str, Any]] = None, store_to_db: bool = True,
            auto_odds: bool = True, game_date: Optional[str] = None) -> Dict[str, Any]:
    rule()
    log(f"{tournament}  {round_name}   {p1}  vs  {p2}   ({surface}, "
        f"best of {'5' if best_of_5 else '3'})")
    rule("-")

    for label, name in (("  ", p1), ("  ", p2)):
        record = store.get(name, {})
        surfaces = "  ".join(
            f"{s} {d['wins']}-{d['matches'] - d['wins']}"
            for s, d in sorted(record.get("by_surface", {}).items()))
        log(f"{label}{name:<24} {record.get('wins', '?')}-{record.get('losses', '?')} "
            f"overall   rank {record.get('last_rank') or '?':<5} {surfaces}")

    market_prob = no_vig(american_to_prob(p1_ml), american_to_prob(p2_ml))
    user_supplied_odds = p1_ml is not None and p2_ml is not None

    from universal_runner import run_tennis
    tour = str(store.get(p1, {}).get("tour") or store.get(p2, {}).get("tour") or "").lower()
    result = run_tennis(
        p1, p2, surface=surface, tournament=tournament, round_name=round_name,
        best_of_5=best_of_5, store_to_db=store_to_db, push_discord=push_discord, auto_odds=auto_odds,
        market_prob=market_prob, tour=tour or None,
        home_ml=p1_ml, away_ml=p2_ml, custom_markets=custom_markets, player_context=player_context, game_date=game_date,
    )

    # market_prob above was only from typed --p1-ml/--p2-ml -- run_tennis()
    # may have auto-fetched a real price internally when neither was given.
    # That reassignment lives inside run_tennis()'s own frame and does not
    # propagate back to this variable by itself, so both the log line AND
    # this function's returned market_prob (which show_review()'s table
    # reads) have to be recomputed from result["auto_odds"] here -- without
    # this, the review table would show blank market/edge columns for a
    # pick that was, underneath, actually made against a real fetched price.
    auto = (result or {}).get("auto_odds") or {} if isinstance(result, dict) else {}
    if market_prob is None:
        if auto.get("status") in ("live", "cached") and auto.get("home_ml") is not None:
            market_prob = no_vig(american_to_prob(auto.get("home_ml")), american_to_prob(auto.get("away_ml")))

    alternatives = (result or {}).get("alternative_markets", [])
    moneyline = (result or {}).get("moneyline", {}) if isinstance(result, dict) else {}
    return {
        "p1": p1, "p2": p2, "surface": surface, "tournament": tournament,
        "round": round_name, "best_of_5": best_of_5,
        "game_date": result.get("game_date"),
        "model_prob": moneyline.get("home_win_prob"),
        "market_prob": market_prob,
        "odds_captured_at": auto.get("captured_at"),
        "custom_markets": result.get("custom_markets") or custom_markets or [],
        "alternative_markets": alternatives,
        "player_context": player_context,
        "context_audit": (result or {}).get("context_audit"),
        "market_source": ("live" if auto.get("status") in ("live", "cached")
                          else "user" if user_supplied_odds else None),
        "p1_ml": p1_ml if p1_ml is not None else auto.get("home_ml"),
        "p2_ml": p2_ml if p2_ml is not None else auto.get("away_ml"),
        "recommendation": moneyline.get("recommendation"),
        "confidence": moneyline.get("confidence"),
    }


def show_review(rows: List[Dict[str, Any]]) -> None:
    log("")
    rule("=", 110)
    log("📋  REVIEW  —  model vs market (vig removed).  Nothing has been pushed.")
    rule("=", 110)
    for index, row in enumerate(rows, start=1):
        log(f"  {index}. {row['p1']} vs {row['p2']} — "
            f"{row.get('tournament') or 'Tennis'} ({row.get('surface') or 'surface unknown'})")
        log(f"     {_tennis_action(row)[0]}")
    log("  💡  Push the ones you want:")
    log("      venv/Scripts/python.exe run_tennis.py --push 1")
    log("")
    log("  Small edges may be estimation noise; this model is not calibrated to betting outcomes.")
    log("  Elo estimates strength. Use --context for sourced injury/travel/venue observations.")
    log("  Numeric context effects are scenarios; unknown conditions are not guessed.")
    rule("=", 110)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-date", help="Actual match date YYYY-MM-DD; checked against matched odds event")
    parser.add_argument("--no-store", action="store_true", help="Predict without database writes")
    parser.add_argument("--no-odds", action="store_true", help="Disable automatic odds lookup")
    parser.add_argument("--context", type=Path, help="Sourced player observations and explicit Elo scenarios JSON")
    parser.add_argument("--match", action="append", metavar='"A vs B"')
    parser.add_argument("--surface", default="hard",
                        choices=["hard", "clay", "grass", "carpet"])
    parser.add_argument("--tournament", default="US Open")
    parser.add_argument("--round", dest="round_name", default="R1")
    parser.add_argument("--p1-ml", action="append", type=float,
                        help="American odds for the first player. Repeat per --match.")
    parser.add_argument("--p2-ml", action="append", type=float)
    parser.add_argument("--best-of", type=int, choices=[3, 5], default=None,
                        help="Override. Default: 5 for ATP Grand Slams, otherwise 3.")
    parser.add_argument("--push", nargs="+", type=int, metavar="N",
                        help="Push these line numbers from the last review.")
    parser.add_argument("--list", metavar="NAME", help="Search the store.")
    for flag in ("games-total", "sets-total", "games-spread", "sets-spread"):
        parser.add_argument("--" + flag, action="append", nargs=4,
            metavar=("MATCH_NUMBER", "LINE", "PRICE_A", "PRICE_B"),
            help="Repeat per alternative line. Prices: American odds or none. "
                 "Totals: over/under. Spreads: first/second supplied player; line applies to the first.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Resolve names and show the data, predict nothing.")
    args = parser.parse_args()

    if not STORE.exists():
        rule()
        log("No tennis store.")
        rule()
        log(f"\nExpected {STORE}\n")
        log("Build it first:")
        log("    venv/Scripts/python.exe ingest_tennis.py")
        sys.exit(1)

    if not MATCHES_CSV.exists():
        # players.json alone is not enough. The Elo engine reads matches.csv;
        # without it every rating falls back to the frozen built-in seeds and
        # every match comes out near a coin flip -- with a confidence score
        # attached, which is worse than an error.
        rule()
        log("NO MATCH HISTORY -- nothing was run")
        rule()
        log(f"\n  {MATCHES_CSV} does not exist.")
        log("  Elo is built from results, not from a list of players, so without")
        log("  it every rating is the starting constant and every prediction is")
        log("  a coin flip wearing a confidence score.\n")
        log("  Build it:")
        log("      venv/Scripts/python.exe ingest_tennis.py")
        sys.exit(1)

    store = json.loads(STORE.read_text(encoding="utf-8-sig"))

    if args.list is not None:
        needle = args.list.strip().lower()
        hits = sorted(k for k in store if needle in k.lower())
        if not hits:
            log(f"Nobody matching {args.list!r} in {len(store)} players.")
            sys.exit(1)
        for key in hits:
            record = store[key]
            log(f"  {key:<26} {record['tour'].upper():<4} "
                f"{record['wins']}-{record['losses']}  "
                f"rank {record.get('last_rank') or '?':<5} "
                f"last {record.get('last_seen')}")
        return

    if args.push:
        if not REVIEW.exists():
            log("Nothing to push -- no review on file. Run the matches first.")
            sys.exit(1)
        saved = json.loads(REVIEW.read_text(encoding="utf-8-sig"))
        rows = saved.get("rows", [])
        from universal_runner import run_tennis
        for number in args.push:
            if not 1 <= number <= len(rows):
                log(f"  [skip] {number} is not a line in the review (1..{len(rows)})")
                continue
            row = rows[number - 1]
            log(f"  pushing {number}. {row['p1']} v {row['p2']}")
            run_tennis(row["p1"], row["p2"], surface=row["surface"],
                       tournament=row["tournament"], round_name=row["round"],
                       best_of_5=row["best_of_5"], store_to_db=False,
                       push_discord=True, market_prob=row.get("market_prob"),
                       tour=str(store.get(row["p1"], {}).get("tour") or "") or None,
                       home_ml=row.get("p1_ml"), away_ml=row.get("p2_ml"),
                       auto_odds=False, custom_markets=row.get("custom_markets"), player_context=row.get("player_context"), game_date=row.get("game_date"))
        return

    if not args.match:
        parser.error('Give at least one --match "Player A vs Player B"')

    try:
        player_context = json.loads(args.context.read_text(encoding="utf-8-sig")) if args.context else None
    except (OSError, ValueError) as exc:
        parser.error(f"Cannot load context: {exc}")
    custom_by_match: Dict[int, List[Dict[str, Any]]] = {}
    from models.tennis_markets import evaluate_markets
    for kind in ("games_total", "sets_total", "games_spread", "sets_spread"):
        for target, line, price_a, price_b in getattr(args, kind) or []:
            try:
                index = int(target)
                if not 1 <= index <= len(args.match):
                    raise ValueError("MATCH_NUMBER must refer to a supplied --match")
                spec = {"kind": kind, "line": float(line),
                    "price_a": None if price_a.lower() == "none" else float(price_a),
                    "price_b": None if price_b.lower() == "none" else float(price_b),
                    "line_origin": "user_supplied"}
                evaluate_markets(0.5, args.best_of == 5, [spec])
                custom_by_match.setdefault(index, []).append(spec)
            except ValueError as exc:
                parser.error(str(exc))

    p1_odds = args.p1_ml or []
    p2_odds = args.p2_ml or []

    resolved: List[Tuple[str, str, Optional[float], Optional[float]]] = []
    problems: List[str] = []
    for index, text in enumerate(args.match):
        try:
            typed_a, typed_b = parse_match(text)
        except ValueError as exc:
            problems.append(str(exc))
            continue
        name_a, how_a = resolve(typed_a, store)
        name_b, how_b = resolve(typed_b, store)
        for typed, name, how in ((typed_a, name_a, how_a), (typed_b, name_b, how_b)):
            if name is None:
                problems.append(f'"{typed}" -> {how}')
            elif how != "exact":
                log(f'[name] "{typed}" -> "{name}"  ({how})')
        if name_a and name_b:
            resolved.append((
                name_a, name_b,
                p1_odds[index] if index < len(p1_odds) else None,
                p2_odds[index] if index < len(p2_odds) else None,
            ))

    if problems:
        rule()
        log("COULD NOT RESOLVE THESE NAMES")
        rule()
        for problem in problems:
            log(f"  {problem}")
        log("\nFind the spelling the store uses:")
        log('    venv/Scripts/python.exe run_tennis.py --list "part of the name"')
        log("\nNothing was run. A prediction on the wrong player is worse than none.")
        sys.exit(1)

    involved = sorted({n for pair in resolved for n in pair[:2]})
    safe, notes = guard(store, involved)
    if not safe:
        rule()
        log("THIN OR STALE DATA -- nothing was run")
        rule()
        for note in notes:
            log(f"  {note}")
        log("\n  Refresh, or add a season:")
        log("      venv/Scripts/python.exe ingest_tennis.py --years 2024 2025 2026")
        sys.exit(1)

    rows: List[Dict[str, Any]] = []
    for match_index, (name_a, name_b, odds_a, odds_b) in enumerate(resolved, start=1):
        tours = {store[name_a]["tour"], store[name_b]["tour"]}
        if len(tours) > 1:
            log(f"  [skip] {name_a} is {store[name_a]['tour'].upper()} and "
                f"{name_b} is {store[name_b]['tour'].upper()} -- they do not "
                f"play each other, so this is a name mix-up, not a fixture.")
            continue
        best_of_5 = (args.best_of == 5) if args.best_of else (tours == {"atp"} and args.tournament.strip().lower() in {"us open", "australian open", "french open", "roland garros", "wimbledon"})

        if args.dry_run:
            log(f"  [dry-run] {name_a} v {name_b}  "
                f"({'best of 5' if best_of_5 else 'best of 3'})")
            continue
        try:
            rows.append(run_one(name_a, name_b, store, args.surface,
                                args.tournament, args.round_name, best_of_5,
                                odds_a, odds_b, push_discord=False,
                                custom_markets=custom_by_match.get(match_index), player_context=player_context,
                                store_to_db=not args.no_store, auto_odds=not args.no_odds, game_date=args.game_date))
        except Exception as exc:                        # noqa: BLE001
            log(f"  [FAILED] {name_a} v {name_b}: {type(exc).__name__}: {exc}")

    if args.dry_run:
        return
    if not rows:
        raise SystemExit("No matches successfully predicted")

    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    REVIEW.write_text(json.dumps(
        {"generated": _dt.datetime.now().isoformat(timespec="seconds"), "rows": rows},
        indent=2), encoding="utf-8")
    show_review(rows)


if __name__ == "__main__":
    main()
