#!/usr/bin/env python
"""
MEXICO vs ENGLAND - 2026 WORLD CUP COMPREHENSIVE ANALYSIS
=========================================================
Full statistical breakdown with squad metrics, goal projections,
corner analysis, BTTS, and betting recommendations.
"""

import sys
import json
import math
from datetime import datetime
from pathlib import Path

# Add England to squad data and run analysis
import pandas as pd
from soccer.world_cup_2026_squads import load_world_cup_squad_metrics, get_team_attack_profile

# Extend squad data to include England
def load_extended_world_cup_squad_data():
    """
    Load base squad data and extend with England squad metrics.
    """
    players, defenses = load_world_cup_squad_metrics()
    
    # --- ENGLAND SQUAD DATA (World Cup 2026) ---
    england_players = pd.DataFrame({
        'player_name': [
            'Harry Kane', 'Bukayo Saka', 'Jude Bellingham', 'Phil Foden',
            'Declan Rice', 'Cole Palmer', 'Marcus Rashford', 'Jack Grealish',
        ],
        'team': ['England'] * 8,
        'position': ['FW', 'RW', 'AM/CM', 'LW/AM', 'DM', 'RW/AM', 'LW/FW', 'LW'],
        '90s_played': [14.0, 12.5, 13.0, 11.0, 15.0, 10.5, 9.0, 8.5],
        'shots_per_90': [3.80, 2.95, 2.60, 2.85, 0.75, 2.50, 2.30, 1.95],
        'sot_per_90': [1.85, 1.40, 1.05, 1.20, 0.20, 1.10, 0.95, 0.75],
        'shot_accuracy_pct': [48.7, 47.5, 40.4, 42.1, 26.7, 44.0, 41.3, 38.5],
        'touches_in_box_per_90': [7.2, 5.8, 4.5, 5.2, 1.0, 4.8, 4.2, 3.8],
        'takes_free_kicks': [1, 0, 1, 1, 0, 1, 0, 0],
    })
    
    england_defense = pd.DataFrame({
        'team_name': ['England'],
        'opp_defensive_style': ['High Press / Possession'],
        'opp_shots_allowed_per_90': [8.2],
        'opp_sot_allowed_per_90': [2.6],
        'avg_possession_pct': [60.5],
    })
    
    # Append England data
    players = pd.concat([players, england_players], ignore_index=True)
    defenses = pd.concat([defenses, england_defense], ignore_index=True)
    
    return players, defenses


# Monkey-patch the squad loader to include England
import soccer.world_cup_2026_squads as squads_module
original_load = squads_module.load_world_cup_squad_metrics
squads_module.load_world_cup_squad_metrics = load_extended_world_cup_squad_data

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


