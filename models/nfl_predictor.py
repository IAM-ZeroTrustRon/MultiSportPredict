#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
models/nfl_predictor.py - NFL game model: spread, moneyline, totals, halftime

    from models.nfl_predictor import predict_nfl_game
    result = predict_nfl_game("Kansas City Chiefs", "Buffalo Bills",
                              market_spread=-2.5, market_total=47.5,
                              market_home_ml=-135, market_away_ml=115)

WHAT IT DOES NOT DO
    No player props. Those are the sharpest markets on the board, priced by
    people holding injury reports, snap counts and weather this model does not
    have. They belong in a separate module that emits projections with no
    recommendation until a graded record justifies otherwise.

THE MODEL
    Each side's expected points is the league average, adjusted by how much
    better than average that offence is and how much worse than average the
    opposing defence is:

        home_pts = league_avg + (home_off - avg) - (away_def - avg) + HFA
        away_pts = league_avg + (away_off - avg) - (home_def - avg)

    Everything else falls out of those two numbers. Spread is their difference,
    total is their sum, team totals are the components themselves.

THREE CONSTANTS THAT MATTER MORE THAN THE MODEL
    HOME_FIELD_POINTS = 1.8
        Home field in the modern NFL is worth roughly 1.5-2.0 points, not the
        ~3 that older references quote. It moved and most published material
        did not.

    MARGIN_SD = 13.5
        NFL final margins have a standard deviation near 13.5 points. This is
        what converts a spread into a win probability. Do not reuse a curve
        fitted for another sport -- that is how a 3-point favourite ends up
        priced like a 10-point one.

    MARGIN_SD_1H = 9.5
        First halves are lower-scoring, so first-half margins are tighter --
        but NOT 13.5 halved. Variance does not scale linearly with points.

    All three are assumptions. They are named, in one place, and meant to be
    re-fitted from your own graded results after a season rather than trusted
    because they appeared in a docstring.

KEY NUMBERS ARE WHY MOST FOOTBALL MODELS LOSE
    NFL margins pile up on 3 and 7 far more than a normal distribution
    predicts. A model spread of 3.4 against a market spread of 3.0 is not an
    edge -- it is noise sitting on top of the single most common margin in the
    sport. Recommendations are suppressed when the edge is small and the market
    number is on or beside a key number. This rule will save more money than any
    refinement to the points model.

MISSING TEAMS RAISE
    A club with no stats does not get league averages. That substitution is the
    bug this project has fixed three times in three sports, and each time it
    produced confident predictions that described nobody.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
STATS_PATH = ROOT / "data" / "nfl_stats.json"

# --- the assumptions, all in one place -------------------------------------
HOME_FIELD_POINTS = 1.8
MARGIN_SD = 13.5
MARGIN_SD_1H = 9.5
FIRST_HALF_SHARE = 0.475          # only used if real 1H data is missing

# Margins cluster here. A "near" number is within half a point of one.
KEY_NUMBERS = (3.0, 7.0, 10.0, 14.0)
KEY_NUMBER_WINDOW = 0.5
MIN_EDGE_NEAR_KEY = 1.5           # points of edge required beside a key number
MIN_EDGE_SPREAD = 1.0             # points of edge required anywhere else
MIN_EDGE_TOTAL = 2.0              # totals are noisier; ask for more

# How far last season's team is regressed toward league average before use.
# Last year's 13-4 team is not this year's 13-4 team.
PRIOR_REGRESSION = 0.30
SHRINKAGE_K = 4                   # weight_current = games / (games + k)


class MissingTeam(Exception):
    """Raised instead of substituting a league average for a club we lack."""


# ==========================================================================
# DATA
# ==========================================================================

