#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
models/tennis_predictor.py — Reusable Tennis Match Predictor
==============================================================
Predicts tennis match outcomes using surface-specific Elo ratings.

Replaces the previous hardcoded-matchup heuristic with a data-driven
engine. Accepts any two player names and a surface, returns calibrated
probabilities — no hand-typed skill ratings, no fabricated props.

Usage:
    from models.tennis_predictor import predict_tennis_match
    result = predict_tennis_match("Novak Djokovic", "Carlos Alcaraz",
                                   surface="grass", best_of_5=True)
    print(result["moneyline"]["home_win_prob"])  # 0.55
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from models.tennis_elo import TennisElo

    # ingest_all_sports.py writes this from the ATP main-tour and Challenger
    # result feeds. Without it TennisElo only applies its small hardcoded
    # SEED_MATCHES list, so every rating is frozen at whenever that was written.
    # matches.csv holds ATP and WTA together. That is safe: Elo only moves a
    # rating through an actual result, and no ATP player has ever played a WTA
    # player, so the two pools never touch inside one file. atp_matches.csv is
    # still read as a fallback so an older store keeps working.
    _TENNIS_DIR = Path(__file__).resolve().parent.parent / "data" / "tennis"
    _ELO_CSV = next((p for p in (_TENNIS_DIR / "matches.csv",
                                 _TENNIS_DIR / "atp_matches.csv") if p.exists()), None)
    _ELO_ENGINE = TennisElo()
    if _ELO_CSV is not None:
        _ELO_MATCHES = _ELO_ENGINE.load_match_history(str(_ELO_CSV))
        print(f"[tennis_predictor] Elo built from {_ELO_MATCHES} real matches "
              f"({_ELO_CSV.name}).")
    else:
        _ELO_MATCHES = _ELO_ENGINE.load_match_history()
        print("[tennis_predictor] WARNING: data/tennis/matches.csv is missing, so Elo "
              "is running on built-in seed matches only -- every rating is frozen at "
              "whenever those were written. Fix: python ingest_tennis.py")
    HAS_ELO = True
except ImportError:
    HAS_ELO = False


# ============================================================================
# UTILITY
# ============================================================================

def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _prob_to_american(p: float) -> str:
    """Convert 0-1 probability to American odds string."""
    p = _clamp(p, 0.001, 0.999)
    if p >= 0.5:
        return str(-round((p / (1 - p)) * 100))
    return f"+{round(((1 - p) / p) * 100)}"


def _prob_to_conf(p: float) -> float:
    """Map win probability to confidence score (0-100)."""
    return round(_clamp(50.0 + abs(p - 0.5) * 150.0, 0.0, 98.0), 1)


def _american_to_decimal(s: str) -> float:
    v = int(s.replace("+", ""))
    return round(1 + (100 / abs(v)), 2) if v < 0 else round(1 + (v / 100), 2)


# ============================================================================
# RECOMMENDATION
# ============================================================================

