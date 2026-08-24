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
    _ELO_ENGINE = TennisElo()
    _ELO_ENGINE.load_match_history()
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

def _recommendation(home_prob: float, market_prob: Optional[float] = None) -> Dict[str, Any]:
    """Generate recommendation strings from probabilities."""
    edge = (home_prob - (market_prob or 0.5)) * 100
    conf = _prob_to_conf(home_prob)

    if market_prob is not None:
        if edge >= 4.5 and conf >= 63:
            rec = f"BET Home ML (edge: {edge:+.1f}%)"
        elif edge >= 2.0 and conf >= 57:
            rec = f"LEAN Home ML (edge: {edge:+.1f}%)"
        elif edge >= 0.5:
            rec = f"SLIGHT LEAN Home ML (edge: {edge:+.1f}%)"
        else:
            rec = "PASS - Market efficient"
    else:
        rec = f"Model Prob: {home_prob:.1%}"

    return {
        "recommendation": rec,
        "edge_pct": round(edge, 1),
        "confidence": conf,
    }


# ============================================================================
# SET DISTRIBUTION
# ============================================================================

def _set_rec(p_over_35: float) -> str:
    if p_over_35 >= 0.55:
        return f"OVER 3.5 Sets -- P(over)={p_over_35:.0%}"
    elif p_over_35 <= 0.40:
        return f"UNDER 3.5 Sets -- P(3 or 4 sets)={1-p_over_35:.0%}"
    return f"LEAN OVER 3.5 Sets -- P(over)={p_over_35:.0%}"


def _spread_rec(p_fav_spread: float, fav_name: str) -> str:
    if p_fav_spread >= 0.52:
        return f"{fav_name} -1.5 Sets -- P={p_fav_spread:.0%}"
    elif p_fav_spread >= 0.46:
        return f"LEAN {fav_name} -1.5 Sets -- P={p_fav_spread:.0%}"
    return f"TAKE Underdog +1.5 Sets -- P(fav covers)={p_fav_spread:.0%} only"


# ============================================================================
# MAIN PREDICTOR
# ============================================================================

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
    edge_rec = _recommendation(home_prob, market_prob)
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
        "sets": {
            "over_35_prob": p_over_35,
            "recommendation_sets_ou": _set_rec(p_over_35),
            "fav_spread_prob": p_fav_spread,
            "recommendation_spread": _spread_rec(p_fav_spread, fav_name),
        },
        "total_games": {
            # Total games estimate based on set distribution
            # For best-of-5: typical 3-set = ~30 games, 4-set = ~38, 5-set = ~45
            "line": 40.5 if best_of_5 else 22.5,
            "over_prob": round(p_over_35, 3),
            "recommendation": "OVER" if p_over_35 >= 0.53 else "UNDER",
        },
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