def load_store() -> Dict[str, Dict[str, Any]]:
    if not STATS_PATH.exists():
        raise MissingTeam(
            f"{STATS_PATH} does not exist. Build it first:\n"
            f"    venv/Scripts/python.exe ingest_nfl.py --season 2025")
    store = json.loads(STATS_PATH.read_text(encoding="utf-8-sig"))
    return {k: v for k, v in store.items()
            if not k.startswith("_") and isinstance(v, dict)}


def _norm(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def resolve_team(name: str, store: Dict[str, Dict[str, Any]]) -> str:
    """Exact, then squashed, then unique substring. Ambiguity raises."""
    if name in store:
        return name
    flat = {_norm(k): k for k in store}
    if _norm(name) in flat:
        return flat[_norm(name)]
    hits = [real for squashed, real in flat.items() if _norm(name) in squashed]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise MissingTeam(f"'{name}' matches {len(hits)}: {', '.join(sorted(hits))}")
    raise MissingTeam(
        f"'{name}' is not in {STATS_PATH.name}. Nothing was guessed. "
        f"Run: venv/Scripts/python.exe ingest_nfl.py --season 2025")


def league_averages(store: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    scored = [float(r["points_for"]) for r in store.values()
              if r.get("points_for") is not None]
    allowed = [float(r["points_against"]) for r in store.values()
               if r.get("points_against") is not None]
    first_for = [float(r["points_1h_for"]) for r in store.values()
                 if r.get("points_1h_for") is not None]
    first_against = [float(r["points_1h_against"]) for r in store.values()
                     if r.get("points_1h_against") is not None]
    if not scored or not allowed:
        raise MissingTeam("No points data in the store at all.")
    average = sum(scored) / len(scored)
    return {
        "points": average,
        "points_against": sum(allowed) / len(allowed),
        "points_1h": (sum(first_for) / len(first_for)) if first_for
                     else average * FIRST_HALF_SHARE,
        "points_1h_against": (sum(first_against) / len(first_against))
                             if first_against else average * FIRST_HALF_SHARE,
        "has_real_1h": bool(first_for and first_against),
    }


# ==========================================================================
# STRENGTH
# ==========================================================================

def regressed(value: float, average: float, amount: float = PRIOR_REGRESSION) -> float:
    """Pull a team's number toward the league mean. Extremes do not repeat."""
    return value + (average - value) * amount


def strengths(record: Dict[str, Any], averages: Dict[str, float],
              regress: bool) -> Tuple[float, float]:
    """(offence, defence) as points per game, regressed if this is a prior."""
    offence = float(record.get("points_for") or averages["points"])
    defence = float(record.get("points_against") or averages["points_against"])
    if regress:
        offence = regressed(offence, averages["points"])
        defence = regressed(defence, averages["points_against"])
    return offence, defence


def current_nfl_season(today: Optional[_dt.date] = None) -> int:
    """The season now in progress. It opens in September and ends in February."""
    today = today or _dt.date.today()
    return today.year if today.month >= 8 else today.year - 1


def blend_weight(games_played: Optional[int], record_season: Optional[int],
                 today: Optional[_dt.date] = None) -> float:
    """How much of this number is THIS season rather than a previous one.

    Games played alone cannot answer that. A completed 2025 season has 17
    games, and counting them as current returned a weight of 0.81 -- so a
    finished prior season was treated as an 81%-current read and was never
    regressed toward the mean. The model then disagreed with the market by ten
    points and called it an edge, when the real disagreement was that it did
    not know what year it was.

    The season stamp settles it. A record from a prior season is weight zero
    however many games it holds.
    """
    if not games_played:
        return 0.0
    season = None
    try:
        season = int(str(record_season)[:4])
    except (TypeError, ValueError):
        pass
    if season is not None and season < current_nfl_season(today):
        return 0.0
    return float(games_played) / (float(games_played) + SHRINKAGE_K)


# ==========================================================================
# PROBABILITY
# ==========================================================================

def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def win_probability(margin: float, sd: float = MARGIN_SD) -> float:
    """P(favourite wins) given an expected margin. Φ(margin / sd)."""
    return normal_cdf(margin / sd)


def cover_probability(model_margin: float, market_spread: float,
                      sd: float = MARGIN_SD) -> float:
    """P(home covers). market_spread is from the home side: -3 means laying 3."""
    return normal_cdf((model_margin + market_spread) / sd)


def american_to_prob(odds: Optional[float]) -> Optional[float]:
    if odds is None:
        return None
    value = float(odds)
    return (-value) / ((-value) + 100.0) if value < 0 else 100.0 / (value + 100.0)


def no_vig(home: Optional[float], away: Optional[float]) -> Optional[float]:
    """Strip the margin so an edge is a disagreement, not the book's cut."""
    if home is None or away is None:
        return None
    total = home + away
    return home / total if total else None


# ==========================================================================
# KEY NUMBERS
# ==========================================================================

def near_key_number(spread: float) -> Optional[float]:
    for key in KEY_NUMBERS:
        if abs(abs(spread) - key) <= KEY_NUMBER_WINDOW:
            return key
    return None


def spread_call(edge: float, market_spread: float) -> Tuple[str, str]:
    """Turn a points edge into a decision, with key numbers respected."""
    key = near_key_number(market_spread)
    floor = MIN_EDGE_NEAR_KEY if key else MIN_EDGE_SPREAD
    if abs(edge) < floor:
        why = (f"edge {edge:+.1f} is inside the noise around {key:g}, the most "
               f"common margin in the sport" if key
               else f"edge {edge:+.1f} is under the {floor:g}-point floor")
        return "PASS", why
    side = "HOME" if edge > 0 else "AWAY"
    note = f"{abs(edge):.1f} points" + (f", clear of the key number {key:g}"
                                        if key else "")
    return side, note


# ==========================================================================
# PREDICT
# ==========================================================================

def predict_nfl_game(home_team: str, away_team: str, *,
                     market_spread: Optional[float] = None,
                     market_total: Optional[float] = None,
                     market_home_ml: Optional[float] = None,
                     market_away_ml: Optional[float] = None,
                     neutral_site: bool = False) -> Dict[str, Any]:
    """Model one game. market_spread is from the home side (-3 = home lays 3)."""
    store = load_store()
    home_key = resolve_team(home_team, store)
    away_key = resolve_team(away_team, store)
    home_rec, away_rec = store[home_key], store[away_key]
    averages = league_averages(store)

    # A prior season gets regressed; a current season with real games does not.
    home_games = int(home_rec.get("games") or 0)
    away_games = int(away_rec.get("games") or 0)
    weight = min(blend_weight(home_games, home_rec.get("season")),
                 blend_weight(away_games, away_rec.get("season")))
    is_prior = weight < 0.5
    seasons = {str(home_rec.get("season")), str(away_rec.get("season"))}

    home_off, home_def = strengths(home_rec, averages, regress=is_prior)
    away_off, away_def = strengths(away_rec, averages, regress=is_prior)

    average = averages["points"]
    hfa = 0.0 if neutral_site else HOME_FIELD_POINTS
    # strengths() returns defence as POINTS ALLOWED, where a bigger number is
    # a worse defence. These two lines subtracted that term, so facing a bad
    # defence lowered your projected points and facing a good one raised them
    # -- the relationship exactly backwards. It put Patriots/Seahawks, two of
    # the best defences in the league, at a 62.7 total, and Jets/Titans at
    # 31.5. Adding the term puts the slate back in the real 41-49 range.
    home_pts = average + (home_off - average) + (away_def - average) + hfa
    away_pts = average + (away_off - average) + (home_def - average)

    margin = home_pts - away_pts
    total = home_pts + away_pts

    home_win = win_probability(margin)
    market_win = no_vig(american_to_prob(market_home_ml),
                        american_to_prob(market_away_ml))

    # ---- spread ----
    spread_result: Dict[str, Any] = {
        "model_spread": round(-margin, 1),      # quoted from the home side
        "market_spread": market_spread,
    }
    if market_spread is not None:
        edge = margin + market_spread           # >0 means home is undervalued
        pick, why = spread_call(edge, market_spread)
        # edge is always HOME-signed. When it's negative enough to pick AWAY,
        # storing the raw value here made a real "AWAY" pick display next to
        # a negative edge_points -- reading as "recommends AWAY, edge says
        # HOME is undervalued", the same sign confusion the MLB moneyline had
        # (see _moneyline_edge in predict_match.py). Sign it to the picked
        # side once a side is actually picked; PASS has no side to sign to.
        edge_points = -edge if pick == "AWAY" else edge
        spread_result.update({
            "edge_points": round(edge_points, 2),
            "cover_prob": round(cover_probability(margin, market_spread), 4),
            "pick": pick, "note": why,
            "near_key_number": near_key_number(market_spread),
        })
    else:
        spread_result["note"] = "no market spread supplied -- no edge claimed"

    # ---- moneyline ----
    moneyline: Dict[str, Any] = {
        "home": home_key, "away": away_key,
        "home_win_probability": round(home_win, 4),
        "away_win_probability": round(1 - home_win, 4),
    }
    if market_win is not None:
        edge_pct = (home_win - market_win) * 100.0
        rec = ("BET HOME" if edge_pct >= 4 else
               "BET AWAY" if edge_pct <= -4 else "PASS")
        # Same fix as the spread block above and as MLB's _moneyline_edge:
        # edge_pct is always HOME-signed, so "BET AWAY" used to ship next to
        # a negative number -- sign it to the picked side once a side is
        # actually picked.
        display_edge_pct = -edge_pct if rec == "BET AWAY" else edge_pct
        moneyline.update({
            "market_home_prob": round(market_win, 4),
            "edge_pct": round(display_edge_pct, 1),
            "recommendation": rec,
            "note": ("" if abs(edge_pct) >= 4 else
                     "under 4 points of disagreement is model error, not an edge"),
        })
    else:
        moneyline["note"] = ("no market price supplied -- the probability is the "
                             "model's, and no edge is claimed against a price "
                             "that was not given")

    # ---- total ----
    total_result: Dict[str, Any] = {
        "model_total": round(total, 1),
        "market_total": market_total,
        "home_team_total": round(home_pts, 1),
        "away_team_total": round(away_pts, 1),
    }
    if market_total is not None:
        edge = total - market_total
        total_result.update({
            "edge_points": round(edge, 2),
            "pick": ("OVER" if edge >= MIN_EDGE_TOTAL else
                     "UNDER" if edge <= -MIN_EDGE_TOTAL else "PASS"),
            "note": ("" if abs(edge) >= MIN_EDGE_TOTAL else
                     f"edge {edge:+.1f} is under the {MIN_EDGE_TOTAL:g}-point floor"),
        })
    else:
        total_result["note"] = "no market total supplied -- no edge claimed"

    # ---- halftime ----
    home_1h_for = home_rec.get("points_1h_for")
    away_1h_for = away_rec.get("points_1h_for")
    has_real = (home_1h_for is not None and away_1h_for is not None
                and averages["has_real_1h"])
    if has_real:
        avg_1h = averages["points_1h"]
        # Same inverted sign as the full-game block above.
        home_1h = (avg_1h + (float(home_1h_for) - avg_1h)
                   + (float(away_rec.get("points_1h_against") or avg_1h) - avg_1h)
                   + hfa * FIRST_HALF_SHARE)
        away_1h = (avg_1h + (float(away_1h_for) - avg_1h)
                   + (float(home_rec.get("points_1h_against") or avg_1h) - avg_1h))
        source = "real first-half splits"
    else:
        home_1h = home_pts * FIRST_HALF_SHARE
        away_1h = away_pts * FIRST_HALF_SHARE
        source = (f"ESTIMATED at {FIRST_HALF_SHARE:.0%} of full game -- no 1H "
                  f"data in the store. Run ingest_nfl_schedule.py")
    margin_1h = home_1h - away_1h
    halftime = {
        "home_1h_points": round(home_1h, 1),
        "away_1h_points": round(away_1h, 1),
        "model_1h_total": round(home_1h + away_1h, 1),
        "home_1h_win_probability": round(win_probability(margin_1h, MARGIN_SD_1H), 4),
        "data_source": source,
        "data_tier": 1 if has_real else 3,
    }

    return {
        "sport": "nfl",
        "match": f"{home_key} vs {away_key}",
        "home": home_key, "away": away_key,
        "model_type": "points_model_v1",
        "spread": spread_result,
        "moneyline": moneyline,
        "total": total_result,
        "halftime": halftime,
        "inputs": {
            "home_off": round(home_off, 2), "home_def": round(home_def, 2),
            "away_off": round(away_off, 2), "away_def": round(away_def, 2),
            "league_avg_points": round(average, 2),
            "home_field_points": hfa,
            "margin_sd": MARGIN_SD,
        },
        # Every Week 1-4 prediction runs mostly on last season. Record how much,
        # so a November review can tell the model from the prior.
        "prior_blend": {
            "current_season_weight": round(weight, 3),
            "prior_regressed": is_prior,
            "regression_amount": PRIOR_REGRESSION if is_prior else 0.0,
            "home_games": home_games, "away_games": away_games,
            "store_seasons": sorted(seasons),
            "current_season": current_nfl_season(),
            "note": ("running on a PRIOR season, regressed toward the mean -- "
                     "treat this as a starting assumption, not a read on these "
                     "teams" if is_prior else "mostly current season"),
        },
    }


def describe(result: Dict[str, Any]) -> str:
    """A block a human can read without opening the JSON."""
    lines: List[str] = []
    spread, ml = result["spread"], result["moneyline"]
    total, half = result["total"], result["halftime"]
    blend = result["prior_blend"]

    lines.append(f"{result['away']}  at  {result['home']}")
    lines.append("-" * 74)
    lines.append(f"  model spread   {spread['model_spread']:+.1f}"
                 + (f"   market {spread['market_spread']:+.1f}"
                    f"   edge {spread.get('edge_points', 0):+.1f}"
                    if spread.get("market_spread") is not None else ""))
    if spread.get("pick"):
        lines.append(f"                 {spread['pick']}  ({spread['note']})")
    lines.append(f"  model total    {total['model_total']:.1f}"
                 + (f"   market {total['market_total']:.1f}"
                    f"   edge {total.get('edge_points', 0):+.1f}"
                    if total.get("market_total") is not None else ""))
    if total.get("pick"):
        lines.append(f"                 {total['pick']}"
                     + (f"  ({total['note']})" if total.get("note") else ""))
    lines.append(f"  team totals    {result['home']} {total['home_team_total']:.1f}"
                 f"   {result['away']} {total['away_team_total']:.1f}")
    lines.append(f"  moneyline      home {ml['home_win_probability']:.1%}"
                 + (f"   market {ml['market_home_prob']:.1%}"
                    f"   edge {ml['edge_pct']:+.1f}   {ml['recommendation']}"
                    if ml.get("market_home_prob") is not None else ""))
    if ml.get("note"):
        lines.append(f"                 {ml['note']}")
    lines.append(f"  first half     {half['home_1h_points']:.1f} - "
                 f"{half['away_1h_points']:.1f}   home ML "
                 f"{half['home_1h_win_probability']:.1%}")
    lines.append(f"                 {half['data_source']}")
    lines.append(f"  blend          {blend['current_season_weight']:.0%} current "
                 f"season   {blend['note']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(0)
    print(describe(predict_nfl_game(sys.argv[1], sys.argv[2])))
