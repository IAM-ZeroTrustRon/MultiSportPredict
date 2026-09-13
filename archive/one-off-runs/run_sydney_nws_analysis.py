#!/usr/bin/env python
"""
Comprehensive Soccer Analysis for Sydney FC NPL vs NWS Spirit FC
NPL NSW - June 3, 2026
Includes: Moneyline (FG, 1H), Totals (FG, 1H, Team), Corners
"""

import sys
import json
import math
from datetime import datetime
from pathlib import Path

# Import the MultiSportModel functions
from MultiSportModel import (
    run_universal_match,
    process_soccer_goals,
    process_soccer_corners,
    process_soccer_btts,
    team_goal_strength,
    team_btts_strength,
    team_corner_strength,
    estimate_team_goals,
    estimate_btts_prob,
    estimate_corner_total,
    poisson_over_prob,
    poisson_at_least_one,
    sigmoid,
    clamp,
    market_recommendation,
    btts_recommendation,
)


def poisson_pmf(k, lam):
    """Poisson probability mass function"""
    if lam <= 0:
        return 0.0 if k > 0 else 1.0
    if k < 0:
        return 0.0
    try:
        log_pmf = -lam + k * math.log(lam) - math.lgamma(k + 1)
        return math.exp(log_pmf)
    except (ValueError, OverflowError):
        return 0.0


def moneyline_prob(home_lam, away_lam):
    """Calculate moneyline probabilities from expected goals"""
    # Probability of home win
    p_home = 0.0
    for h in range(0, 10):
        for a in range(0, h):
            p_home += poisson_pmf(h, home_lam) * poisson_pmf(a, away_lam)
    
    # Probability of draw
    p_draw = 0.0
    for i in range(0, 10):
        p_draw += poisson_pmf(i, home_lam) * poisson_pmf(i, away_lam)
    
    # Probability of away win
    p_away = 1.0 - p_home - p_draw
    
    return p_home, p_draw, p_away


