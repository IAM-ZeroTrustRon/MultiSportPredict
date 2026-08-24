#!/usr/bin/env python
"""
VPS vs FC Inter Turku - 2026 Finnish Cup Semi-Final
====================================================
Live Match Analytics Feed Script

Data Source: Sharp bettor consensus, H2H trends, form vectors
Match: VPS vs FC Inter Turku | Finnish Cup Semi-Final
Date: June 30, 2026 | Kickoff: 11:00 AM EDT
Venue: Lemonsoft Stadion (Hietalahti Stadium), Vaasa
Live Status: 27th minute, 0-0

Market Context:
- Pre-match: Inter Turku +100 (2.00) away favorite
- VPS: +225 (3.25) | Draw: +210 (3.10)
- Sharp lean: Draw / Under 2.5
"""

import sys
import json
import math
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

import pandas as pd

# Import the SoccerPredictor
from models.soccer_predictor import SoccerPredictor, get_league_config
from models.soccer_predictor import (
    team_goal_strength,
    team_btts_strength,
    team_corner_strength,
    estimate_team_goals,
    estimate_btts_prob,
    estimate_corner_total,
    poisson_over_prob,
    poisson_at_least_one,
    calculate_bivariate_poisson_probabilities,
    dixon_coles_xg_adjustment,
)

# Import core utilities
from core.utils import sigmoid, clamp


# ============================================================================
# MATCH DATA FROM PROVIDED ANALYTICS
# ============================================================================

MATCH_INFO = {
    "home_team": "VPS",
    "away_team": "FC Inter Turku",
    "competition": "Finnish Cup Semi-Final",
    "date": "2026-06-30",
    "venue": "Lemonsoft Stadion, Vaasa",
    "kickoff_edt": "11:00 AM",
    "live_minute": 27,
    "live_home_score": 0,
    "live_away_score": 0,
}

# Form vectors (derived from provided analytics)
VPS_DATA = {
    # Recent form: 5 consecutive wins, GD 36:5 (includes cup blowouts)
    # Competitive xG estimates derived from Veikkausliiga + cup form
    "xg_for": 2.20,           # Strong attack, tempered by H2H suppression
    "xg_against": 0.85,       # Very strong defense (5 GA in 5 matches)
    "shots": 15.0,            # Volume shooters in recent form
    "sot": 5.2,               # Quality chances
    "goals_for": 2.4,         # Actual goals per game (tempered from 7.2 avg)
    "goals_against": 0.7,     # Tight defense
    "clean_sheets": 6,        # 6 clean sheets in last 11 (10 W/D in 11)
    "missing_attacker": 0,    # No reported injuries
    "missing_creator": 0,
    "missing_cb": 0,
    "missing_gk": 0,
    "tempo": 0.35,            # Moderate tempo
    "width_crossing": 0.55,   # Use width
    "final_third_pressure": 0.50,
}

INTER_TURKU_DATA = {
    # Recent form: 4 wins in last 5, GD 19:7 (3.8 avg)
    # Incredible consistency: 18 W/D in last 19 matches
    "xg_for": 2.10,           # Strong attack
    "xg_against": 1.10,       # Solid defense (7 GA in 5 matches)
    "shots": 14.0,
    "sot": 4.8,
    "goals_for": 2.0,         # Actual goals per game
    "goals_against": 1.0,
    "clean_sheets": 5,        # Consistent defensive record
    "missing_attacker": 0,    # No reported injuries
    "missing_creator": 0,
    "missing_cb": 0,
    "missing_gk": 0,
    "tempo": 0.30,            # Controlled tempo
    "width_crossing": 0.50,
    "final_third_pressure": 0.45,
}

# H2H context (from provided data)
H2H_CONTEXT = {
    "last_meeting_score": "0-0 (April 4, 2026, Veikkausliiga)",
    "avg_goals_per_h2h": 1.00,   # Last 5 H2Hs avg exactly 1.00 goals
    "h2h_cautious_factor": 0.70,  # H2H suppression factor (1.0 = neutral)
}