def _recommendation(home_prob: float, market_prob: Optional[float] = None,
                    home_player: str = "Home", away_player: str = "Away") -> Dict[str, Any]:
    """Generate recommendation strings from probabilities.

    Bidirectional: `edge` here is the HOME side's edge (positive when the
    model likes home more than the market does), but a real, betsize-worthy
    edge can sit on EITHER side. This used to only ever test edge >= a
    positive threshold, so a large edge on the away player (edge very
    negative -- the model likes away far more than the market does) fell
    through every branch to "PASS - Market efficient" no matter how large
    it was -- tennis's moneyline could never recommend the away player, at
    all, ever. Mirrors predict_match.py's _moneyline_edge(), which already
    handles both directions for baseball: pick the side by sign, then
    display THAT side's edge (magnitude, positive by construction) instead
    of the raw home-signed number -- otherwise a correctly-recommended away
    pick prints with a misleading negative-looking edge, which is the exact
    bug that shipped as "LEAN St. Louis Cardinals ML (edge: -9.1%)" for MLB.
    """
    edge = (home_prob - (market_prob or 0.5)) * 100
    conf = _prob_to_conf(home_prob)

    if market_prob is not None:
        side = home_player if edge >= 0 else away_player
        magnitude = abs(edge)
        display_edge = magnitude
        # side/action_word/strength are returned as their own fields (not
        # just baked into `rec`) so a caller building a one-line verdict
        # (embed_builder.moneyline_verdict) can assemble one from clean
        # values instead of parsing this sentence back apart.
        if magnitude >= 4.5 and conf >= 63:
            action_word, strength = "BET", "strong"
        elif magnitude >= 2.0 and conf >= 57:
            action_word, strength = "LEAN", "moderate"
        elif magnitude >= 0.5:
            action_word, strength = "SLIGHT LEAN", "slight"
        else:
            action_word, strength = "PASS", None
        rec = (f"{action_word} {side} ML (edge: {display_edge:+.1f}%)"
               if action_word != "PASS" else "PASS - Market efficient")
        edge_pct = round(display_edge if magnitude >= 0.5 else edge, 1)
        rec_side = side if action_word != "PASS" else None
    else:
        rec = f"Model Prob: {home_prob:.1%}"
        edge_pct = round(edge, 1)
        action_word, strength, rec_side = None, None, None

    return {
        "recommendation": rec,
        "edge_pct": edge_pct,
        "confidence": conf,
        "action": action_word,
        "side": rec_side,
        "strength": strength,
    }


# ============================================================================
# SET DISTRIBUTION
# ============================================================================

def _set_rec(p_over_35: float, best_of_5: bool) -> str:
    """Text label for the sets-total O/U market.

    The line printed here has to key off best_of_5, not just the number --
    a best-of-3 match can only ever produce 2 or 3 sets, so "OVER 3.5 Sets"
    describes a result that cannot happen. p_over_35 was already computed
    correctly per format one level up (the caller branches on best_of_5
    when building it); this used to hardcode "3.5"/5-set wording onto that
    correct number regardless of format, which is what put best-of-5 set
    lines on WTA cards. Bo5's line is 3.5 (over = 4-5 sets, under = a 3-0
    sweep); Bo3's is 2.5 (over = 3 sets, under = a 2-0 sweep).
    """
    line = 3.5 if best_of_5 else 2.5
    sweep_sets = 3 if best_of_5 else 2
    if p_over_35 >= 0.55:
        return f"OVER {line} Sets -- P(over)={p_over_35:.0%}"
    elif p_over_35 <= 0.40:
        return f"UNDER {line} Sets -- P({sweep_sets} sets)={1-p_over_35:.0%}"
    return f"LEAN OVER {line} Sets -- P(over)={p_over_35:.0%}"


def _spread_rec(p_fav_spread: float, fav_name: str) -> str:
    if p_fav_spread >= 0.52:
        return f"{fav_name} -1.5 Sets -- P={p_fav_spread:.0%}"
    elif p_fav_spread >= 0.46:
        return f"LEAN {fav_name} -1.5 Sets -- P={p_fav_spread:.0%}"
    return f"TAKE Underdog +1.5 Sets -- P(fav covers)={p_fav_spread:.0%} only"


# ============================================================================
# MAIN PREDICTOR
# ============================================================================

