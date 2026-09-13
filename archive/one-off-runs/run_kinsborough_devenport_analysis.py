#!/usr/bin/env python
"""
Comprehensive Analysis for Soccer Match
- Kinsborough Lions vs Devenport City
Tasmanian Premier League - June 8, 2026
Focus: Goals, Corners, BTTS, and Match Outcome
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Import the updated SoccerPredictor from models
from models.soccer_predictor import (
    SoccerPredictor,
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


def analyze_soccer_match(
    home_team, away_team, home_data, away_data, market_data, venue,
    date="2026-06-08", league="Tasmanian Premier League"
):
    """Analyze a soccer match with comprehensive betting analysis using the updated model"""
    
    print("=" * 80)
    print(f"COMPREHENSIVE MATCH ANALYSIS: {home_team} vs {away_team}")
    print(f"{league} - {date}")
    print(f"Venue: {venue}")
    print("=" * 80)
    print()
    
    # Use the updated SoccerPredictor
    predictor = SoccerPredictor(league=league)
    
    # 1. TEAM OFFENSIVE/DEFENSIVE ANALYSIS
    print("1. TEAM OFFENSIVE/DEFENSIVE ANALYSIS")
    print("-" * 40)
    
    print(f"   {home_team}:")
    print(f"      xG For: {home_data['xg_for']:.2f} | xG Against: {home_data['xg_against']:.2f}")
    print(f"      Goals For: {home_data['goals_for']:.1f} | Goals Against: {home_data['goals_against']:.1f}")
    print(f"      Shots: {home_data['shots']:.0f} | SoT: {home_data['sot']:.0f}")
    print(f"      Clean Sheets (last 10): {home_data['clean_sheets']}")
    print()
    print(f"   {away_team}:")
    print(f"      xG For: {away_data['xg_for']:.2f} | xG Against: {away_data['xg_against']:.2f}")
    print(f"      Goals For: {away_data['goals_for']:.1f} | Goals Against: {away_data['goals_against']:.1f}")
    print(f"      Shots: {away_data['shots']:.0f} | SoT: {away_data['sot']:.0f}")
    print(f"      Clean Sheets (last 10): {away_data['clean_sheets']}")
    print()
    
    # 2. GOAL STRENGTH ANALYSIS
    print("2. GOAL STRENGTH ANALYSIS")
    print("-" * 40)
    
    home_goal_strength = team_goal_strength(
        home_data['xg_for'], home_data['xg_against'], home_data['shots'], home_data['sot'],
        home_data['goals_for'], home_data['goals_against'], home_data['tempo'], 1,
        home_data['missing_attacker'], home_data['missing_creator'], 
        home_data['missing_cb'], home_data['missing_gk']
    )
    away_goal_strength = team_goal_strength(
        away_data['xg_for'], away_data['xg_against'], away_data['shots'], away_data['sot'],
        away_data['goals_for'], away_data['goals_against'], away_data['tempo'], 0,
        away_data['missing_attacker'], away_data['missing_creator'],
        away_data['missing_cb'], away_data['missing_gk']
    )
    
    print(f"   {home_team} Goal Strength: {home_goal_strength:+.2f}")
    print(f"   {away_team} Goal Strength: {away_goal_strength:+.2f}")
    print()
    
    # 3. EXPECTED GOALS PROJECTION (Using updated model)
    print("3. EXPECTED GOALS PROJECTION")
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
    
    # Goal probabilities
    p_over_15 = poisson_over_prob(total_lam, 1.5)
    p_over_25 = poisson_over_prob(total_lam, 2.5)
    p_over_35 = poisson_over_prob(total_lam, 3.5)
    
    print(f"   Over 1.5 Goals Probability: {p_over_15:.3f}")
    print(f"   Over 2.5 Goals Probability: {p_over_25:.3f}")
    print(f"   Over 3.5 Goals Probability: {p_over_35:.3f}")
    print()
    
    # 4. BTTS (BOTH TEAMS TO SCORE) ANALYSIS
    print("4. BTTS (BOTH TEAMS TO SCORE) ANALYSIS")
    print("-" * 40)
    
    home_btts_strength = team_btts_strength(
        home_data['xg_for'], home_data['xg_against'], home_data['goals_for'], home_data['goals_against'],
        home_data['sot'], home_data['tempo'], home_data['final_third_pressure'], 
        home_data['missing_attacker'], home_data['missing_cb'], home_data['missing_gk'], 
        home_data['clean_sheets']
    )
    away_btts_strength = team_btts_strength(
        away_data['xg_for'], away_data['xg_against'], away_data['goals_for'], away_data['goals_against'],
        away_data['sot'], away_data['tempo'], away_data['final_third_pressure'],
        away_data['missing_attacker'], away_data['missing_cb'], away_data['missing_gk'],
        away_data['clean_sheets']
    )
    
    btts_prob = estimate_btts_prob(home_lam, away_lam, home_btts_strength, away_btts_strength)
    
    # Adjustments
    defensive_weakness = (home_data['xg_against'] + away_data['xg_against'] - 2.5) * 0.05
    btts_prob = max(0, min(1, btts_prob + defensive_weakness))
    
    missing_defenders = (home_data['missing_cb'] + home_data['missing_gk'] + 
                         away_data['missing_cb'] + away_data['missing_gk']) * 0.02
    btts_prob = max(0, min(1, btts_prob + missing_defenders))
    
    tempo_factor = (home_data['tempo'] + away_data['tempo']) * 0.03
    btts_prob = max(0, min(1, btts_prob + tempo_factor))
    
    # BTTS recommendation
    btts_confidence = min(100, max(0, 50 + (btts_prob - 0.5) * 100))
    btts_lean = "BET" if btts_confidence > 60 else "PASS"
    
    print(f"   {home_team} BTTS Strength: {home_btts_strength:+.2f}")
    print(f"   {away_team} BTTS Strength: {away_btts_strength:+.2f}")
    print(f"   BTTS Probability: {btts_prob:.3f}")
    print(f"   BTTS Confidence: {btts_confidence:.1f}%")
    print(f"   BTTS Recommendation: {btts_lean}")
    print()
    
    # 5. CORNERS ANALYSIS
    print("5. CORNERS ANALYSIS")
    print("-" * 40)
    
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
        market_data.get('weather_penalty', 0), market_data.get('referee_flow', 0),
        market_data.get('must_win_home', 0), market_data.get('must_win_away', 0)
    )
    
    p_corners_85 = poisson_over_prob(corner_total, 8.5)
    p_corners_95 = poisson_over_prob(corner_total, 9.5)
    p_corners_105 = poisson_over_prob(corner_total, 10.5)
    
    print(f"   {home_team} Corner Strength: {home_corner_strength:+.2f}")
    print(f"   {away_team} Corner Strength: {away_corner_strength:+.2f}")
    print(f"   Projected Total Corners: {corner_total:.1f}")
    print(f"   Over 8.5 Corners Probability: {p_corners_85:.3f}")
    print(f"   Over 9.5 Corners Probability: {p_corners_95:.3f}")
    print(f"   Over 10.5 Corners Probability: {p_corners_105:.3f}")
    
    corners_market_line = market_data.get('corners_line', 9.5)
    if corners_market_line <= 8.5:
        corners_prob = p_corners_85
    elif corners_market_line <= 9.5:
        corners_prob = p_corners_95
    else:
        corners_prob = p_corners_105
    
    corners_confidence = min(100, max(0, 50 + (corners_prob - 0.5) * 100))
    corners_lean = "BET" if corners_confidence > 60 else "PASS"
    print(f"   Corners Confidence: {corners_confidence:.1f}%")
    print(f"   Corners Recommendation: {corners_lean}")
    print()
    
    # 6. GOALS MARKET ANALYSIS
    print("6. GOALS MARKET ANALYSIS")
    print("-" * 40)
    
    goals_market_line = market_data.get('goals_line', 2.5)
    if goals_market_line <= 1.5:
        goals_prob = p_over_15
    elif goals_market_line <= 2.5:
        goals_prob = p_over_25
    else:
        goals_prob = p_over_35
    
    goals_edge = total_lam - goals_market_line
    goals_confidence = min(100, max(0, 50 + goals_edge * 10))
    goals_lean = "OVER" if goals_edge > 0 else "UNDER"
    goals_rec = "BET" if goals_confidence > 60 else "PASS"
    
    print(f"   Market Goals Line: {goals_market_line}")
    print(f"   Model Projected Total: {total_lam:.2f}")
    print(f"   Edge: {goals_edge:+.2f}")
    print(f"   Over Probability: {goals_prob:.3f}")
    print(f"   Confidence: {goals_confidence:.1f}%")
    print(f"   Goals Recommendation: {goals_rec} {goals_lean}")
    print()
    
    # 7. MATCH OUTCOME PROJECTION (Using Bivariate Poisson)
    print("7. MATCH OUTCOME PROJECTION")
    print("-" * 40)
    
    # Apply Dixon-Coles adjustment
    home_attack, home_defense = dixon_coles_xg_adjustment(
        home_data['xg_for'], home_data['xg_against'], 
        away_data['xg_for'], away_data['xg_against']
    )
    away_attack, away_defense = dixon_coles_xg_adjustment(
        away_data['xg_for'], away_data['xg_against'],
        home_data['xg_for'], home_data['xg_against']
    )
    
    # Calculate match outcome probabilities using Bivariate Poisson
    prob_matrix = calculate_bivariate_poisson_probabilities(home_lam, away_lam)
    
    home_win_prob = prob_matrix.apply(lambda row: row[row.index < row.name].sum(), axis=1).sum()
    away_win_prob = prob_matrix.apply(lambda row: row[row.index > row.name].sum(), axis=1).sum()
    draw_prob = prob_matrix.apply(lambda row: row[row.index == row.name].sum(), axis=1).sum()
    
    # Normalize probabilities
    total_prob = home_win_prob + away_win_prob + draw_prob
    if total_prob > 0:
        home_win_prob /= total_prob
        away_win_prob /= total_prob
        draw_prob /= total_prob
    
    print(f"   {home_team} Win Probability: {home_win_prob:.3f}")
    print(f"   Draw Probability: {draw_prob:.3f}")
    print(f"   {away_team} Win Probability: {away_win_prob:.3f}")
    
    # Match outcome recommendation
    if home_win_prob >= 0.50:
        outcome_lean = f"Home Win ({home_team})"
    elif away_win_prob >= 0.50:
        outcome_lean = f"Away Win ({away_team})"
    elif draw_prob >= 0.30:
        outcome_lean = "Draw"
    else:
        outcome_lean = "Pass"
    
    print(f"   Outcome Recommendation: {outcome_lean}")
    print()
    
    # 8. SIDE (HANDICAP) ANALYSIS
    print("8. SIDE (HANDICAP) ANALYSIS")
    print("-" * 40)
    
    side_market_line = market_data.get('side_line', 0.0)
    side_edge = (home_lam - away_lam) - side_market_line
    side_confidence = min(100, max(0, 50 + side_edge * 10))
    side_lean = "HOME" if side_edge > 0 else "AWAY"
    side_rec = "BET" if side_confidence > 60 else "PASS"
    
    print(f"   Market Side Line: {side_market_line}")
    print(f"   Model Goal Diff: {home_lam - away_lam:.2f}")
    print(f"   Edge: {side_edge:+.2f}")
    print(f"   Confidence: {side_confidence:.1f}%")
    print(f"   Side Recommendation: {side_rec} {side_lean}")
    print()
    
    # 9. KEY HANDICAPPING FACTORS
    print("9. KEY HANDICAPPING FACTORS")
    print("-" * 40)
    print()
    
    print(f"   FACTORS FAVORING {home_team.upper()}:")
    if home_goal_strength > away_goal_strength:
        print(f"   [+] Better goal strength ({home_goal_strength:+.2f} vs {away_goal_strength:+.2f})")
    if home_data['xg_for'] > away_data['xg_for']:
        print(f"   [+] Higher xG ({home_data['xg_for']:.2f} vs {away_data['xg_for']:.2f})")
    if home_data['xg_against'] < away_data['xg_against']:
        print(f"   [+] Better defensive xG ({home_data['xg_against']:.2f} vs {away_data['xg_against']:.2f})")
    if home_data['clean_sheets'] > away_data['clean_sheets']:
        print(f"   [+] More clean sheets ({home_data['clean_sheets']} vs {away_data['clean_sheets']})")
    if home_win_prob > 0.45:
        print(f"   [+] Home advantage (Win prob: {home_win_prob:.1%})")
    print()
    
    print(f"   FACTORS FAVORING {away_team.upper()}:")
    if away_goal_strength > home_goal_strength:
        print(f"   [+] Better goal strength ({away_goal_strength:+.2f} vs {home_goal_strength:+.2f})")
    if away_data['xg_for'] > home_data['xg_for']:
        print(f"   [+] Higher xG ({away_data['xg_for']:.2f} vs {home_data['xg_for']:.2f})")
    if away_data['xg_against'] < home_data['xg_against']:
        print(f"   [+] Better defensive xG ({away_data['xg_against']:.2f} vs {home_data['xg_against']:.2f})")
    if away_data['clean_sheets'] > home_data['clean_sheets']:
        print(f"   [+] More clean sheets ({away_data['clean_sheets']} vs {home_data['clean_sheets']})")
    if away_win_prob > 0.45:
        print(f"   [+] Strong away form (Win prob: {away_win_prob:.1%})")
    print()
    
    # FINAL SUMMARY
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Match: {home_team} vs {away_team}")
    print(f"   Projected Score: {home_team} {home_lam:.1f} - {away_team} {away_lam:.1f}")
    print(f"   Total Expected Goals: {total_lam:.2f}")
    print()
    print("   === BETTING RECOMMENDATIONS ===")
    print(f"   Match Outcome: {outcome_lean}")
    print(f"   Side ({side_market_line}): {side_rec} {side_lean} (Confidence: {side_confidence:.1f}%)")
    print(f"   Goals (O/U {goals_market_line}): {goals_rec} (Confidence: {goals_confidence:.1f}%)")
    print(f"   BTTS: {btts_lean} (Confidence: {btts_confidence:.1f}%)")
    print(f"   Corners (O/U {corners_market_line}): {corners_lean} (Confidence: {corners_confidence:.1f}%)")
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
        "projections": {
            "home_expected_goals": round(home_lam, 2),
            "away_expected_goals": round(away_lam, 2),
            "total_expected_goals": round(total_lam, 2),
            "home_win_prob": round(home_win_prob, 3),
            "draw_prob": round(draw_prob, 3),
            "away_win_prob": round(away_win_prob, 3),
        },
        "goals_analysis": {
            "over_15_prob": round(p_over_15, 3),
            "over_25_prob": round(p_over_25, 3),
            "over_35_prob": round(p_over_35, 3),
            "market_line": goals_market_line,
            "edge": round(goals_edge, 3),
            "confidence": round(goals_confidence, 1),
            "recommendation": goals_rec,
            "lean": goals_lean,
        },
        "btts_analysis": {
            "home_btts_strength": round(home_btts_strength, 2),
            "away_btts_strength": round(away_btts_strength, 2),
            "btts_probability": round(btts_prob, 3),
            "confidence": round(btts_confidence, 1),
            "recommendation": btts_lean,
        },
        "corners_analysis": {
            "home_corner_strength": round(home_corner_strength, 2),
            "away_corner_strength": round(away_corner_strength, 2),
            "projected_total": round(corner_total, 1),
            "over_85_prob": round(p_corners_85, 3),
            "over_95_prob": round(p_corners_95, 3),
            "over_105_prob": round(p_corners_105, 3),
            "market_line": corners_market_line,
            "confidence": round(corners_confidence, 1),
            "recommendation": corners_lean,
        },
        "side_analysis": {
            "market_line": side_market_line,
            "model_goal_diff": round(home_lam - away_lam, 2),
            "edge": round(side_edge, 3),
            "confidence": round(side_confidence, 1),
            "recommendation": side_rec,
            "lean": side_lean,
        },
        "recommendations": {
            "match_outcome": outcome_lean,
            "side": {"recommendation": side_rec, "lean": side_lean, "confidence": round(side_confidence, 1)},
            "goals": {"recommendation": goals_rec, "lean": goals_lean, "confidence": round(goals_confidence, 1)},
            "btts": {"recommendation": btts_lean, "confidence": round(btts_confidence, 1)},
            "corners": {"recommendation": corners_lean, "confidence": round(corners_confidence, 1)},
        },
        "goal_strength": {
            "home": round(home_goal_strength, 2),
            "away": round(away_goal_strength, 2),
        },
        "model_info": {
            "type": "Bivariate Poisson with Dixon-Coles adjustments",
            "league_config": predictor.config,
        },
        "timestamp": datetime.now().isoformat()
    }
    
    return results


def run_kinsborough_devenport_analysis():
    """Run analysis for Kinsborough Lions vs Devenport City"""
    
    print("\n" + "=" * 80)
    print("TASMANIAN PREMIER LEAGUE: KINSBOROUGH LIONS vs DEVENPORT CITY")
    print("June 8, 2026")
    print("=" * 80 + "\n")
    
    # Kinsborough Lions (Home) - Home team with moderate attacking prowess
    home_data = {
        'xg_for': 1.55,
        'xg_against': 1.30,
        'shots': 12.5,
        'sot': 4.3,
        'goals_for': 1.6,
        'goals_against': 1.2,
        'clean_sheets': 4,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.25,
        'width_crossing': 0.52,
        'final_third_pressure': 0.53,
    }
    
    # Devenport City (Away) - Away team with solid defense
    away_data = {
        'xg_for': 1.40,
        'xg_against': 1.35,
        'shots': 11.0,
        'sot': 3.9,
        'goals_for': 1.4,
        'goals_against': 1.3,
        'clean_sheets': 3,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.15,
        'width_crossing': 0.48,
        'final_third_pressure': 0.47,
    }
    
    market_data = {
        'goals_line': 2.5,
        'corners_line': 9.5,
        'side_line': 0.0,  # Pick'em
        'weather_penalty': 0,
        'referee_flow': 0,
        'must_win_home': 0,
        'must_win_away': 0,
    }
    
    result = analyze_soccer_match(
        home_team="Kinsborough Lions",
        away_team="Devenport City",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Kinsborough Stadium",
        date="2026-06-08",
        league="Tasmanian Premier League"
    )
    
    return result


if __name__ == "__main__":
    result = run_kinsborough_devenport_analysis()
    
    # Save results
    output_dir = Path("output/soccer")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "kinsborough_lions_vs_devenport_city_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")