def analyze_soccer_match(
    home_team, away_team, home_data, away_data, market_data, venue,
    date="2026-06-03", league="NPL NSW"
):
    """Analyze a soccer match with comprehensive projections"""
    
    print("=" * 80)
    print(f"COMPREHENSIVE SOCCER ANALYSIS: {home_team} vs {away_team}")
    print(f"{league} - {date}")
    print(f"Venue: {venue}")
    print("=" * 80)
    print()
    
    # 1. TEAM OFFENSIVE ANALYSIS
    print("1. TEAM OFFENSIVE ANALYSIS")
    print("-" * 40)
    
    home_goal_strength_val = team_goal_strength(
        home_data['xg_for'], home_data['xg_against'], home_data['shots'], home_data['sot'],
        home_data['goals_for'], home_data['goals_against'], home_data['tempo'], 1,
        home_data['missing_attacker'], home_data['missing_creator'],
        home_data['missing_cb'], home_data['missing_gk']
    )
    
    away_goal_strength_val = team_goal_strength(
        away_data['xg_for'], away_data['xg_against'], away_data['shots'], away_data['sot'],
        away_data['goals_for'], away_data['goals_against'], away_data['tempo'], 0,
        away_data['missing_attacker'], away_data['missing_creator'],
        away_data['missing_cb'], away_data['missing_gk']
    )
    
    print(f"   {home_team} Goal Strength: {home_goal_strength_val:.2f}")
    print(f"   {away_team} Goal Strength: {away_goal_strength_val:.2f}")
    print()
    
    # 2. TEAM DEFENSIVE ANALYSIS
    print("2. TEAM DEFENSIVE ANALYSIS")
    print("-" * 40)
    
    home_btts_strength_val = team_btts_strength(
        home_data['xg_for'], home_data['xg_against'], home_data['goals_for'], home_data['goals_against'],
        home_data['sot'], home_data['tempo'], home_data['final_third_pressure'],
        home_data['missing_attacker'], home_data['missing_cb'], home_data['missing_gk'],
        home_data['clean_sheets_last10']
    )
    
    away_btts_strength_val = team_btts_strength(
        away_data['xg_for'], away_data['xg_against'], away_data['goals_for'], away_data['goals_against'],
        away_data['sot'], away_data['tempo'], away_data['final_third_pressure'],
        away_data['missing_attacker'], away_data['missing_cb'], away_data['missing_gk'],
        away_data['clean_sheets_last10']
    )
    
    print(f"   {home_team} BTTS Strength: {home_btts_strength_val:.2f}")
    print(f"   {away_team} BTTS Strength: {away_btts_strength_val:.2f}")
    print()
    
    # 3. CORNER KICK ANALYSIS
    print("3. CORNER KICK ANALYSIS")
    print("-" * 40)
    
    home_corner_strength_val = team_corner_strength(
        home_data['shots'], home_data['sot'], home_data['final_third_pressure'],
        home_data['width_crossing'], home_data['tempo'], 1,
        home_data['missing_cb'], home_data['missing_gk'], home_data['missing_attacker']
    )
    
    away_corner_strength_val = team_corner_strength(
        away_data['shots'], away_data['sot'], away_data['final_third_pressure'],
        away_data['width_crossing'], away_data['tempo'], 0,
        away_data['missing_cb'], away_data['missing_gk'], away_data['missing_attacker']
    )
    
    print(f"   {home_team} Corner Strength: {home_corner_strength_val:.2f}")
    print(f"   {away_team} Corner Strength: {away_corner_strength_val:.2f}")
    print()
    
    # 4. EXPECTED GOALS PROJECTION
    print("4. EXPECTED GOALS PROJECTION")
    print("-" * 40)
    
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
    
    total_lam = home_lam + away_lam
    
    print(f"   {home_team} Expected Goals: {home_lam:.2f}")
    print(f"   {away_team} Expected Goals: {away_lam:.2f}")
    print(f"   Total Expected Goals: {total_lam:.2f}")
    print()
    
    # 5. MONEYLINE PROJECTIONS (Full Game)
    print("5. MONEYLINE PROJECTIONS (FULL GAME)")
    print("-" * 40)
    
    p_home, p_draw, p_away = moneyline_prob(home_lam, away_lam)
    
    print(f"   {home_team} Win Probability: {p_home:.3f} ({p_home*100:.1f}%)")
    print(f"   Draw Probability: {p_draw:.3f} ({p_draw*100:.1f}%)")
    print(f"   {away_team} Win Probability: {p_away:.3f} ({p_away*100:.1f}%)")
    
    # Convert to American odds
    def prob_to_american(prob):
        if prob > 0.5:
            return -100 * prob / (1 - prob)
        else:
            return 100 * (1 - prob) / prob
    
    home_odds = prob_to_american(p_home)
    draw_odds = prob_to_american(p_draw)
    away_odds = prob_to_american(p_away)
    
    print(f"   Implied Odds: {home_team} {home_odds:+.0f} | Draw {draw_odds:+.0f} | {away_team} {away_odds:+.0f}")
    print()
    
    # 6. FIRST HALF MONEYLINE
    print("6. FIRST HALF MONEYLINE")
    print("-" * 40)
    
    # First half expected goals (roughly 45% of full game)
    home_lam_1h = home_lam * 0.45
    away_lam_1h = away_lam * 0.45
    
    p_home_1h, p_draw_1h, p_away_1h = moneyline_prob(home_lam_1h, away_lam_1h)
    
    print(f"   {home_team} 1H Win Probability: {p_home_1h:.3f} ({p_home_1h*100:.1f}%)")
    print(f"   1H Draw Probability: {p_draw_1h:.3f} ({p_draw_1h*100:.1f}%)")
    print(f"   {away_team} 1H Win Probability: {p_away_1h:.3f} ({p_away_1h*100:.1f}%)")
    print()
    
    # 7. FULL GAME TOTALS
    print("7. FULL GAME TOTALS")
    print("-" * 40)
    
    p_over_15 = poisson_over_prob(total_lam, 1.5)
    p_over_25 = poisson_over_prob(total_lam, 2.5)
    p_over_35 = poisson_over_prob(total_lam, 3.5)
    p_under_15 = 1 - p_over_15
    p_under_25 = 1 - p_over_25
    p_under_35 = 1 - p_over_35
    
    print(f"   Over 1.5 Goals: {p_over_15:.3f} ({p_over_15*100:.1f}%)")
    print(f"   Over 2.5 Goals: {p_over_25:.3f} ({p_over_25*100:.1f}%)")
    print(f"   Over 3.5 Goals: {p_over_35:.3f} ({p_over_35*100:.1f}%)")
    print(f"   Under 1.5 Goals: {p_under_15:.3f} ({p_under_15*100:.1f}%)")
    print(f"   Under 2.5 Goals: {p_under_25:.3f} ({p_under_25*100:.1f}%)")
    print(f"   Under 3.5 Goals: {p_under_35:.3f} ({p_under_35*100:.1f}%)")
    
    # Market recommendation
    total_line = market_data.get('total', 2.5)
    if total_line <= 1.5:
        prob_over = p_over_15
    elif total_line <= 2.5:
        prob_over = p_over_25
    else:
        prob_over = p_over_35
    
    goals_lean = market_recommendation(prob_over, total_line)
    print(f"   Market Total: {total_line}")
    print(f"   Recommendation: {goals_lean}")
    print()
    
    # 8. FIRST HALF TOTALS
    print("8. FIRST HALF TOTALS")
    print("-" * 40)
    
    p_1h_over_05 = poisson_over_prob(total_lam * 0.45, 0.5)
    p_1h_over_15 = poisson_over_prob(total_lam * 0.45, 1.5)
    p_1h_under_05 = 1 - p_1h_over_05
    p_1h_under_15 = 1 - p_1h_over_15
    
    print(f"   1H Over 0.5 Goals: {p_1h_over_05:.3f} ({p_1h_over_05*100:.1f}%)")
    print(f"   1H Over 1.5 Goals: {p_1h_over_15:.3f} ({p_1h_over_15*100:.1f}%)")
    print(f"   1H Under 0.5 Goals: {p_1h_under_05:.3f} ({p_1h_under_05*100:.1f}%)")
    print(f"   1H Under 1.5 Goals: {p_1h_under_15:.3f} ({p_1h_under_15*100:.1f}%)")
    print()
    
    # 9. TEAM TOTALS
    print("9. TEAM TOTALS")
    print("-" * 40)
    
    # Home team totals
    p_home_over_15 = poisson_over_prob(home_lam, 1.5)
    p_home_over_25 = poisson_over_prob(home_lam, 2.5)
    p_home_under_15 = 1 - p_home_over_15
    p_home_under_25 = 1 - p_home_over_25
    
    print(f"   {home_team}:")
    print(f"      Over 1.5 Team Goals: {p_home_over_15:.3f} ({p_home_over_15*100:.1f}%)")
    print(f"      Over 2.5 Team Goals: {p_home_over_25:.3f} ({p_home_over_25*100:.1f}%)")
    print(f"      Under 1.5 Team Goals: {p_home_under_15:.3f} ({p_home_under_15*100:.1f}%)")
    print(f"      Under 2.5 Team Goals: {p_home_under_25:.3f} ({p_home_under_25*100:.1f}%)")
    print()
    
    # Away team totals
    p_away_over_15 = poisson_over_prob(away_lam, 1.5)
    p_away_over_25 = poisson_over_prob(away_lam, 2.5)
    p_away_under_15 = 1 - p_away_over_15
    p_away_under_25 = 1 - p_away_over_25
    
    print(f"   {away_team}:")
    print(f"      Over 1.5 Team Goals: {p_away_over_15:.3f} ({p_away_over_15*100:.1f}%)")
    print(f"      Over 2.5 Team Goals: {p_away_over_25:.3f} ({p_away_over_25*100:.1f}%)")
    print(f"      Under 1.5 Team Goals: {p_away_under_15:.3f} ({p_away_under_15*100:.1f}%)")
    print(f"      Under 2.5 Team Goals: {p_away_under_25:.3f} ({p_away_under_25*100:.1f}%)")
    print()
    
    # 10. BTTS (Both Teams To Score)
    print("10. BTTS (BOTH TEAMS TO SCORE)")
    print("-" * 40)
    
    btts_prob = estimate_btts_prob(home_data['xg_for'], away_data['xg_for'],
                                   home_btts_strength_val, away_btts_strength_val)
    
    # Adjustments
    defensive_weakness = (home_data['xg_against'] + away_data['xg_against'] - 2.5) * 0.05
    btts_prob = clamp(btts_prob + defensive_weakness)
    
    missing_defenders = (home_data['missing_cb'] + home_data['missing_gk'] +
                        away_data['missing_cb'] + away_data['missing_gk']) * 0.02
    btts_prob = clamp(btts_prob + missing_defenders)
    
    tempo_factor = (home_data['tempo'] + away_data['tempo']) * 0.03
    btts_prob = clamp(btts_prob + tempo_factor)
    
    btts_lean = btts_recommendation(btts_prob)
    
    print(f"   BTTS Yes Probability: {btts_prob:.3f} ({btts_prob*100:.1f}%)")
    print(f"   BTTS No Probability: {1 - btts_prob:.3f} ({(1-btts_prob)*100:.1f}%)")
    print(f"   Recommendation: {btts_lean}")
    print()
    
    # 11. CORNER PROJECTIONS
    print("11. CORNER PROJECTIONS")
    print("-" * 40)
    
    corner_total = estimate_corner_total(
        home_corner_strength_val, away_corner_strength_val,
        weather_penalty=0, referee_flow=0,
        must_win_home=0, must_win_away=0
    )
    
    p_corners_85 = poisson_over_prob(corner_total, 8.5)
    p_corners_95 = poisson_over_prob(corner_total, 9.5)
    p_corners_105 = poisson_over_prob(corner_total, 10.5)
    p_corners_115 = poisson_over_prob(corner_total, 11.5)
    
    print(f"   Projected Total Corners: {corner_total:.1f}")
    print(f"   Over 8.5 Corners: {p_corners_85:.3f} ({p_corners_85*100:.1f}%)")
    print(f"   Over 9.5 Corners: {p_corners_95:.3f} ({p_corners_95*100:.1f}%)")
    print(f"   Over 10.5 Corners: {p_corners_105:.3f} ({p_corners_105*100:.1f}%)")
    print(f"   Over 11.5 Corners: {p_corners_115:.3f} ({p_corners_115*100:.1f}%)")
    
    # Team corner projections
    home_corners = (home_corner_strength_val + 5) * 1.2
    away_corners = (away_corner_strength_val + 5) * 1.2
    
    print(f"   {home_team} Projected Corners: {home_corners:.0f}")
    print(f"   {away_team} Projected Corners: {away_corners:.0f}")
    
    corner_line = market_data.get('corners', 9.5)
    if corner_line <= 8.5:
        prob_corners_over = p_corners_85
    elif corner_line <= 9.5:
        prob_corners_over = p_corners_95
    else:
        prob_corners_over = p_corners_105
    
    corners_lean = market_recommendation(prob_corners_over, corner_line)
    print(f"   Market Corners: {corner_line}")
    print(f"   Recommendation: {corners_lean}")
    print()
    
    # 12. UNIVERSAL MODEL VERIFICATION
    print("12. UNIVERSAL MODEL VERIFICATION")
    print("-" * 40)
    
    core = {
        'home_team': home_team,
        'away_team': away_team,
        'league': league,
        'date': date,
        'market_line': market_data.get('total', 2.5),
        'current_line': market_data.get('total', 2.5),
        'open_line': market_data.get('total', 2.5),
    }
    
    goals_metrics = {
        'home_xg_for': home_data['xg_for'],
        'home_xg_against': home_data['xg_against'],
        'home_shots': home_data['shots'],
        'home_sot': home_data['sot'],
        'home_goals_for': home_data['goals_for'],
        'home_goals_against': home_data['goals_against'],
        'home_clean_sheets_last10': home_data['clean_sheets_last10'],
        'home_missing_attacker': home_data['missing_attacker'],
        'home_missing_creator': home_data['missing_creator'],
        'home_missing_cb': home_data['missing_cb'],
        'home_missing_gk': home_data['missing_gk'],
        'home_tempo': home_data['tempo'],
        'home_width_crossing': home_data['width_crossing'],
        'home_final_third_pressure': home_data['final_third_pressure'],
        'away_xg_for': away_data['xg_for'],
        'away_xg_against': away_data['xg_against'],
        'away_shots': away_data['shots'],
        'away_sot': away_data['sot'],
        'away_goals_for': away_data['goals_for'],
        'away_goals_against': away_data['goals_against'],
        'away_clean_sheets_last10': away_data['clean_sheets_last10'],
        'away_missing_attacker': away_data['missing_attacker'],
        'away_missing_creator': away_data['missing_creator'],
        'away_missing_cb': away_data['missing_cb'],
        'away_missing_gk': away_data['missing_gk'],
        'away_tempo': away_data['tempo'],
        'away_width_crossing': away_data['width_crossing'],
        'away_final_third_pressure': away_data['final_third_pressure'],
    }
    
    goals_result = run_universal_match('soccer_goals', core, goals_metrics)
    btts_result = run_universal_match('soccer_btts', core, goals_metrics)
    corners_result = run_universal_match('soccer_corners', core, goals_metrics)
    
    print(f"   Goals Model: Score={goals_result['model_score']:.2f}, Prob={goals_result['model_prob']:.3f}, Lean={goals_result['lean']}")
    print(f"   BTTS Model: Score={btts_result['model_score']:.2f}, Prob={btts_result['model_prob']:.3f}, Lean={btts_result['lean']}")
    print(f"   Corners Model: Score={corners_result['model_score']:.2f}, Prob={corners_result['model_prob']:.3f}, Lean={corners_result['lean']}")
    print()
    
    # FINAL SUMMARY
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Projected Score: {home_team} {home_lam:.1f} - {away_team} {away_lam:.1f}")
    print(f"   Total Expected Goals: {total_lam:.2f}")
    print()
    print("   MONEYLINE:")
    print(f"      {home_team}: {p_home:.1%} | Draw: {p_draw:.1%} | {away_team}: {p_away:.1%}")
    print()
    print("   FIRST HALF MONEYLINE:")
    print(f"      {home_team}: {p_home_1h:.1%} | Draw: {p_draw_1h:.1%} | {away_team}: {p_away_1h:.1%}")
    print()
    print("   TOTALS:")
    print(f"      FG Over 2.5: {p_over_25:.1%} | 1H Over 1.5: {p_1h_over_15:.1%}")
    print(f"      {home_team} Team Total Over 1.5: {p_home_over_15:.1%}")
    print(f"      {away_team} Team Total Over 1.5: {p_away_over_15:.1%}")
    print()
    print(f"   BTTS: {btts_prob:.1%}")
    print()
    print("   CORNERS:")
    print(f"      Total Corners: {corner_total:.0f} | Over 9.5: {p_corners_95:.1%}")
    print()
    print("   PRIMARY RECOMMENDATIONS:")
    print(f"      Goals: {goals_lean}")
    print(f"      BTTS: {btts_lean}")
    print(f"      Corners: {corners_lean}")
    print()
    
    # Determine confidence
    max_prob = max(p_over_25, btts_prob, p_corners_95, abs(p_home - 0.5) + 0.5)
    if max_prob >= 0.65:
        confidence = "HIGH"
    elif max_prob >= 0.58:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    
    print(f"   CONFIDENCE LEVEL: {confidence}")
    print()
    
    # Build results dictionary
    results = {
        "game_info": {
            "home_team": home_team,
            "away_team": away_team,
            "league": league,
            "date": date,
            "venue": venue
        },
        "team_metrics": {
            "home": home_data,
            "away": away_data
        },
        "market_data": market_data,
        "projections": {
            "home_goals": round(home_lam, 2),
            "away_goals": round(away_lam, 2),
            "total_goals": round(total_lam, 2),
            "home_corners": round(home_corners, 0),
            "away_corners": round(away_corners, 0),
            "total_corners": round(corner_total, 1),
        },
        "moneyline": {
            "full_game": {
                "home_win_prob": round(p_home, 4),
                "draw_prob": round(p_draw, 4),
                "away_win_prob": round(p_away, 4),
                "implied_odds": {
                    "home": round(home_odds, 0),
                    "draw": round(draw_odds, 0),
                    "away": round(away_odds, 0),
                }
            },
            "first_half": {
                "home_win_prob": round(p_home_1h, 4),
                "draw_prob": round(p_draw_1h, 4),
                "away_win_prob": round(p_away_1h, 4),
            }
        },
        "totals": {
            "full_game": {
                "over_15": round(p_over_15, 4),
                "over_25": round(p_over_25, 4),
                "over_35": round(p_over_35, 4),
                "under_15": round(p_under_15, 4),
                "under_25": round(p_under_25, 4),
                "under_35": round(p_under_35, 4),
            },
            "first_half": {
                "over_05": round(p_1h_over_05, 4),
                "over_15": round(p_1h_over_15, 4),
                "under_05": round(p_1h_under_05, 4),
                "under_15": round(p_1h_under_15, 4),
            },
            "team_totals": {
                "home": {
                    "over_15": round(p_home_over_15, 4),
                    "over_25": round(p_home_over_25, 4),
                    "under_15": round(p_home_under_15, 4),
                    "under_25": round(p_home_under_25, 4),
                },
                "away": {
                    "over_15": round(p_away_over_15, 4),
                    "over_25": round(p_away_over_25, 4),
                    "under_15": round(p_away_under_15, 4),
                    "under_25": round(p_away_under_25, 4),
                }
            }
        },
        "btts": {
            "yes_prob": round(btts_prob, 4),
            "no_prob": round(1 - btts_prob, 4),
        },
        "corners": {
            "total": round(corner_total, 1),
            "over_85": round(p_corners_85, 4),
            "over_95": round(p_corners_95, 4),
            "over_105": round(p_corners_105, 4),
            "over_115": round(p_corners_115, 4),
        },
        "recommendations": {
            "goals_total": goals_lean,
            "btts": btts_lean,
            "corners_total": corners_lean,
        },
        "model_details": {
            "home_goal_strength": round(home_goal_strength_val, 2),
            "away_goal_strength": round(away_goal_strength_val, 2),
            "home_btts_strength": round(home_btts_strength_val, 2),
            "away_btts_strength": round(away_btts_strength_val, 2),
            "home_corner_strength": round(home_corner_strength_val, 2),
            "away_corner_strength": round(away_corner_strength_val, 2),
            "goals_model_score": goals_result['model_score'],
            "goals_model_prob": goals_result['model_prob'],
            "btts_model_score": btts_result['model_score'],
            "btts_model_prob": btts_result['model_prob'],
            "corners_model_score": corners_result['model_score'],
            "corners_model_prob": corners_result['model_prob'],
        },
        "confidence": confidence,
        "timestamp": datetime.now().isoformat()
    }
    
    return results