def _total_games_projection(set_dist: Dict[str, float], home_prob: float,
                            best_of_5: bool) -> Dict[str, Any]:
    """Project total games, and the chance of going over the line.

    This used to be:

        "over_prob": round(p_over_35, 3)

    -- the probability of OVER 3.5 SETS, handed straight to the games market.
    Over 3.5 sets and over 22.5 games are correlated but they are not the same
    event, and reusing one number for both made them identical to three
    decimals in every prediction the model has ever produced.

    Games come from two things the set distribution already knows:

      how many SETS get played   -- weighted by the distribution
      how long each set runs     -- evenly matched players trade breaks and
                                    reach 6-4, 7-5, 7-6; a mismatch ends 6-2

    So expected games = expected sets x games per set, with games-per-set slid
    between about 10.4 (a coin flip) and 9.1 (a rout). The over probability is
    then a normal around that projection, which is an approximation -- the real
    distribution is lumpy because a set cannot end 6-5 -- but it is an
    approximation of the right quantity.
    """
    SETS_IN = {"3-0": 3, "3-1": 4, "3-2": 5, "0-3": 3, "1-3": 4, "2-3": 5,
               "2-0": 2, "2-1": 3, "0-2": 2, "1-2": 3}
    total_weight = sum(p for k, p in set_dist.items() if k in SETS_IN)
    if not total_weight:
        return {"line": 40.5 if best_of_5 else 22.5, "over_prob": None,
                "recommendation": "PASS",
                "note": "set distribution unreadable -- no games projection"}

    expected_sets = sum(p * SETS_IN[k] for k, p in set_dist.items()
                        if k in SETS_IN) / total_weight

    mismatch = min(abs(home_prob - 0.5) * 2.0, 1.0)      # 0 even, 1 lopsided

    # GAMES PER SET IS AN ASSUMPTION AND NEEDS FITTING FROM YOUR OWN RESULTS.
    # Set scores run 6-0 (6 games) to 7-6 (13), clustering on 6-4 and 6-3, so
    # the tour average sits near 9.5. Best-of-five matches run slightly longer
    # per set than best-of-three -- deeper into a match, more holds, more
    # tiebreaks -- which is why the base differs by format. The first pass at
    # 10.4 projected 26 games for an even best-of-three, against a market line
    # of 22.5; that was the tell.
    base = 9.8 if best_of_5 else 9.1
    games_per_set = base - 1.1 * mismatch

    expected_games = expected_sets * games_per_set
    line = 40.5 if best_of_5 else 22.5
    sd = 6.0 if best_of_5 else 4.2
    over_prob = 1.0 - 0.5 * (1.0 + math.erf((line - expected_games)
                                            / (sd * math.sqrt(2.0))))

    if over_prob >= 0.56:
        rec = "OVER"
    elif over_prob <= 0.44:
        rec = "UNDER"
    else:
        rec = "PASS"
    return {
        "line": line,
        "projected_games": round(expected_games, 1),
        "expected_sets": round(expected_sets, 2),
        "games_per_set": round(games_per_set, 2),
        "over_prob": round(over_prob, 3),
        "recommendation": rec,
        "data_tier": 2,
        "note": ("games-per-set is an unfitted assumption -- grade this market "
                 "before backing it"),
    }


