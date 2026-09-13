 #!/usr/bin/env python
"""
Comprehensive Analysis for Niger vs Mauritania
International Match - June 2026
"""

import sys
import json
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

def run_comprehensive_analysis():
    """Run comprehensive analysis for Niger vs Mauritania"""
    
    print("=" * 80)
    print("COMPREHENSIVE MATCH ANALYSIS: NIGER vs MAURITANIA")
    print("International Match - June 2026")
    print("=" * 80)
    print()
    
    # ========================================================================
    # TEAM DATA (Based on provided analysis - both teams have extreme structural deficiencies)
    # ========================================================================
    
    # Home Team: Niger 🇳🇪
    # Key characteristics: Struggles to maintain possession in opponent's half
    home_data = {
        'xg_for': 0.85,           # Very low - extreme deficiencies in final-third creativity
        'xg_against': 1.15,       # Decent defense but vulnerable
        'shots': 8.5,             # Low shot volume
        'sot': 2.8,               # Low shots on target
        'goals_for': 0.75,        # Very low scoring
        'goals_against': 1.0,     # Moderate defending
        'clean_sheets_last10': 4, # Solid defensive organization
        'missing_attacker': 0,    # No major squad adjustments
        'missing_creator': 1,     # Lack of creativity is structural
        'missing_cb': 0,          # Defensive unit intact
        'missing_gk': 0,          # Goalkeeper available
        'tempo': -0.2,            # Slow tempo - struggles in final third
        'width_crossing': 0.35,   # Limited width play
        'final_third_pressure': 0.30,  # Very low pressure in final third
    }
    
    # Away Team: Mauritania 🇲🇷
    # Key characteristics: Physical, direct style, minimal clear-cut chances
    away_data = {
        'xg_for': 0.90,           # Very low - minimal clear-cut chances
        'xg_against': 1.10,       # Solid defense
        'shots': 9.0,             # Low shot volume
        'sot': 3.0,               # Low shots on target
        'goals_for': 0.80,        # Very low scoring
        'goals_against': 0.95,    # Good defending
        'clean_sheets_last10': 5, # Excellent defensive organization
        'missing_attacker': 0,    # No major squad adjustments
        'missing_creator': 1,     # Lack of creativity is structural
        'missing_cb': 0,          # Rugged defensive unit intact
        'missing_gk': 0,          # Goalkeeper available
        'tempo': -0.1,            # Slow-moderate tempo
        'width_crossing': 0.40,   # Limited width play
        'final_third_pressure': 0.35,  # Low pressure in final third
    }
    
    # Market Data (Based on provided analysis)
    market_data = {
        'open_line': 2.0,         # Very low opening total
        'current_line': 2.0,      # Current total goals line
        'total': 2.0,             # Game total - very low
        'corner_total': 7.5,      # Low corner total (6.5-8.5 range)
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
    
    print(f"   Niger Goal Strength: {home_goal_strength:.2f}")
    print(f"   Mauritania Goal Strength: {away_goal_strength:.2f}")
    print(f"   Offensive Edge: {'Niger' if home_goal_strength > away_goal_strength else 'Mauritania'}")
    print(f"   [WARNING] BOTH TEAMS SHOW EXTREME OFFENSIVE DEFICIENCIES")
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
    
    print(f"   Niger BTTS Strength: {home_btts_strength:.2f}")
    print(f"   Mauritania BTTS Strength: {away_btts_strength:.2f}")
    print(f"   BTTS Lean: {'Yes' if (home_btts_strength + away_btts_strength) > 0 else 'No'}")
    print(f"   [DEFENSE] BOTH TEAMS LEAN ON RUGGED DEFENSIVE UNITS")
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
    
    print(f"   Niger Corner Strength: {home_corner_strength:.2f}")
    print(f"   Mauritania Corner Strength: {away_corner_strength:.2f}")
    print(f"   [CORNERS] LOW CORNER VOLUME EXPECTED (6.5-8.5 range)")
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
    
    print(f"   Niger Expected Goals: {home_lam:.2f}")
    print(f"   Mauritania Expected Goals: {away_lam:.2f}")
    print(f"   Total Expected Goals: {total_lam:.2f}")
    print(f"   [GOALS] EXTREMELY LOW SCORING EXPECTATION")
    print()
    
    print("5. GOALS MARKET PROBABILITIES")
    print("-" * 40)
    
    p_over_15 = poisson_over_prob(total_lam, 1.5)
    p_over_25 = poisson_over_prob(total_lam, 2.5)
    p_over_35 = poisson_over_prob(total_lam, 3.5)
    
    print(f"   Over 1.5 Goals Probability: {p_over_15:.3f}")
    print(f"   Over 2.5 Goals Probability: {p_over_25:.3f}")
    print(f"   Over 3.5 Goals Probability: {p_over_35:.3f}")
    print(f"   [STATS] 80% OF MATCHES FOR BOTH TEAMS STAY UNDER 2.5 GOALS")
    print()
    
    print("6. BTTS ANALYSIS")
    print("-" * 40)
    
    btts_prob = estimate_btts_prob(home_data['xg_for'], away_data['xg_for'], 
                                   home_btts_strength, away_btts_strength)
    
    # Adjustments for this specific matchup
    defensive_weakness = (home_data['xg_against'] + away_data['xg_against'] - 2.5) * 0.05
    btts_prob = clamp(btts_prob + defensive_weakness)
    
    missing_defenders = (home_data['missing_cb'] + home_data['missing_gk'] + 
                        away_data['missing_cb'] + away_data['missing_gk']) * 0.02
    btts_prob = clamp(btts_prob + missing_defenders)
    
    tempo_factor = (home_data['tempo'] + away_data['tempo']) * 0.03
    btts_prob = clamp(btts_prob + tempo_factor)
    
    print(f"   BTTS Probability: {btts_prob:.3f}")
    print(f"   BTTS Recommendation: {btts_recommendation(btts_prob)}")
    print(f"   [BTTS] LOW PROBABILITY - BOTH TEAMS STRUGGLE TO SCORE")
    print()
    
    print("7. CORNERS PROJECTION")
    print("-" * 40)
    
    corner_total = estimate_corner_total(
        home_corner_strength, away_corner_strength,
        weather_penalty=0, referee_flow=0,
        must_win_home=0, must_win_away=0
    )
    
    p_corners_85 = poisson_over_prob(corner_total, 8.5)
    p_corners_95 = poisson_over_prob(corner_total, 9.5)
    p_corners_105 = poisson_over_prob(corner_total, 10.5)
    
    print(f"   Projected Total Corners: {corner_total:.1f}")
    print(f"   Over 8.5 Corners Probability: {p_corners_85:.3f}")
    print(f"   Over 9.5 Corners Probability: {p_corners_95:.3f}")
    print(f"   Over 10.5 Corners Probability: {p_corners_105:.3f}")
    print(f"   [CORNERS] MINIMAL ATTACKING TRANSITIONS = LOW CORNER COUNT")
    print()
    
    print("8. MARKET LINE ANALYSIS")
    print("-" * 40)
    
    # Goals market recommendation
    if market_data['total'] <= 1.5:
        prob_over = p_over_15
    elif market_data['total'] <= 2.0:
        prob_over = p_over_25
    else:
        prob_over = p_over_25
    
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
    
    print("9. UNIVERSAL MODEL ANALYSIS")
    print("-" * 40)
    
    # Prepare data for universal match function
    core = {
        'home_team': 'Niger',
        'away_team': 'Mauritania',
        'league': 'International',
        'date': '2026-06-08',
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
    
    print("10. BETTING RECOMMENDATIONS")
    print("-" * 40)
    
    recommendations = {
        'goals_total': goals_result['lean'],
        'btts': btts_result['lean'],
        'corners_total': corners_result['lean'],
    }
    
    for market, rec in recommendations.items():
        print(f"   {market.replace('_', ' ').title()}: {rec}")
    print()
    
    # ========================================================================
    # SMART PICKS (Based on provided analysis)
    # ========================================================================
    
    print("11. SMART PICKS & MARKET ANALYSIS")
    print("-" * 40)
    print()
    print("   DOUBLE CHANCE & MONEYLINE:")
    print("   • This is a pure coin-flip market")
    print("   • Mauritania: razor-thin road favorite (+165)")
    print("   • Double Chance: Niger or Draw (-210) - SAFETY NET")
    print()
    print("   GOALS PROJECTION:")
    print("   • Market set very low bar")
    print("   • Over 1.5 line priced at -145")
    print("   • Sharp volume pushing toward low-scoring outcome")
    print()
    print("   CORNER VOLUME:")
    print("   • Low (6.5-8.5 line)")
    print("   • Minimal attacking transitions")
    print("   • Frequent midfield aerial duels")
    print()
    print("   [TOP] SAFEST WAGER: Under 2.5 Total Match Goals (-190)")
    print("   [VALUE] VALUE PLAY: Under 1.5 Goals (+115)")
    print("   [ALT] FIRST HALF: Draw (-110) - grinding nature expected")
    print()
    
    # ========================================================================
    # KEY FACTORS SUMMARY
    # ========================================================================
    
    print("12. KEY HANDICAPPING FACTORS SUMMARY")
    print("-" * 40)
    print()
    print("   FACTORS FAVORING UNDER:")
    print("   [+] 80% of matches for both teams stay under 2.5 goals")
    print("   [+] Extreme structural deficiencies in final-third creativity")
    print("   [+] Both teams lean on rugged, midfield-heavy defensive units")
    print("   [+] Designed to frustrate rather than dictate tempo")
    print("   [+] Minimal clear-cut chances created")
    print()
    print("   FACTORS FAVORING DRAW:")
    print("   [+] Pure coin-flip matchup")
    print("   [+] Both teams have similar limitations")
    print("   [+] Grinding, physical style from both sides")
    print()
    print("   FACTORS AGAINST HIGH SCORING:")
    print("   [+] Niger struggles to maintain possession in opponent's half")
    print("   [+] Mauritania plays direct style with minimal chances")
    print("   [+] Low corner volume indicates lack of attacking pressure")
    print()
    
    # ========================================================================
    # FINAL RECOMMENDATION
    # ========================================================================
    
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Projected Score: Niger {home_lam:.1f} - Mauritania {away_lam:.1f}")
    print(f"   Total Expected Goals: {total_lam:.2f}")
    print(f"   BTTS Probability: {btts_prob:.1%}")
    print(f"   Projected Corners: {corner_total:.0f}")
    print()
    print("   PRIMARY RECOMMENDATIONS:")
    print("   [1] SAFEST: Under 2.5 Total Goals (-190)")
    print("   [2] VALUE: Under 1.5 Goals (+115)")
    print("   [3] ALTERNATIVE: First Half Draw (-110)")
    print("   [4] DOUBLE CHANCE: Niger or Draw (-210)")
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
    print("   [WARNING] MATCH CHARACTERISTICS:")
    print("   - Extremely low-scoring affair expected")
    print("   - Physical, defensive battle")
    print("   - Coin-flip outcome with slight edge to draw")
    print("   - Under 2.5 goals is the strongest play")
    print()
    
    # ========================================================================
    # SAVE RESULTS TO JSON
    # ========================================================================
    
    results = {
        "game_info": {
            "home_team": "Niger",
            "away_team": "Mauritania",
            "league": "International",
            "date": "2026-06-08",
            "venue": "Neutral/International"
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
            "btts_probability": round(btts_prob, 4),
            "corner_total": round(corner_total, 1)
        },
        "probabilities": {
            "over_15": round(p_over_15, 4),
            "over_25": round(p_over_25, 4),
            "over_35": round(p_over_35, 4),
            "btts": round(btts_prob, 4),
            "corners_over_85": round(p_corners_85, 4),
            "corners_over_95": round(p_corners_95, 4),
            "corners_over_105": round(p_corners_105, 4)
        },
        "recommendations": recommendations,
        "smart_picks": {
            "safest_wager": "Under 2.5 Total Goals (-190)",
            "value_play": "Under 1.5 Goals (+115)",
            "first_half": "Draw (-110)",
            "double_chance": "Niger or Draw (-210)"
        },
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
        "match_characteristics": {
            "expected_style": "Physical, defensive, low-scoring",
            "key_factor": "Extreme offensive deficiencies for both teams",
            "likely_outcome": "Under 2.5 goals, possible draw"
        },
        "confidence": confidence,
        "timestamp": datetime.now().isoformat()
    }
    
    # Save to output
    output_path = Path("output/niger_vs_mauritania_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"   Detailed results saved to: {output_path}")
    print()
    print("=" * 80)

if __name__ == "__main__":
    run_comprehensive_analysis()