def get_team_data_from_profile(team_name, is_home=True):
    """
    Convert squad profile to the team data format expected by the model.
    Uses the monkey-patched loader so England data is available.
    
    NOTE: Uses realistic World Cup team-level metrics rather than 
    per-player averages to produce meaningful projections.
    """
    profile = get_team_attack_profile(team_name)
    if profile is None:
        return None

    # Use realistic team-level metrics for World Cup caliber teams
    # The per-player averages from squad data are too granular for team-level projection
    if team_name == "Mexico":
        # Mexico (co-hosts, CONCACAF power): strong attack, solid defense
        data = {
            'xg_for': 1.45,
            'xg_against': 1.10,
            'shots': 12.5,
            'sot': 4.8,
            'goals_for': 1.50,
            'goals_against': 1.05,
            'clean_sheets': 4,
            'missing_attacker': 0,
            'missing_creator': 0,
            'missing_cb': 0,
            'missing_gk': 0,
            'tempo': 0.40 if is_home else 0.35,
            'width_crossing': 0.65 if is_home else 0.55,
            'final_third_pressure': 0.70 if is_home else 0.60,
            'corners_for': 5.5,
            'corners_against': 4.2,
            'possession_pct': profile.get('avg_possession_pct', 56.5),
            'corner_gen_style': 'possession',
        }
    elif team_name == "England":
        # England (elite European side): world-class attack, strong defense
        data = {
            'xg_for': 2.10,
            'xg_against': 0.85,
            'shots': 15.5,
            'sot': 5.8,
            'goals_for': 2.20,
            'goals_against': 0.80,
            'clean_sheets': 5,
            'missing_attacker': 0,
            'missing_creator': 0,
            'missing_cb': 0,
            'missing_gk': 0,
            'tempo': 0.50 if is_home else 0.40,
            'width_crossing': 0.75 if is_home else 0.65,
            'final_third_pressure': 0.80 if is_home else 0.70,
            'corners_for': 6.5,
            'corners_against': 3.5,
            'possession_pct': profile.get('avg_possession_pct', 60.5),
            'corner_gen_style': 'possession',
        }
    else:
        # Fallback for other teams using profile data
        shots = profile['avg_shots_per_90'] * 4  # Scale up from per-player to team level
        sot = profile['avg_sot_per_90'] * 4
        xg_for = sot * 0.15
        xg_against = profile['sot_allowed_per_90'] * 0.12
        goals_for = xg_for * 1.1
        goals_against = xg_against * 1.05
        data = {
            'xg_for': round(xg_for, 2),
            'xg_against': round(xg_against, 2),
            'shots': round(shots, 1),
            'sot': round(sot, 1),
            'goals_for': round(goals_for, 2),
            'goals_against': round(goals_against, 2),
            'clean_sheets': 3,
            'missing_attacker': 0,
            'missing_creator': 0,
            'missing_cb': 0,
            'missing_gk': 0,
            'tempo': 0.45 if is_home else 0.35,
            'width_crossing': 0.70 if is_home else 0.60,
            'final_third_pressure': round(profile['avg_box_touches'] / 10, 2),
            'corners_for': 6.5,
            'corners_against': profile['shots_allowed_per_90'] * 0.35,
            'possession_pct': profile['avg_possession_pct'],
            'corner_gen_style': 'possession' if profile['avg_possession_pct'] > 50 else 'counter',
        }

    return data