# Market consensus (from provided sharp data)
MARKET_CONSENSUS = {
    "pre_match_moneyline": {
        "VPS": 3.25,          # +225
        "Draw": 3.10,         # +210
        "Inter Turku": 2.00,  # +100
    },
    "market_total": 2.5,
    "sharp_lean": "Draw / Under 2.5",
    "knockout_factor": 0.85,  # Semi-final knockout suppression (lower = fewer goals)
}


# ============================================================================
# COMPREHENSIVE PREDICTION ENGINE
# ============================================================================

def run_comprehensive_analysis() -> Dict[str, Any]:
    """Run full analysis feeding provided match data into the model."""

    print("=" * 80)
    print("  2026 FINNISH CUP SEMI-FINAL - LIVE MATCH ANALYTICS")
    print(f"  {MATCH_INFO['home_team']} vs {MATCH_INFO['away_team']}")
    print(f"  {MATCH_INFO['competition']} | {MATCH_INFO['date']}")
    print(f"  Venue: {MATCH_INFO['venue']}")
    print(f"  Live: {MATCH_INFO['live_minute']}' | Score: {MATCH_INFO['live_home_score']}-{MATCH_INFO['live_away_score']}")
    print("=" * 80)
    print()

    # ------------------------------------------------------------------
    # 1. Team Offensive/Defensive Analysis
    # ------------------------------------------------------------------
    print("1. TEAM OFFENSIVE/DEFENSIVE ANALYSIS")
    print("-" * 40)
    
    for team_name, data in [("VPS", VPS_DATA), ("FC Inter Turku", INTER_TURKU_DATA)]:
        print(f"   {team_name}:")
        print(f"      xG For: {data['xg_for']:.2f} | xG Against: {data['xg_against']:.2f}")
        print(f"      Goals For: {data['goals_for']:.1f} | Goals Against: {data['goals_against']:.1f}")
        print(f"      Shots: {data['shots']:.0f} | SoT: {data['sot']:.0f}")
        print(f"      Clean Sheets (last 11/19): {data['clean_sheets']}")
        print()

    # ------------------------------------------------------------------
    # 2. Goal Strength Analysis
    # ------------------------------------------------------------------
    print("2. GOAL STRENGTH ANALYSIS")
    print("-" * 40)

    home_goal_strength = team_goal_strength(
        VPS_DATA['xg_for'], VPS_DATA['xg_against'], VPS_DATA['shots'], VPS_DATA['sot'],
        VPS_DATA['goals_for'], VPS_DATA['goals_against'], VPS_DATA['tempo'], 1,
        VPS_DATA['missing_attacker'], VPS_DATA['missing_creator'],
        VPS_DATA['missing_cb'], VPS_DATA['missing_gk']
    )
    away_goal_strength = team_goal_strength(
        INTER_TURKU_DATA['xg_for'], INTER_TURKU_DATA['xg_against'],
        INTER_TURKU_DATA['shots'], INTER_TURKU_DATA['sot'],
        INTER_TURKU_DATA['goals_for'], INTER_TURKU_DATA['goals_against'],
        INTER_TURKU_DATA['tempo'], 0,
        INTER_TURKU_DATA['missing_attacker'], INTER_TURKU_DATA['missing_creator'],
        INTER_TURKU_DATA['missing_cb'], INTER_TURKU_DATA['missing_gk']
    )

    print(f"   VPS Goal Strength:          {home_goal_strength:+.3f}")
    print(f"   FC Inter Turku Goal Strength: {away_goal_strength:+.3f}")
    print()

    # ------------------------------------------------------------------
    # 3. Goal Projections (with H2H + Cup Knockout Adjustments)
    # ------------------------------------------------------------------
    print("3. PROJECTED GOALS (BIVARIATE POISSON)")
    print("-" * 40)

    # Dixon-Coles adjustment
    home_attack, home_defense = dixon_coles_xg_adjustment(
        VPS_DATA['xg_for'], VPS_DATA['xg_against'],
        INTER_TURKU_DATA['xg_for'], INTER_TURKU_DATA['xg_against']
    )
    away_attack, away_defense = dixon_coles_xg_adjustment(
        INTER_TURKU_DATA['xg_for'], INTER_TURKU_DATA['xg_against'],
        VPS_DATA['xg_for'], VPS_DATA['xg_against']
    )

    # Base lambda estimates
    home_lambda = estimate_team_goals(
        VPS_DATA['xg_for'], VPS_DATA['sot'], VPS_DATA['tempo'], 1,
        VPS_DATA['missing_attacker'], VPS_DATA['missing_creator'],
        INTER_TURKU_DATA['xg_against'], INTER_TURKU_DATA['missing_cb'],
        INTER_TURKU_DATA['missing_gk']
    )
    away_lambda = estimate_team_goals(
        INTER_TURKU_DATA['xg_for'], INTER_TURKU_DATA['sot'],
        INTER_TURKU_DATA['tempo'], 0,
        INTER_TURKU_DATA['missing_attacker'], INTER_TURKU_DATA['missing_creator'],
        VPS_DATA['xg_against'], VPS_DATA['missing_cb'], VPS_DATA['missing_gk']
    )

    # Apply league config (Finnish Cup -> use default with cup-style suppression)
    finnish_cup_config = {
        'goal_variance': 0.90,       # Cup knockout = lower variance
        'avg_goals_per_game': 2.30,  # Finnish league avg ~2.4, cup lower
        'home_advantage': 0.30,
        'draw_rate': 0.32,           # Cup draws (go to ET/pens)
    }
    home_lambda *= finnish_cup_config['goal_variance']
    away_lambda *= finnish_cup_config['goal_variance']

    # Apply H2H suppression (avg 1.00 goals per match in last 5 H2Hs)
    h2h_suppression = H2H_CONTEXT['h2h_cautious_factor']
    home_lambda *= h2h_suppression
    away_lambda *= h2h_suppression

    # Apply knockout semi-final suppression
    knockout_factor = MARKET_CONSENSUS['knockout_factor']
    home_lambda *= knockout_factor
    away_lambda *= knockout_factor

    # Home advantage
    home_lambda *= (1 + finnish_cup_config['home_advantage'] * 0.1)

    total_lambda = home_lambda + away_lambda

    print(f"   VPS Expected Goals (xG):      {home_lambda:.3f}")
    print(f"   FC Inter Turku Expected Goals (xG): {away_lambda:.3f}")
    print(f"   Match Total Expected Goals:  {total_lambda:.3f}")
    print(f"   (Adjusted for: H2H x{h2h_suppression}, Cup KO x{knockout_factor})")
    print()

    # ------------------------------------------------------------------
    # 4. Match Outcome Probabilities
    # ------------------------------------------------------------------
    print("4. MATCH OUTCOME PROBABILITIES")
    print("-" * 40)

    prob_matrix = calculate_bivariate_poisson_probabilities(home_lambda, away_lambda)

    home_win_prob = prob_matrix.apply(
        lambda row: row[row.index < row.name].sum(), axis=1
    ).sum()
    away_win_prob = prob_matrix.apply(
        lambda row: row[row.index > row.name].sum(), axis=1
    ).sum()
    draw_prob = prob_matrix.apply(
        lambda row: row[row.index == row.name].sum(), axis=1
    ).sum()

    # Normalize
    total_prob = home_win_prob + away_win_prob + draw_prob
    if total_prob > 0:
        home_win_prob /= total_prob
        away_win_prob /= total_prob
        draw_prob /= total_prob

    print(f"   VPS Win:         {home_win_prob:.1%}  (Pre-market: {1/3.25:.1%})")
    print(f"   Draw:            {draw_prob:.1%}  (Pre-market: {1/3.10:.1%})")
    print(f"   FC Inter Turku:  {away_win_prob:.1%}  (Pre-market: {1/2.00:.1%})")
    print()

    # Edge calculation vs market
    home_edge = home_win_prob - (1 / MARKET_CONSENSUS['pre_match_moneyline']['VPS'])
    draw_edge = draw_prob - (1 / MARKET_CONSENSUS['pre_match_moneyline']['Draw'])
    away_edge = away_win_prob - (1 / MARKET_CONSENSUS['pre_match_moneyline']['Inter Turku'])

    print(f"   Edge vs Market:")
    print(f"      VPS:   {home_edge:+.1%}")
    print(f"      Draw:  {draw_edge:+.1%}")
    print(f"      Inter: {away_edge:+.1%}")

    best_side = max(
        [("VPS", home_edge), ("Draw", draw_edge), ("Inter Turku", away_edge)],
        key=lambda x: x[1]
    )
    print(f"   >> Sharp Side Lean: {best_side[0]} (edge: {best_side[1]:+.1%})")
    print()

    # ------------------------------------------------------------------
    # 5. Total Goals Analysis (Over/Under)
    # ------------------------------------------------------------------
    print("5. TOTAL GOALS ANALYSIS (OVER/UNDER)")
    print("-" * 40)

    market_total = MARKET_CONSENSUS['market_total']
    p_over_15 = poisson_over_prob(total_lambda, 1.5)
    p_over_25 = poisson_over_prob(total_lambda, 2.5)
    p_over_35 = poisson_over_prob(total_lambda, 3.5)
    p_over_45 = poisson_over_prob(total_lambda, 4.5)

    print(f"   Expected Total Goals: {total_lambda:.3f}")
    print(f"   Market Total Line:    {market_total:.1f}")
    print(f"   Edge vs {market_total}: {total_lambda - market_total:+.3f}")
    print()
    print(f"   Over 1.5: {p_over_15:.1%}")
    print(f"   Over 2.5: {p_over_25:.1%}")
    print(f"   Over 3.5: {p_over_35:.1%}")
    print(f"   Over 4.5: {p_over_45:.1%}")
    print()

    # Under probability for the 2.5 market
    p_under_25 = 1 - p_over_25
    under_edge = p_under_25 - 0.5  # Rough even-money line
    print(f"   Under 2.5: {p_under_25:.1%} (edge vs 50%: {under_edge:+.1%})")

    if total_lambda < market_total:
        total_lean = "UNDER"
        total_edge_val = market_total - total_lambda
    else:
        total_lean = "OVER"
        total_edge_val = total_lambda - market_total
    print(f"   >> Total Lean: {total_lean} {market_total} (edge: {total_edge_val:+.3f} goals)")
    print()

    # ------------------------------------------------------------------
    # 6. BTTS (Both Teams to Score)
    # ------------------------------------------------------------------
    print("6. BOTH TEAMS TO SCORE (BTTS)")
    print("-" * 40)

    home_btts = team_btts_strength(
        VPS_DATA['xg_for'], VPS_DATA['xg_against'],
        VPS_DATA['goals_for'], VPS_DATA['goals_against'],
        VPS_DATA['sot'], VPS_DATA['tempo'], VPS_DATA['final_third_pressure'],
        VPS_DATA['missing_attacker'], VPS_DATA['missing_cb'],
        VPS_DATA['missing_gk'], VPS_DATA['clean_sheets']
    )
    away_btts = team_btts_strength(
        INTER_TURKU_DATA['xg_for'], INTER_TURKU_DATA['xg_against'],
        INTER_TURKU_DATA['goals_for'], INTER_TURKU_DATA['goals_against'],
        INTER_TURKU_DATA['sot'], INTER_TURKU_DATA['tempo'],
        INTER_TURKU_DATA['final_third_pressure'],
        INTER_TURKU_DATA['missing_attacker'], INTER_TURKU_DATA['missing_cb'],
        INTER_TURKU_DATA['missing_gk'], INTER_TURKU_DATA['clean_sheets']
    )
    btts_prob = estimate_btts_prob(home_lambda, away_lambda, home_btts, away_btts)

    btts_yes_edge = btts_prob - 0.5
    print(f"   BTTS Yes: {btts_prob:.1%} (edge vs 50%: {btts_yes_edge:+.1%})")
    print(f"   BTTS No:  {(1-btts_prob):.1%}")
    btts_lean = "BTTS YES" if btts_prob > 0.50 else "BTTS NO"
    print(f"   >> BTTS Lean: {btts_lean}")
    print()

    # ------------------------------------------------------------------
    # 7. Corner Projection
    # ------------------------------------------------------------------
    print("7. CORNER ANALYSIS")
    print("-" * 40)

    home_corner = team_corner_strength(
        VPS_DATA['shots'], VPS_DATA['sot'], VPS_DATA['final_third_pressure'],
        VPS_DATA['width_crossing'], VPS_DATA['tempo'], 1,
        VPS_DATA['missing_cb'], VPS_DATA['missing_gk'], VPS_DATA['missing_attacker']
    )
    away_corner = team_corner_strength(
        INTER_TURKU_DATA['shots'], INTER_TURKU_DATA['sot'],
        INTER_TURKU_DATA['final_third_pressure'],
        INTER_TURKU_DATA['width_crossing'], INTER_TURKU_DATA['tempo'], 0,
        INTER_TURKU_DATA['missing_cb'], INTER_TURKU_DATA['missing_gk'],
        INTER_TURKU_DATA['missing_attacker']
    )
    corner_total = estimate_corner_total(home_corner, away_corner, 0, 0, 0, 0)

    p_corners_85 = poisson_over_prob(corner_total, 8.5)
    p_corners_95 = poisson_over_prob(corner_total, 9.5)
    p_corners_105 = poisson_over_prob(corner_total, 10.5)

    print(f"   Projected Total Corners: {corner_total:.1f}")
    print(f"   Over 8.5:  {p_corners_85:.1%}")
    print(f"   Over 9.5:  {p_corners_95:.1%}")
    print(f"   Over 10.5: {p_corners_105:.1%}")
    print()

    # ------------------------------------------------------------------
    # 8. Live State Integration
    # ------------------------------------------------------------------
    print("8. LIVE STATE (27TH MINUTE, 0-0)")
    print("-" * 40)

    # At 27 minutes, ~30% of match elapsed
    elapsed_ratio = MATCH_INFO['live_minute'] / 90.0
    remaining_ratio = 1 - elapsed_ratio

    # Scale expected goals for remaining time
    remaining_home_lambda = home_lambda * remaining_ratio
    remaining_away_lambda = away_lambda * remaining_ratio
    remaining_total_lambda = total_lambda * remaining_ratio

    # Probability of 0-0 final (both teams fail to score in remaining time)
    p_home_score_rest = poisson_at_least_one(remaining_home_lambda)
    p_away_score_rest = poisson_at_least_one(remaining_away_lambda)
    p_scoreless_rest = (1 - p_home_score_rest) * (1 - p_away_score_rest)

    print(f"   Elapsed: {MATCH_INFO['live_minute']}' ({elapsed_ratio:.1%})")
    print(f"   Remaining expected goals:")
    print(f"      VPS (rest of match):      {remaining_home_lambda:.3f}")
    print(f"      Inter Turku (rest of match): {remaining_away_lambda:.3f}")
    print(f"      Total (rest of match):    {remaining_total_lambda:.3f}")
    print()
    print(f"   Probability of final score 0-0: {p_scoreless_rest:.1%}")
    print(f"   Probability of at least 1 goal: {(1-p_scoreless_rest):.1%}")
    print()

    # ------------------------------------------------------------------
    # 9. Betting Recommendations
    # ------------------------------------------------------------------
    print("9. BETTING RECOMMENDATIONS")
    print("-" * 40)

    # Moneyline
    best_bet = max(
        [
            ("VPS ML (+225)", home_win_prob, home_edge, 1/3.25),
            ("Draw (+210)", draw_prob, draw_edge, 1/3.10),
            ("Inter Turku ML (+100)", away_win_prob, away_edge, 1/2.00),
        ],
        key=lambda x: x[2]
    )

    # Total
    total_rec = f"{total_lean} {market_total}" if abs(total_edge_val) > 0.10 else "PASS"

    # BTTS
    btts_rec = f"{'BTTS Yes' if btts_prob > 0.50 else 'BTTS No'} (conf: {abs(btts_prob-0.5)/0.5:.0%})"

    print(f"   >> BEST SIDE:  {best_bet[0]}")
    print(f"      Model Prob: {best_bet[1]:.1%} | Market Imp: {best_bet[3]:.1%} | Edge: {best_bet[2]:+.1%}")
    print()
    print(f"   >> TOTAL:      {total_rec}")
    print(f"      Model Total: {total_lambda:.3f} | Market: {market_total}")
    print()
    print(f"   >> BTTS:       {btts_rec}")
    print()

    # ------------------------------------------------------------------
    # 10. Sharp Consensus Summary
    # ------------------------------------------------------------------
    print("10. SHARP CONSENSUS SUMMARY")
    print("-" * 40)
    print(f"    Pre-Market Fave:  Inter Turku (+100 / 2.00)")
    print(f"    Live Score:       {MATCH_INFO['live_home_score']}-{MATCH_INFO['live_away_score']} ({MATCH_INFO['live_minute']}')")
    print(f"    H2H Context:      Last meeting 0-0 (Apr 4), avg 1.00 goals last 5 H2Hs")
    print(f"    Cup Context:      Semi-final - both teams risk-averse")
    print(f"    Sharp Lean:       {MARKET_CONSENSUS['sharp_lean']}")
    print()

    # Build output dict
    result = {
        "match": MATCH_INFO,
        "team_data": {
            "VPS": VPS_DATA,
            "FC Inter Turku": INTER_TURKU_DATA,
        },
        "h2h_context": H2H_CONTEXT,
        "market": MARKET_CONSENSUS,
        "model_output": {
            "home_lambda": round(home_lambda, 4),
            "away_lambda": round(away_lambda, 4),
            "total_lambda": round(total_lambda, 4),
            "home_win_prob": round(home_win_prob, 4),
            "draw_prob": round(draw_prob, 4),
            "away_win_prob": round(away_win_prob, 4),
            "home_edge": round(home_edge, 4),
            "draw_edge": round(draw_edge, 4),
            "away_edge": round(away_edge, 4),
            "btts_prob": round(btts_prob, 4),
            "corner_projection": round(corner_total, 1),
            "over_25_prob": round(p_over_25, 4),
            "under_25_prob": round(p_under_25, 4),
            "scoreless_rest_prob": round(p_scoreless_rest, 4),
        },
        "recommendations": {
            "best_side": {
                "pick": best_bet[0],
                "model_prob": round(best_bet[1], 4),
                "edge": round(best_bet[2], 4),
            },
            "total": total_rec,
            "btts": btts_rec,
            "sharp_consensus": MARKET_CONSENSUS['sharp_lean'],
        }
    }

    # Save to JSON
    output_dir = Path("output/soccer")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "VPS_vs_FC_Inter_Turku_finnish_cup_2026_06_30.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"   Full analysis saved to: {output_path}")
    print()

    return result


# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    run_comprehensive_analysis()