def run_sydney_nws_analysis():
    """Run comprehensive soccer analysis for Sydney FC NPL vs NWS Spirit FC"""
    
    print("=" * 80)
    print("COMPREHENSIVE SOCCER ANALYSIS: SYDNEY FC NPL vs NWS SPIRIT FC")
    print("NPL NSW - June 3, 2026")
    print("=" * 80)
    print()
    
    # Define team data based on NPL NSW metrics
    # Sydney FC NPL (Home)
    home_data = {
        'xg_for': 1.85,        # Expected goals for per game
        'xg_against': 1.15,    # Expected goals against per game
        'shots': 14.2,         # Shots per game
        'sot': 5.5,            # Shots on target per game
        'goals_for': 1.9,      # Goals scored per game
        'goals_against': 1.1,  # Goals conceded per game
        'clean_sheets_last10': 5,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.35,         # Game tempo factor
        'width_crossing': 0.65, # Width and crossing tendency
        'final_third_pressure': 0.70,  # Final third pressure
    }
    
    # NWS Spirit FC (Away)
    away_data = {
        'xg_for': 1.45,        # Expected goals for per game
        'xg_against': 1.55,    # Expected goals against per game
        'shots': 11.8,         # Shots per game
        'sot': 4.2,            # Shots on target per game
        'goals_for': 1.4,      # Goals scored per game
        'goals_against': 1.5,  # Goals conceded per game
        'clean_sheets_last10': 2,
        'missing_attacker': 1,  # Missing one attacker
        'missing_creator': 0,
        'missing_cb': 1,        # Missing one center back
        'missing_gk': 0,
        'tempo': 0.25,         # Game tempo factor
        'width_crossing': 0.50, # Width and crossing tendency
        'final_third_pressure': 0.50,  # Final third pressure
    }
    
    # Market data
    market_data = {
        'open_line': 2.5,      # Opening total
        'current_line': 2.5,   # Current total
        'total': 2.5,          # Goals total
        'corners': 9.5,        # Corner total
    }
    
    # Run analysis
    result = analyze_soccer_match(
        home_team="Sydney FC NPL",
        away_team="NWS Spirit FC",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Jubilee Oval, Sydney",
        date="2026-06-03",
        league="NPL NSW"
    )
    
    # Save results
    output_path = Path("output/sydney_vs_nws_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"Detailed results saved to: {output_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    run_sydney_nws_analysis()