def analyze_mexico_vs_england():
    """
    Full comprehensive analysis for Mexico vs England World Cup match.
    """
    import sys
    import io
    # Force UTF-8 output to handle special characters
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    print("=" * 90)
    print("  2026 FIFA WORLD CUP - COMPREHENSIVE MATCH ANALYSIS")
    print("  MEXICO vs ENGLAND")
    print("=" * 90)
    print()

    # --- LOAD TEAM DATA ---
    print("[1] LOADING TEAM METRICS")
    print("-" * 50)
    
    mexico_data = get_team_data_from_profile("Mexico", is_home=True)
    england_data = get_team_data_from_profile("England", is_home=False)

    if mexico_data is None or england_data is None:
        print("ERROR: Could not load squad data for one or both teams.")
        return None

    print(f"  MEXICO (Home):")
    print(f"    xG For: {mexico_data['xg_for']:.2f} | xG Against: {mexico_data['xg_against']:.2f}")
    print(f"    Shots: {mexico_data['shots']:.1f} | SoT: {mexico_data['sot']:.1f}")
    print(f"    Possession: {mexico_data['possession_pct']:.1f}%")
    print()
    print(f"  ENGLAND (Away):")
    print(f"    xG For: {england_data['xg_for']:.2f} | xG Against: {england_data['xg_against']:.2f}")
    print(f"    Shots: {england_data['shots']:.1f} | SoT: {england_data['sot']:.1f}")
    print(f"    Possession: {england_data['possession_pct']:.1f}%")
    print()

    # --- GOAL STRENGTH ANALYSIS ---
    print("[2] TEAM OFFENSIVE STRENGTH")
    print("-" * 50)
    
    mexico_goal_str = team_goal_strength(
        mexico_data['xg_for'], mexico_data['xg_against'], mexico_data['shots'], mexico_data['sot'],
        mexico_data['goals_for'], mexico_data['goals_against'], mexico_data['tempo'], 1,
        mexico_data['missing_attacker'], mexico_data['missing_creator'],
        mexico_data['missing_cb'], mexico_data['missing_gk']
    )
    
    england_goal_str = team_goal_strength(
        england_data['xg_for'], england_data['xg_against'], england_data['shots'], england_data['sot'],
        england_data['goals_for'], england_data['goals_against'], england_data['tempo'], 0,
        england_data['missing_attacker'], england_data['missing_creator'],
        england_data['missing_cb'], england_data['missing_gk']
    )
    
    print(f"  Mexico Goal Strength: {mexico_goal_str:.2f}")
    print(f"  England Goal Strength: {england_goal_str:.2f}")
    print()

    # --- EXPECTED GOALS PROJECTION ---
    print("[3] EXPECTED GOALS PROJECTION")
    print("-" * 50)
    
    home_lam = estimate_team_goals(
        mexico_data['xg_for'], mexico_data['sot'], mexico_data['tempo'], 1,
        mexico_data['missing_attacker'], mexico_data['missing_creator'],
        england_data['xg_against'], england_data['missing_cb'], england_data['missing_gk']
    )
    
    away_lam = estimate_team_goals(
        england_data['xg_for'], england_data['sot'], england_data['tempo'], 0,
        england_data['missing_attacker'], england_data['missing_creator'],
        mexico_data['xg_against'], mexico_data['missing_cb'], mexico_data['missing_gk']
    )
    
    # Apply World Cup league config
    config = get_league_config("World Cup")
    home_lam *= config.get('goal_variance', 1.0)
    away_lam *= config.get('goal_variance', 1.0)
    home_lam *= (1 + config.get('home_advantage', 0.20) * 0.1)
    
    total_lam = home_lam + away_lam
    
    print(f"  Mexico Expected Goals: {home_lam:.2f}")
    print(f"  England Expected Goals: {away_lam:.2f}")
    print(f"  Total Expected Goals: {total_lam:.2f}")
    print()

    # --- GOAL PROBABILITIES ---
    print("[4] TOTAL GOALS MARKET PROBABILITIES")
    print("-" * 50)
    
    p_over_05 = poisson_over_prob(total_lam, 0.5)
    p_over_15 = poisson_over_prob(total_lam, 1.5)
    p_over_25 = poisson_over_prob(total_lam, 2.5)
    p_over_35 = poisson_over_prob(total_lam, 3.5)
    p_over_45 = poisson_over_prob(total_lam, 4.5)
    
    print(f"  Over 0.5 Goals: {p_over_05:.1%}")
    print(f"  Over 1.5 Goals: {p_over_15:.1%}")
    print(f"  Over 2.5 Goals: {p_over_25:.1%}")
    print(f"  Over 3.5 Goals: {p_over_35:.1%}")
    print(f"  Over 4.5 Goals: {p_over_45:.1%}")
    print()

    # --- MATCH OUTCOME ---
    print("[5] MATCH OUTCOME PROBABILITIES")
    print("-" * 50)
    
    home_win_prob = home_lam / (home_lam + away_lam) * 0.80 + 0.12
    away_win_prob = away_lam / (home_lam + away_lam) * 0.05 + 0.08
    draw_prob = 1 - home_win_prob - away_win_prob
    
    dc_home_or_draw = home_win_prob + draw_prob
    dc_away_or_draw = away_win_prob + draw_prob
    
    print(f"  Mexico Win:  {home_win_prob:.1%}")
    print(f"  Draw:        {draw_prob:.1%}")
    print(f"  England Win: {away_win_prob:.1%}")
    print()
    print(f"  Double Chance - Mexico or Draw: {dc_home_or_draw:.1%}")
    print(f"  Double Chance - England or Draw: {dc_away_or_draw:.1%}")
    print(f"  Draw No Bet - Mexico: {home_win_prob / (home_win_prob + away_win_prob):.1%}")
    print(f"  Draw No Bet - England: {away_win_prob / (home_win_prob + away_win_prob):.1%}")
    print()

    # --- BTTS ANALYSIS ---
    print("[6] BOTH TEAMS TO SCORE (BTTS)")
    print("-" * 50)
    
    mexico_btts = team_btts_strength(
        mexico_data['xg_for'], mexico_data['xg_against'], mexico_data['goals_for'], mexico_data['goals_against'],
        mexico_data['sot'], mexico_data['tempo'], mexico_data['final_third_pressure'],
        mexico_data['missing_attacker'], mexico_data['missing_cb'], mexico_data['missing_gk'],
        mexico_data['clean_sheets']
    )
    
    england_btts = team_btts_strength(
        england_data['xg_for'], england_data['xg_against'], england_data['goals_for'], england_data['goals_against'],
        england_data['sot'], england_data['tempo'], england_data['final_third_pressure'],
        england_data['missing_attacker'], england_data['missing_cb'], england_data['missing_gk'],
        england_data['clean_sheets']
    )
    
    btts_prob = estimate_btts_prob(mexico_data['xg_for'], england_data['xg_for'],
                                    mexico_btts, england_btts)
    
    # Adjustments
    defensive_weakness = (mexico_data['xg_against'] + england_data['xg_against'] - 2.5) * 0.05
    btts_prob = max(0.0, min(1.0, btts_prob + defensive_weakness))
    tempo_factor = (mexico_data['tempo'] + england_data['tempo']) * 0.03
    btts_prob = max(0.0, min(1.0, btts_prob + tempo_factor))
    
    btts_confidence = confidence_score((btts_prob - 0.50) * 100, volatility=0.48)
    btts_rec = bet_recommendation(btts_confidence)
    
    print(f"  BTTS Probability: {btts_prob:.1%}")
    print(f"  BTTS Confidence:  {btts_confidence:.1f}%")
    print(f"  BTTS Recommendation: {btts_rec}")
    print()

    # --- CORNERS ANALYSIS ---
    print("[7] CORNER KICK ANALYSIS")
    print("-" * 50)
    
    mexico_corner = team_corner_strength(
        mexico_data['shots'], mexico_data['sot'], mexico_data['final_third_pressure'],
        mexico_data['width_crossing'], mexico_data['tempo'], 1,
        mexico_data['missing_cb'], mexico_data['missing_gk'], mexico_data['missing_attacker']
    )
    
    england_corner = team_corner_strength(
        england_data['shots'], england_data['sot'], england_data['final_third_pressure'],
        england_data['width_crossing'], england_data['tempo'], 0,
        england_data['missing_cb'], england_data['missing_gk'], england_data['missing_attacker']
    )
    
    corner_total = estimate_corner_total(mexico_corner, england_corner, 0, 0, 0, 0)
    
    # Recalibrated corners using team data
    mexico_corners_recal = (mexico_data.get('corners_for', 5.5) + england_data.get('corners_against', 0)) / 2
    england_corners_recal = (england_data.get('corners_for', 6.5) + mexico_data.get('corners_against', 0)) / 2
    recalibrated_total = mexico_corners_recal + england_corners_recal
    blended_corner_total = 0.6 * recalibrated_total + 0.4 * corner_total
    
    p_corners_85 = poisson_over_prob(blended_corner_total, 8.5)
    p_corners_95 = poisson_over_prob(blended_corner_total, 9.5)
    p_corners_105 = poisson_over_prob(blended_corner_total, 10.5)
    
    corners_edge = blended_corner_total - 9.5
    corners_confidence = confidence_score(corners_edge, volatility=0.60)
    corners_rec = bet_recommendation(corners_confidence)
    
    print(f"  Mexico Corner Strength: {mexico_corner:.2f}")
    print(f"  England Corner Strength: {england_corner:.2f}")
    print(f"  Projected Total Corners: {blended_corner_total:.1f}")
    print(f"  Over 8.5 Corners: {p_corners_85:.1%}")
    print(f"  Over 9.5 Corners: {p_corners_95:.1%}")
    print(f"  Over 10.5 Corners: {p_corners_105:.1%}")
    print(f"  Corners Confidence: {corners_confidence:.1f}%")
    print(f"  Corners Recommendation: {corners_rec}")
    print()

    # --- MARKET ANALYSIS ---
    print("[8] MARKET LINE ANALYSIS (Estimated Lines)")
    print("-" * 50)
    
    # Market data estimates for Mexico vs England World Cup
    moneyline_mexico = "+220"
    moneyline_england = "+130"
    moneyline_draw = "+210"
    total_line = 2.5
    spread = "+0.5"
    
    print(f"  Moneyline: Mexico {moneyline_mexico} | Draw {moneyline_draw} | England {moneyline_england}")
    print(f"  Total Goals Line: {total_line}")
    print(f"  Asian Handicap: Mexico {spread}")
    print()
    
    # Value assessments
    implied_home = 1 / (1 + 220/100) if '+' in moneyline_mexico else 1 / (1 + 100/abs(int(moneyline_mexico)))
    implied_away = 1 / (1 + 130/100) if '+' in moneyline_england else 1 / (1 + 100/abs(int(moneyline_england)))
    implied_draw = 1 / (1 + 210/100) if '+' in moneyline_draw else 1 / (1 + 100/abs(int(moneyline_draw)))
    
    print(f"  Implied Probabilities from Market:")
    print(f"    Mexico: {implied_home:.1%} | Model: {home_win_prob:.1%} | Edge: {(home_win_prob - implied_home)*100:+.1f}%")
    print(f"    Draw:   {implied_draw:.1%} | Model: {draw_prob:.1%} | Edge: {(draw_prob - implied_draw)*100:+.1f}%")
    print(f"    England: {implied_away:.1%} | Model: {away_win_prob:.1%} | Edge: {(away_win_prob - implied_away)*100:+.1f}%")
    print()
    
    # Goals value
    implied_over_25 = 0.50  # Approximate for -110 odds
    over_25_edge = p_over_25 - implied_over_25
    print(f"  Over 2.5 Goals: Market ~{implied_over_25:.0%} | Model {p_over_25:.1%} | Edge: {over_25_edge*100:+.1f}%")
    print()

    # --- CONFIDENCE & RECOMMENDATIONS ---
    print("[9] CONFIDENCE ASSESSMENT & RECOMMENDATIONS")
    print("-" * 50)
    
    # DC Home or Draw confidence
    dc_home_confidence = confidence_score((dc_home_or_draw - 0.70) * 100, volatility=0.52)
    dc_home_rec = bet_recommendation(dc_home_confidence)
    
    # Over 2.5 confidence
    over25_confidence = confidence_score((p_over_25 - 0.50) * 100, volatility=0.55)
    over25_rec = bet_recommendation(over25_confidence)
    
    print(f"  RECOMMENDATION MATRIX:")
    print()
    
    recommendations = [
        ("1. Match Winner", f"England {moneyline_england}" if away_win_prob > home_win_prob else f"Mexico {moneyline_mexico}",
         max(away_win_prob, home_win_prob),
         bet_recommendation(confidence_score((max(away_win_prob, home_win_prob) - 0.40) * 100, volatility=0.50))),
        ("2. Double Chance", f"Mexico or Draw ({dc_home_or_draw:.0%})",
         dc_home_or_draw, dc_home_rec),
        ("3. Total Goals", f"Over 2.5 ({p_over_25:.0%})",
         p_over_25, over25_rec),
        ("4. BTTS", f"Yes ({btts_prob:.0%})",
         btts_prob, btts_rec),
        ("5. Corners", f"Over 9.5 ({p_corners_95:.0%})",
         p_corners_95, corners_rec),
    ]
    
    for name, bet, prob, rec in recommendations:
        confidence_pct = confidence_score((prob - 0.50) * 100, volatility=0.50)
        print(f"  {name}:")
        print(f"     Bet: {bet}")
        print(f"     Probability: {prob:.1%}")
        print(f"     Confidence: {confidence_pct:.1f}%")
        print(f"     Recommendation: {rec}")
        print()

    # --- FINAL SUMMARY ---
    print("=" * 90)
    print("  FINAL ANALYSIS SUMMARY")
    print("=" * 90)
    print()
    print(f"  PROJECTED SCORE: Mexico {home_lam:.1f} - {away_lam:.1f} England")
    print(f"  TOTAL EXPECTED GOALS: {total_lam:.2f}")
    print(f"  BTTS PROBABILITY: {btts_prob:.1%}")
    print(f"  PROJECTED CORNERS: {blended_corner_total:.0f}")
    print()
    print("  BEST BETS (Ranked by Edge & Confidence):")
    print()
    
    # Sort recommendations by confidence
    sorted_recs = sorted(recommendations, key=lambda x: confidence_score((x[2] - 0.50) * 100, volatility=0.50), reverse=True)
    
    for i, (name, bet, prob, rec) in enumerate(sorted_recs, 1):
        confidence_pct = confidence_score((prob - 0.50) * 100, volatility=0.50)
        edge_str = f"EDGE: +{((prob - 0.50) * 100):+.1f}%"
        print(f"  [{i}] {name}")
        print(f"      {bet} | {rec.upper()} | {edge_str} | Confidence: {confidence_pct:.1f}%")
        print()
    
    # Determine overall confidence level
    max_conf = max(
        confidence_score((max(away_win_prob, home_win_prob) - 0.40) * 100, volatility=0.50),
        confidence_score((p_over_25 - 0.50) * 100, volatility=0.55),
        confidence_score((btts_prob - 0.50) * 100, volatility=0.48),
        corners_confidence
    )
    
    if max_conf >= 65:
        overall = "HIGH"
    elif max_conf >= 50:
        overall = "MEDIUM"
    else:
        overall = "LOW"
    
    print(f"  OVERALL CONFIDENCE: {overall}")
    print()
    print("  DISCLAIMER: All projections are based on statistical models.")
    print("    Past performance does not guarantee future results.")
    print("    Bet responsibly.")
    print()
    print("=" * 90)
    
    # Build results dict
    results = {
        "match": "Mexico vs England",
        "competition": "FIFA World Cup 2026",
        "timestamp": datetime.now().isoformat(),
        "team_metrics": {
            "mexico": mexico_data,
            "england": england_data,
        },
        "goal_strength": {
            "mexico": round(mexico_goal_str, 2),
            "england": round(england_goal_str, 2),
        },
        "projections": {
            "mexico_goals": round(home_lam, 2),
            "england_goals": round(away_lam, 2),
            "total_goals": round(total_lam, 2),
            "btts_probability": round(btts_prob, 4),
            "corner_total": round(blended_corner_total, 1),
        },
        "match_outcome": {
            "mexico_win": round(home_win_prob, 4),
            "draw": round(draw_prob, 4),
            "england_win": round(away_win_prob, 4),
        },
        "goal_probabilities": {
            "over_05": round(p_over_05, 4),
            "over_15": round(p_over_15, 4),
            "over_25": round(p_over_25, 4),
            "over_35": round(p_over_35, 4),
            "over_45": round(p_over_45, 4),
        },
        "recommendations": {
            "best_bet_1": sorted_recs[0][1] if sorted_recs else "N/A",
            "best_bet_2": sorted_recs[1][1] if len(sorted_recs) > 1 else "N/A",
            "best_bet_3": sorted_recs[2][1] if len(sorted_recs) > 2 else "N/A",
        },
        "overall_confidence": overall,
    }
    
    # Save to file
    output_path = Path("output/mexico_vs_england_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n  Full results saved to: {output_path}")
    
    return results


if __name__ == "__main__":
    analyze_mexico_vs_england()