def predict_tennis_match(
    home_player: str,
    away_player: str,
    *,
    surface: str = "grass",
    best_of_5: bool = True,
    tournament: Optional[str] = None,
    round_name: Optional[str] = None,
    market_prob: Optional[float] = None,
    market_home_odds: Optional[str] = None,
    market_away_odds: Optional[str] = None,
    elo_engine: Optional[TennisElo] = None,
) -> Dict[str, Any]:
    """Predict tennis match outcome using Elo ratings.

    Args:
        home_player: Name of player A (listed first).
        away_player: Name of player B (listed second).
        surface: Court surface ('hard', 'clay', 'grass').
        best_of_5: True for Grand Slams, False for best-of-3 tournaments.
        tournament: Optional tournament name for display.
        round_name: Optional round name for display.
        market_prob: Market-implied win probability for home_player (optional).
        market_home_odds: Market odds for home_player e.g. "-303" (optional).
        market_away_odds: Market odds for away_player e.g. "+237" (optional).
        elo_engine: Optional pre-loaded TennisElo instance. Creates default if None.

    Returns:
        Dict with keys: match, tournament, round, model_type,
                        moneyline, sets, total_games, dominance_ratio,
                        set_distribution, recommendation, notes.
    """
    engine = elo_engine or _ELO_ENGINE

    # Get win probability from Elo
    home_prob = engine.expected_win_prob(home_player, away_player, surface)
    away_prob = 1.0 - home_prob

    # Determine favorite
    if home_prob >= away_prob:
        fav_name, dog_name = home_player, away_player
        fav_prob, dog_prob = home_prob, away_prob
    else:
        fav_name, dog_name = away_player, home_player
        fav_prob, dog_prob = away_prob, home_prob

    # Set distribution
    sd = engine.set_distribution(home_prob, best_of_5=best_of_5)
    if best_of_5:
        p_over_35 = round(1.0 - sd["3-0"] - sd["0-3"], 3)
        p_fav_spread = round(
            sd["3-0"] + sd["3-1"] if fav_name == home_player else sd["0-3"] + sd["1-3"], 3
        )
    else:
        p_over_35 = round(1.0 - sd["2-0"] - sd["0-2"], 3)
        p_fav_spread = round(
            sd["2-0"] if fav_name == home_player else sd["0-2"], 3
        )

    # Dominance Ratio
    dr_home = engine.dominance_ratio(home_player, surface)
    dr_away = engine.dominance_ratio(away_player, surface)

    # Fair odds
    home_fair = _prob_to_american(home_prob)
    away_fair = _prob_to_american(away_prob)

    # Market data
    edge_rec = _recommendation(home_prob, market_prob, home_player, away_player)
    market_note = ""
    if market_prob is not None:
        edge_vs_market = (fav_prob - market_prob) * 100
        market_note = (
            f"Market prices {fav_name} at {market_prob:.1%} "
            f"({market_home_odds or 'N/A'}/{market_away_odds or 'N/A'}). "
            f"Model edge vs market: {edge_vs_market:+.1f}%"
        )

    # Player info from Elo
    home_elo = engine.get_rating(home_player, surface)
    away_elo = engine.get_rating(away_player, surface)
    home_matches = engine.get_match_count(home_player, surface)
    away_matches = engine.get_match_count(away_player, surface)

    fav_odds = _prob_to_american(fav_prob)
    dog_odds = _prob_to_american(dog_prob)

    notes = [
        f"Elo Ratings — {home_player}: {home_elo:.0f} ({home_matches} matches) | "
        f"{away_player}: {away_elo:.0f} ({away_matches} matches) on {surface}",
        f"DR: {home_player} {dr_home:.3f} | {away_player} {dr_away:.3f}",
        f"Surface: {surface.capitalize()} | Format: {'Best of 5' if best_of_5 else 'Best of 3'}",
    ]
    if market_note:
        notes.append(market_note)

    return {
        "match": f"{home_player} vs {away_player}",
        "tournament": tournament or "Tennis",
        "round": round_name or "",
        "model_type": "elo_surface",
        "moneyline": {
            "home": home_player,
            "away": away_player,
            "home_win_prob": round(home_prob, 4),
            "away_win_prob": round(away_prob, 4),
            "home_fair_odds": home_fair,
            "away_fair_odds": away_fair,
            "lean": home_player if home_prob >= 0.52 else (away_player if away_prob >= 0.52 else "coin_flip"),
            "confidence": edge_rec["confidence"],
            **edge_rec,
        },
        "market_home_odds": market_home_odds,
        "market_away_odds": market_away_odds,
        # The actual real-vs-model comparison hinges on this, not the odds
        # strings above -- run_tennis.py's whole call chain only ever passes
        # market_prob, never market_home_odds/market_away_odds, so a
        # consumer checking those two for "was there a real market" would
        # always see None even when --p1-ml/--p2-ml were given.
        "market_prob": market_prob,
        "sets": {
            "over_35_prob": p_over_35,
            "recommendation_sets_ou": _set_rec(p_over_35, best_of_5),
            "fav_spread_prob": p_fav_spread,
            "recommendation_spread": _spread_rec(p_fav_spread, fav_name),
        },
        "total_games": _total_games_projection(sd, home_prob, best_of_5),
        "set_distribution": sd,
        "dominance_ratio": {
            home_player: dr_home,
            away_player: dr_away,
        },
        "elo_ratings": {
            home_player: round(home_elo, 0),
            away_player: round(away_elo, 0),
        },
        "match_counts": {
            home_player: home_matches,
            away_player: away_matches,
        },
        "recommendation": edge_rec["recommendation"],
        "confidence": edge_rec["confidence"],
        "edge_pct": edge_rec["edge_pct"],
        "notes": notes,
    }