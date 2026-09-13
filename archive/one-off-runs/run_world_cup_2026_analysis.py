#!/usr/bin/env python
"""
2026 World Cup Match Analysis
==============================
Uses real squad metrics for Canada, Qatar, Mexico, and South Korea.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from soccer.world_cup_2026_squads import get_matchup_context, load_world_cup_squad_metrics, get_team_attack_profile
from models.soccer_predictor import (
    get_league_config,
    poisson_over_prob,
    estimate_team_goals,
    estimate_btts_prob,
    team_goal_strength,
    team_btts_strength,
    team_corner_strength,
    estimate_corner_total,
)
from core.confidence_engine import confidence_score, bet_recommendation
from soccer.soccer_predict_game import fetch_soccer_ref_data
import pandas as pd


def get_team_data_from_profile(team_name, is_home=True):
    """
    Convert squad profile to the team data format expected by the model.
    """
    profile = get_team_attack_profile(team_name)
    if profile is None:
        return None

    # Map profile data to model inputs
    # Shots and SoT per 90 -> use avg_sot_per_90 * 2.5 as rough proxy for shots
    shots = profile['avg_shots_per_90']
    sot = profile['avg_sot_per_90']
    xg_for = sot * 0.15  # rough conversion: 15% of SoT become goals
    xg_against = profile['sot_allowed_per_90'] * 0.12  # opponent conversion

    # Goals scored/allowed per game (from shots/SoT)
    goals_for = xg_for * 1.1  # slight finishing boost
    goals_against = xg_against * 1.05

    data = {
        'xg_for': round(xg_for, 2),
        'xg_against': round(xg_against, 2),
        'shots': round(shots, 1),
        'sot': round(sot, 1),
        'goals_for': round(goals_for, 2),
        'goals_against': round(goals_against, 2),
        'clean_sheets': 2,  # placeholder
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.30 if is_home else 0.25,
        'width_crossing': 0.55,
        'final_third_pressure': round(profile['avg_box_touches'] / 10, 2),
        'corners_for': 5.5,
        'corners_against': profile['shots_allowed_per_90'] * 0.35,
        'possession_pct': profile['avg_possession_pct'],
        'corner_gen_style': 'possession' if profile['avg_possession_pct'] > 50 else 'counter',
    }

    return data


def analyze_world_cup_match(home_team, away_team, league="World_Cup"):
    """
    Run full analysis for a World Cup match using real squad data.
    """
    print(f"\n{'='*80}")
    print(f"2026 WORLD CUP ANALYSIS: {home_team} vs {away_team}")
    print(f"League: {league}")
    print(f"{'='*80}\n")

    # Load real squad data
    print("--- Loading Real Squad Metrics ---")
    home_data = get_team_data_from_profile(home_team, is_home=True)
    away_data = get_team_data_from_profile(away_team, is_home=False)

    if home_data is None or away_data is None:
        print(f"Error: Could not load squad data for {home_team} or {away_team}")
        return None

    print(f"Home ({home_team}):")
    print(f"  xG For: {home_data['xg_for']:.2f} | xG Against: {home_data['xg_against']:.2f}")
    print(f"  Shots: {home_data['shots']:.1f} | SoT: {home_data['sot']:.1f}")
    print(f"  Possession: {home_data['possession_pct']:.1f}%")
    print()
    print(f"Away ({away_team}):")
    print(f"  xG For: {away_data['xg_for']:.2f} | xG Against: {away_data['xg_against']:.2f}")
    print(f"  Shots: {away_data['shots']:.1f} | SoT: {away_data['sot']:.1f}")
    print(f"  Possession: {away_data['possession_pct']:.1f}%")
    print()

    # Get referee data
    ref_data = fetch_soccer_ref_data(home_team, away_team)

    # Calculate expected goals
    home_lam = estimate_team_goals(
        home_data['xg_for'], home_data['sot'], home_data['tempo'], 1,
        home_data['missing_attacker'], home_data['missing_creator'],
        away_data['xg_against'], away_data['missing_cb'], away_data['missing_gk']
    )
    away_lam = estimate_team_goals(
        away_data['xg_for'], away_data['sot'], away_data['tempo'], 0,
        away_data['missing_attacker'], away_data['missing_creator'],
        home_data['xg_against'], home_data['missing_cb'], home_data['missing_gk']
    )

    # Apply league config
    config = get_league_config(league)
    home_lam *= config.get('goal_variance', 1.0)
    away_lam *= config.get('goal_variance', 1.0)
    home_lam *= (1 + config.get('home_advantage', 0.05) * 0.1)

    total_lam = home_lam + away_lam

    # BTTS probability
    btts_prob = estimate_btts_prob(home_data['xg_for'], away_data['xg_for'], 0, 0)

    # Corners analysis
    home_corner_strength = team_corner_strength(
        home_data['shots'], home_data['sot'], home_data['final_third_pressure'],
        home_data['width_crossing'], home_data['tempo'], 1,
        home_data['missing_cb'], home_data['missing_gk'], home_data['missing_attacker']
    )
    away_corner_strength = team_corner_strength(
        away_data['shots'], away_data['sot'], away_data['final_third_pressure'],
        away_data['width_crossing'], away_data['tempo'], 0,
        away_data['missing_cb'], away_data['missing_gk'], away_data['missing_attacker']
    )
    corner_total = estimate_corner_total(
        home_corner_strength, away_corner_strength,
        0, 0, 0, 0
    )

    # Recalibrated corners
    home_corners_recal = (home_data['corners_for'] + away_data['corners_against']) / 2
    away_corners_recal = (away_data['corners_for'] + home_data['corners_against']) / 2
    recalibrated_total = home_corners_recal + away_corners_recal
    blended_corner_total = 0.6 * recalibrated_total + 0.4 * corner_total

    # Probabilities
    p_over_15 = poisson_over_prob(total_lam, 1.5)
    p_over_25 = poisson_over_prob(total_lam, 2.5)
    p_corners_95 = poisson_over_prob(blended_corner_total, 9.5)

    # Match outcome
    home_win_prob = home_lam / (home_lam + away_lam) * 0.85 + 0.10
    away_win_prob = away_lam / (home_lam + away_lam) * 0.05 + 0.05
    draw_prob = 1 - home_win_prob - away_win_prob

    # Recommendations
    corners_edge = blended_corner_total - 9.5
    corners_confidence = confidence_score(corners_edge, volatility=0.60)
    corners_rec = bet_recommendation(corners_confidence)

    dc_home_or_draw = home_win_prob + draw_prob
    dc_home_confidence = confidence_score((dc_home_or_draw - 0.75) * 100, volatility=0.52)
    dc_home_rec = bet_recommendation(dc_home_confidence)

    btts_confidence = confidence_score((btts_prob - 0.50) * 100, volatility=0.48)
    btts_rec = bet_recommendation(btts_confidence)

    # Print results
    print(f"Projected Score: {home_team} {home_lam:.1f} - {away_lam:.1f} {away_team}")
    print(f"Projected Total Goals: {total_lam:.2f}")
    print(f"\nGoal Probabilities:")
    print(f"  Over 1.5: {p_over_15:.1%}")
    print(f"  Over 2.5: {p_over_25:.1%}")
    print(f"\nMatch Outcome:")
    print(f"  {home_team} Win: {home_win_prob:.1%}")
    print(f"  Draw: {draw_prob:.1%}")
    print(f"  {away_team} Win: {away_win_prob:.1%}")
    print(f"\nCorners Analysis:")
    print(f"  Projected Total: {blended_corner_total:.1f}")
    print(f"  Over 9.5: {p_corners_95:.1%}")
    print(f"  Confidence: {corners_confidence:.1f}%")
    print(f"  Recommendation: {corners_rec}")
    print(f"\nBTTS Probability: {btts_prob:.1%} (Confidence: {btts_confidence:.1f}%)")
    print(f"\nDouble Chance (Home or Draw): {dc_home_or_draw:.1%} (Confidence: {dc_home_confidence:.1f}%)")
    print(f"  Recommendation: {dc_home_rec}")

    print(f"\n=== BEST PROP BETS ===")
    print(f"1. Over 9.5 Corners — {corners_rec}")
    print(f"2. Double Chance (Home or Draw) — {dc_home_rec}")
    print(f"3. BTTS Yes — {btts_rec}")
    print(f"4. Over 2.5 Goals — {'strong support' if p_over_25 > 0.60 else 'moderate'} ({p_over_25:.1%})")

    return {
        'home_team': home_team,
        'away_team': away_team,
        'projected_score': f"{home_lam:.1f}-{away_lam:.1f}",
        'total_goals': round(total_lam, 2),
        'over_25_prob': round(p_over_25, 3),
        'btts_prob': round(btts_prob, 3),
        'home_win_prob': round(home_win_prob, 3),
        'draw_prob': round(draw_prob, 3),
        'away_win_prob': round(away_win_prob, 3),
        'corners': {
            'projected_total': round(blended_corner_total, 1),
            'over_95_prob': round(p_corners_95, 3),
            'confidence': round(corners_confidence, 1),
            'recommendation': corners_rec,
        },
        'recommendations': {
            'corners': corners_rec,
            'double_chance': dc_home_rec,
            'btts': btts_rec,
        }
    }


if __name__ == "__main__":
    # Analyze Canada vs Qatar
    canada_qatar = analyze_world_cup_match("Canada", "Qatar", league="World_Cup_Group_B")

    # Analyze Mexico vs South Korea
    mexico_korea = analyze_world_cup_match("Mexico", "South Korea", league="World_Cup_Group_B")

    print("\n" + "="*80)
    print("WORLD CUP 2026 — analysis complete")
    print("="*80)