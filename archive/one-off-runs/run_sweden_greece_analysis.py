#!/usr/bin/env python
"""
Comprehensive Analysis for Sweden vs Greece
International Match - June 4, 2026
Includes: Moneyline (1X2), Team Goals, Match Goals, Team Corners, Match Corners
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


def calculate_moneyline_prob(home_lam, away_lam):
    """Calculate Moneyline (1X2) probabilities using Poisson distribution"""
    # Probability of home win
    p_home_win = 0.0
    p_draw = 0.0
    p_away_win = 0.0
    
    for h in range(0, 10):
        p_h = (math.exp(-home_lam) * home_lam**h) / math.factorial(h)
        for a in range(0, 10):
            p_a = (math.exp(-away_lam) * away_lam**a) / math.factorial(a)
            prob = p_h * p_a
            if h > a:
                p_home_win += prob
            elif h == a:
                p_draw += prob
            else:
                p_away_win += prob
    
    return p_home_win, p_draw, p_away_win


def run_comprehensive_analysis():
    """Run comprehensive analysis for Sweden vs Greece"""
    
    print("=" * 80)
    print("COMPREHENSIVE MATCH ANALYSIS: SWEDEN vs GREECE")
    print("International Match - June 4, 2026")
    print("=" * 80)
    print()
    
    # ========================================================================
    # TEAM DATA (Estimated based on recent international performance)
    # ========================================================================
    
    # Home Team: Sweden
    home_data = {
        'xg_for': 1.45,           # Expected goals scored per game
        'xg_against': 1.15,       # Expected goals conceded per game
        'shots': 12.5,            # Average shots per game
        'sot': 4.5,               # Average shots on target per game
        'goals_for': 1.4,         # Actual goals scored per game
        'goals_against': 1.0,     # Actual goals conceded per game
        'clean_sheets_last10': 5, # Clean sheets in last 10 games
        'missing_attacker': 0,    # Number of missing attackers
        'missing_creator': 0,     # Number of missing creative midfielders
        'missing_cb': 0,          # Number of missing center backs
        'missing_gk': 0,          # Number of missing goalkeepers
        'tempo': 0.15,            # Playing tempo (positive = fast)
        'width_crossing': 0.65,   # Width and crossing tendency (0-1)
        'final_third_pressure': 0.58,  # Pressure in final third (0-1)
    }
    
    # Away Team: Greece
    away_data = {
        'xg_for': 1.15,           # Expected goals scored per game
        'xg_against': 1.35,       # Expected goals conceded per game
        'shots': 10.2,            # Average shots per game
        'sot': 3.5,               # Average shots on target per game
        'goals_for': 1.0,         # Actual goals scored per game
        'goals_against': 1.3,     # Actual goals conceded per game
        'clean_sheets_last10': 3, # Clean sheets in last 10 games
        'missing_attacker': 1,    # Number of missing attackers
        'missing_creator': 0,     # Number of missing creative midfielders
        'missing_cb': 1,          # Number of missing center backs
        'missing_gk': 0,          # Number of missing goalkeepers
        'tempo': 0.05,            # Playing tempo (positive = fast)
        'width_crossing': 0.45,   # Width and crossing tendency (0-1)
        'final_third_pressure': 0.48,  # Pressure in final third (0-1)
    }
    
    # Market Data (Estimated typical lines for this matchup)
    market_data = {
        'open_line': 2.25,        # Opening total goals line
        'current_line': 2.25,     # Current total goals line
        'total': 2.25,            # Game total
        'corner_total': 9.0,      # Corner total
    }
    
    # ========================================================================
    # DETAILED HANDICAPPING ANALYSIS
    # ========================================================================
    
    print("1. TEAM OFFENSIVE ANALYSIS")
    print("-" * 40)
    
    home_goal_strength = team_goal_strength(
        home_data['xg_for'], home_data['xg_against'], home_data['shots'], home_data['sot'],
        home_data['goals_for'], home_data['goals_against'], home_data['tempo'], 1,  # home advantage
        home_data['missing_attacker'], home_data['missing_creator'], 
        home_data['missing_cb'], home_data['missing_gk']
    )
    
    away_goal_strength = team_goal_strength(
        away_data['xg_for'], away_data['xg_against'], away_data['shots'], away_data['sot'],
        away_data['goals_for'], away_data['goals_against'], away_data['tempo'], 0,  # away
        away_data['missing_attacker'], away_data['missing_creator'], 
        away_data['missing_cb'], away_data['missing_gk']
    )
    
    print(f"   Sweden Goal Strength: {home_goal_strength:.2f}")
    print(f"   Greece Goal Strength: {away_goal_strength:.2f}")
    print(f"   Offensive Edge: {'Sweden' if home_goal_strength > away_goal_strength else 'Greece'}")
    print()
    
    print("2. TEAM DEFENSIVE ANALYSIS")
    print("-" * 40)
    
    home_btts_strength = team_btts_strength(
        home_data['xg_for'], home_data['xg_against'], home_data['goals_for'], home_data['goals_against'],
        home_data['sot'], home_data['tempo'], home_data['final_third_pressure'], 
        home_data['missing_attacker'], home_data['missing_cb'], home_data['missing_gk'], 
        home_data['clean_sheets_last10']
    )
    
    away_btts_strength = team_btts_strength(
        away_data['xg_for'], away_data['xg_against'], away_data['goals_for'], away_data['goals_against'],
        away_data['sot'], away_data['tempo'], away_data['final_third_pressure'], 
        away_data['missing_attacker'], away_data['missing_cb'], away_data['missing_gk'], 
        away_data['clean_sheets_last10']
    )
    
    print(f"   Sweden BTTS Strength: {home_btts_strength:.2f}")
    print(f"   Greece BTTS Strength: {away_btts_strength:.2f}")
    print(f"   BTTS Lean: {'Yes' if (home_btts_strength + away_btts_strength) > 0 else 'No'}")
    print()
    
    print("3. CORNER KICK ANALYSIS")
    print("-" * 40)
    
    home_corner_strength = team_corner_strength(
        home_data['shots'], home_data['sot'], home_data['final_third_pressure'], 
        home_data['width_crossing'], home_data['tempo'], 1,  # home advantage
        home_data['missing_cb'], home_data['missing_gk'], home_data['missing_attacker']
    )
    
    away_corner_strength = team_corner_strength(
        away_data['shots'], away_data['sot'], away_data['final_third_pressure'], 
        away_data['width_crossing'], away_data['tempo'], 0,  # away
        away_data['missing_cb'], away_data['missing_gk'], away_data['missing_attacker']
    )
    
    print(f"   Sweden Corner Strength: {home_corner_strength:.2f}")
    print(f"   Greece Corner Strength: {away_corner_strength:.2f}")
    print()
    
    print("4. EXPECTED GOALS PROJECTION")
    print("-" * 40)
    
    home_lam = estimate_team_goals(
        home_data['xg_for'], home_data['sot'], home_data['tempo'], 1,  # home advantage
        home_data['missing_attacker'], home_data['missing_creator'],
        away_data['xg_against'], away_data['missing_cb'], away_data['missing_gk']
    )
    
    away_lam = estimate_team_goals(
        away_data['xg_for'], away_data['sot'], away_data['tempo'], 0,  # away
        away_data['missing_attacker'], away_data['missing_creator'],
        home_data['xg_against'], home_data['missing_cb'], home_data['missing_gk']
    )
    
    total_lam = home_lam + away_lam
    
    print(f"   Sweden Expected Goals: {home_lam:.2f}")
    print(f"   Greece Expected Goals: {away_lam:.2f}")
    print(f"   Total Expected Goals: {total_lam:.2f}")
    print()
    
    print("5. MONEYLINE (1X2) ANALYSIS")
    print("-" * 40)
    
    p_home_win, p_draw, p_away_win = calculate_moneyline_prob(home_lam, away_lam)
    
    print(f"   Sweden Win Probability: {p_home_win:.3f} ({p_home_win*100:.1f}%)")
    print(f"   Draw Probability: {p_draw:.3f} ({p_draw*100:.1f}%)")
    print(f"   Greece Win Probability: {p_away_win:.3f} ({p_away_win*100:.1f}%)")
    
    # Moneyline recommendation
    if p_home_win >= 0.50:
        ml_lean = "Sweden Win"
    elif p_away_win >= 0.40:
        ml_lean = "Greece Win or Draw (Double Chance)"
    else:
        ml_lean = "Sweden Win (narrow)"
    
    print(f"   Moneyline Recommendation: {ml_lean}")
    print()
    
    print("6. GOALS MARKET PROBABILITIES")
    print("-" * 40)
    
    p_over_15 = poisson_over_prob(total_lam, 1.5)
    p_over_25 = poisson_over_prob(total_lam, 2.5)
    p_over_35 = poisson_over_prob(total_lam, 3.5)
    p_under_25 = 1 - p_over_25
    
    print(f"   Over 1.5 Goals Probability: {p_over_15:.3f}")
    print(f"   Over 2.5 Goals Probability: {p_over_25:.3f}")
    print(f"   Over 3.5 Goals Probability: {p_over_35:.3f}")
    print(f"   Under 2.5 Goals Probability: {p_under_25:.3f}")
    print()
    
    print("7. BTTS ANALYSIS")
    print("-" * 40)
    
    btts_prob = estimate_btts_prob(home_data['xg_for'], away_data['xg_for'], 
                                   home_btts_strength, away_btts_strength)
    
    # Adjustments
    defensive_weakness = (home_data['xg_against'] + away_data['xg_against'] - 2.5) * 0.05
    btts_prob = clamp(btts_prob + defensive_weakness)
    
    missing_defenders = (home_data['missing_cb'] + home_data['missing_gk'] + 
                        away_data['missing_cb'] + away_data['missing_gk']) * 0.02
    btts_prob = clamp(btts_prob + missing_defenders)
    
    tempo_factor = (home_data['tempo'] + away_data['tempo']) * 0.03
    btts_prob = clamp(btts_prob + tempo_factor)
    
    print(f"   BTTS Probability: {btts_prob:.3f}")
    print(f"   BTTS Recommendation: {btts_recommendation(btts_prob)}")
    print()
    
    print("8. CORNERS PROJECTION")
    print("-" * 40)
    
    corner_total = estimate_corner_total(
        home_corner_strength, away_corner_strength,
        weather_penalty=0, referee_flow=0,
        must_win_home=0, must_win_away=0
    )
    
    p_corners_85 = poisson_over_prob(corner_total, 8.5)
    p_corners_95 = poisson_over_prob(corner_total, 9.5)
    p_corners_105 = poisson_over_prob(corner_total, 10.5)
    
    # Team corners projection
    home_corner_proj = corner_total * (home_corner_strength / (home_corner_strength + away_corner_strength + 0.01))
    away_corner_proj = corner_total * (away_corner_strength / (home_corner_strength + away_corner_strength + 0.01))
    
    print(f"   Projected Total Corners: {corner_total:.1f}")
    print(f"   Sweden Projected Corners: {home_corner_proj:.1f}")
    print(f"   Greece Projected Corners: {away_corner_proj:.1f}")
    print(f"   Over 8.5 Corners Probability: {p_corners_85:.3f}")
    print(f"   Over 9.5 Corners Probability: {p_corners_95:.3f}")
    print(f"   Over 10.5 Corners Probability: {p_corners_105:.3f}")
    print()
    
    print("9. MARKET LINE ANALYSIS")
    print("-" * 40)
    
    # Goals market recommendation
    if market_data['total'] <= 1.5:
        prob_over = p_over_15
    elif market_data['total'] <= 2.5:
        prob_over = p_over_25
    else:
        prob_over = p_over_35
    
    goals_lean = market_recommendation(prob_over, market_data['total'])
    
    # Corners market recommendation
    if market_data['corner_total'] <= 8.5:
        prob_corners_over = p_corners_85
    elif market_data['corner_total'] <= 9.5:
        prob_corners_over = p_corners_95
    else:
        prob_corners_over = p_corners_105
    
    corners_lean = market_recommendation(prob_corners_over, market_data['corner_total'])
    
    print(f"   Goals Total Line: {market_data['total']}")
    print(f"   Goals Recommendation: {goals_lean}")
    print(f"   Corners Total Line: {market_data['corner_total']}")
    print(f"   Corners Recommendation: {corners_lean}")
    print()
    
    # ========================================================================
    # MODEL CALCULATIONS USING UNIVERSAL MATCH FUNCTION
    # ========================================================================
    
    print("10. UNIVERSAL MODEL ANALYSIS")
    print("-" * 40)
    
    # Prepare data for universal match function
    core = {
        'home_team': 'Sweden',
        'away_team': 'Greece',
        'league': 'International Friendly',
        'date': '2026-06-04',
        'market_line': market_data['total'],
        'current_line': market_data['current_line'],
        'open_line': market_data['open_line'],
    }
    
    # Goals analysis
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
    
    print(f"   Goals Model Score: {goals_result['model_score']:.2f}")
    print(f"   Goals Model Probability: {goals_result['model_prob']:.3f}")
    print(f"   Goals Recommendation: {goals_result['lean']}")
    print()
    
    # BTTS analysis
    btts_result = run_universal_match('soccer_btts', core, goals_metrics)
    
    print(f"   BTTS Model Score: {btts_result['model_score']:.2f}")
    print(f"   BTTS Model Probability: {btts_result['model_prob']:.3f}")
    print(f"   BTTS Recommendation: {btts_result['lean']}")
    print()
    
    # Corners analysis
    corners_metrics = goals_metrics.copy()  # Same data for corners
    
    corners_result = run_universal_match('soccer_corners', core, corners_metrics)
    
    print(f"   Corners Model Score: {corners_result['model_score']:.2f}")
    print(f"   Corners Model Probability: {corners_result['model_prob']:.3f}")
    print(f"   Corners Recommendation: {corners_result['lean']}")
    print()
    
    # ========================================================================
    # BETTING RECOMMENDATIONS
    # ========================================================================
    
    print("11. BETTING RECOMMENDATIONS")
    print("-" * 40)
    
    recommendations = {
        'moneyline': ml_lean,
        'goals_total': goals_result['lean'],
        'btts': btts_result['lean'],
        'corners_total': corners_result['lean'],
    }
    
    for market, rec in recommendations.items():
        print(f"   {market.replace('_', ' ').title()}: {rec}")
    print()
    
    # ========================================================================
    # KEY FACTORS SUMMARY
    # ========================================================================
    
    print("12. KEY HANDICAPPING FACTORS SUMMARY")
    print("-" * 40)
    print()
    print("   FACTORS FAVORING SWEDEN:")
    print("   [+] Home advantage")
    print(f"   [+] Better xG for ({home_data['xg_for']:.2f} vs {away_data['xg_for']:.2f})")
    print(f"   [+] More shots per game ({home_data['shots']:.1f} vs {away_data['shots']:.1f})")
    print(f"   [+] Better defensive record ({home_data['goals_against']:.1f} GA vs {away_data['goals_against']:.1f} GA)")
    print(f"   [+] More clean sheets ({home_data['clean_sheets_last10']} vs {away_data['clean_sheets_last10']} in last 10)")
    print("   [+] No missing key players")
    print(f"   [+] Higher corner strength ({home_corner_strength:.2f} vs {away_corner_strength:.2f})")
    print()
    print("   FACTORS FAVORING GREECE:")
    print("   [+] Defensive organization (typical Greek style)")
    print("   [+] Sweden missing no attackers but Greece missing 1 attacker")
    print()
    print("   FACTORS FAVORING OVER:")
    print(f"   [+] Sweden's attacking intent (xG: {home_data['xg_for']:.2f})")
    print(f"   [+] Total xG suggests {total_lam:.2f} goals")
    print("   [+] Greece missing a center back")
    print()
    print("   FACTORS FAVORING UNDER:")
    print(f"   [+] Greece's defensive approach (xG against: {away_data['xg_against']:.2f})")
    print("   [+] International matches can be tactical")
    print()
    print("   FACTORS FAVORING BTTS:")
    print("   [+] Greece missing key defender")
    print(f"   [+] Sweden strong at home (xG: {home_data['xg_for']:.2f})")
    print()
    print("   FACTORS FAVORING SWEDEN CORNERS:")
    print(f"   [+] Higher shots ({home_data['shots']:.1f} vs {away_data['shots']:.1f})")
    print(f"   [+] More width and crossing ({home_data['width_crossing']:.2f} vs {away_data['width_crossing']:.2f})")
    print(f"   [+] Higher final third pressure ({home_data['final_third_pressure']:.2f} vs {away_data['final_third_pressure']:.2f})")
    print()
    
    # ========================================================================
    # FINAL RECOMMENDATION
    # ========================================================================
    
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Projected Score: Sweden {home_lam:.1f} - Greece {away_lam:.1f}")
    print(f"   Total Expected Goals: {total_lam:.2f}")
    print(f"   Moneyline: Sweden {p_home_win:.1%} | Draw {p_draw:.1%} | Greece {p_away_win:.1%}")
    print(f"   BTTS Probability: {btts_prob:.1%}")
    print(f"   Projected Corners: {corner_total:.0f}")
    print(f"   Sweden Projected Corners: {home_corner_proj:.0f}")
    print(f"   Greece Projected Corners: {away_corner_proj:.0f}")
    print()
    print("   PRIMARY RECOMMENDATIONS:")
    for market, rec in recommendations.items():
        print(f"   - {market.replace('_', ' ').title()}: {rec}")
    print()
    
    # Determine confidence level
    max_prob = max(goals_result['model_prob'], btts_result['model_prob'], corners_result['model_prob'])
    if max_prob >= 0.65:
        confidence = "HIGH"
    elif max_prob >= 0.58:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    
    print(f"   CONFIDENCE LEVEL: {confidence}")
    print()
    
    # ========================================================================
    # SAVE RESULTS TO JSON
    # ========================================================================
    
    results = {
        "game_info": {
            "home_team": "Sweden",
            "away_team": "Greece",
            "league": "International Friendly",
            "date": "2026-06-04",
            "venue": "Sweden (Home)"
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
            "moneyline": {
                "home_win_prob": round(p_home_win, 4),
                "draw_prob": round(p_draw, 4),
                "away_win_prob": round(p_away_win, 4)
            },
            "btts_probability": round(btts_prob, 4),
            "corner_total": round(corner_total, 1),
            "home_corners": round(home_corner_proj, 1),
            "away_corners": round(away_corner_proj, 1)
        },
        "probabilities": {
            "over_15": round(p_over_15, 4),
            "over_25": round(p_over_25, 4),
            "over_35": round(p_over_35, 4),
            "under_25": round(p_under_25, 4),
            "btts": round(btts_prob, 4),
            "corners_over_85": round(p_corners_85, 4),
            "corners_over_95": round(p_corners_95, 4),
            "corners_over_105": round(p_corners_105, 4)
        },
        "recommendations": recommendations,
        "model_details": {
            "home_goal_strength": round(home_goal_strength, 2),
            "away_goal_strength": round(away_goal_strength, 2),
            "home_btts_strength": round(home_btts_strength, 2),
            "away_btts_strength": round(away_btts_strength, 2),
            "home_corner_strength": round(home_corner_strength, 2),
            "away_corner_strength": round(away_corner_strength, 2),
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
    
    # Save to output
    output_path = Path("output/sweden_vs_greece_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"   Detailed results saved to: {output_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    run_comprehensive_analysis()