#!/usr/bin/env python
"""
COMPREHENSIVE WORLD CUP ANALYSIS
Match 1: Argentina vs Algeria (Group J)
Match 2: Iraq vs Norway
World Cup - June 16, 2026
"""

import sys
import json
import math
from datetime import datetime
from pathlib import Path

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


def analyze_soccer_match(home_team, away_team, home_data, away_data, market_data, league="World Cup"):
    """Analyze a single soccer match and return results"""
    
    print("=" * 80)
    print(f"COMPREHENSIVE MATCH ANALYSIS: {home_team} vs {away_team}")
    print(f"{league} - June 16, 2026")
    print("=" * 80)
    print()
    
    # 1. TEAM OFFENSIVE ANALYSIS
    print("1. TEAM OFFENSIVE ANALYSIS")
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
    
    print(f"   {home_team} Goal Strength: {home_goal_strength:.2f}")
    print(f"   {away_team} Goal Strength: {away_goal_strength:.2f}")
    print()
    
    # 2. TEAM DEFENSIVE ANALYSIS
    print("2. TEAM DEFENSIVE & BTTS ANALYSIS")
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
    
    print(f"   {home_team} BTTS Strength: {home_btts_strength:.2f}")
    print(f"   {away_team} BTTS Strength: {away_btts_strength:.2f}")
    print()
    
    # 3. CORNER KICK ANALYSIS
    print("3. CORNER KICK ANALYSIS")
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
    
    print(f"   {home_team} Corner Strength: {home_corner_strength:.2f}")
    print(f"   {away_team} Corner Strength: {away_corner_strength:.2f}")
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
    
    # 5. GOALS MARKET PROBABILITIES
    print("5. GOALS MARKET PROBABILITIES")
    print("-" * 40)
    
    p_over_15 = poisson_over_prob(total_lam, 1.5)
    p_over_25 = poisson_over_prob(total_lam, 2.5)
    p_over_35 = poisson_over_prob(total_lam, 3.5)
    p_over_45 = poisson_over_prob(total_lam, 4.5)
    
    print(f"   Over 1.5 Goals: {p_over_15:.1%}")
    print(f"   Over 2.5 Goals: {p_over_25:.1%}")
    print(f"   Over 3.5 Goals: {p_over_35:.1%}")
    print(f"   Over 4.5 Goals: {p_over_45:.1%}")
    print()
    
    # 6. BTTS ANALYSIS
    print("6. BOTH TEAMS TO SCORE (BTTS)")
    print("-" * 40)
    
    btts_prob = estimate_btts_prob(home_data['xg_for'], away_data['xg_for'], 
                                   home_btts_strength, away_btts_strength)
    
    defensive_weakness = (home_data['xg_against'] + away_data['xg_against'] - 2.5) * 0.05
    btts_prob = clamp(btts_prob + defensive_weakness)
    missing_defenders = (home_data['missing_cb'] + home_data['missing_gk'] + 
                        away_data['missing_cb'] + away_data['missing_gk']) * 0.02
    btts_prob = clamp(btts_prob + missing_defenders)
    tempo_factor = (home_data['tempo'] + away_data['tempo']) * 0.03
    btts_prob = clamp(btts_prob + tempo_factor)
    
    print(f"   BTTS Probability: {btts_prob:.1%}")
    print(f"   BTTS Recommendation: {btts_recommendation(btts_prob)}")
    print()
    
    # 7. CORNERS PROJECTION
    print("7. CORNERS PROJECTION")
    print("-" * 40)
    
    corner_total = estimate_corner_total(
        home_corner_strength, away_corner_strength,
        weather_penalty=0, referee_flow=0,
        must_win_home=1 if home_data.get('must_win', False) else 0, 
        must_win_away=1 if away_data.get('must_win', False) else 0
    )
    
    print(f"   Projected Total Corners: {corner_total:.1f}")
    print()
    
    # 8. MARKET LINE ANALYSIS
    print("8. MARKET LINE ANALYSIS")
    print("-" * 40)
    
    if market_data['total'] <= 1.5:
        prob_over = p_over_15
    elif market_data['total'] <= 2.5:
        prob_over = p_over_25
    else:
        prob_over = p_over_35
    
    goals_lean = market_recommendation(prob_over, market_data['total'])
    
    # Expected value calculation for Under 2.5
    implied_prob_under = 1 - prob_over
    
    print(f"   Goals Total Line: {market_data['total']}")
    print(f"   Model Over Probability: {prob_over:.1%}")
    print(f"   Goals Recommendation: {goals_lean}")
    print()
    
    # 9. MODEL ANALYSIS
    print("9. UNIVERSAL MODEL ANALYSIS")
    print("-" * 40)
    
    core = {
        'home_team': home_team,
        'away_team': away_team,
        'league': league,
        'date': '2026-06-16',
        'market_line': market_data['total'],
        'current_line': market_data['total'],
        'open_line': market_data['total'],
    }
    
    metrics = {
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
    
    goals_result = run_universal_match('soccer_goals', core, metrics)
    btts_result = run_universal_match('soccer_btts', core, metrics)
    corners_result = run_universal_match('soccer_corners', core, metrics)
    
    print(f"   Goals Model Score: {goals_result['model_score']:.2f} (Prob: {goals_result['model_prob']:.3f})")
    print(f"   Goals Recommendation: {goals_result['lean']}")
    print(f"   BTTS Model Score: {btts_result['model_score']:.2f} (Prob: {btts_result['model_prob']:.3f})")
    print(f"   BTTS Recommendation: {btts_result['lean']}")
    print(f"   Corners Model Score: {corners_result['model_score']:.2f} (Prob: {corners_result['model_prob']:.3f})")
    print(f"   Corners Recommendation: {corners_result['lean']}")
    print()
    
    # 10. FINAL RECOMMENDATIONS
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   PROJECTED SCORE: {home_team} {home_lam:.1f} - {away_team} {away_lam:.1f}")
    print(f"   TOTAL EXPECTED GOALS: {total_lam:.2f}")
    print(f"   BTTS PROBABILITY: {btts_prob:.1%}")
    print(f"   PROJECTED CORNERS: {corner_total:.0f}")
    print()
    print("   PRIMARY RECOMMENDATIONS:")
    print(f"   [1] Goals Total ({market_data['total']}): {goals_result['lean']}")
    print(f"   [2] BTTS: {btts_result['lean']}")
    print(f"   [3] Corners: {corners_result['lean']}")
    print()
    
    # Determine confidence
    max_prob = max(goals_result['model_prob'], btts_result['model_prob'], corners_result['model_prob'])
    if max_prob >= 0.65:
        confidence = "HIGH"
    elif max_prob >= 0.58:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    
    print(f"   CONFIDENCE LEVEL: {confidence}")
    print()
    
    results = {
        "game_info": {
            "home_team": home_team,
            "away_team": away_team,
            "league": league,
            "date": "2026-06-16"
        },
        "team_metrics": {"home": home_data, "away": away_data},
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
        },
        "recommendations": {
            "goals_total": goals_result['lean'],
            "btts": btts_result['lean'],
            "corners_total": corners_result['lean'],
        },
        "model_details": {
            "home_goal_strength": round(home_goal_strength, 2),
            "away_goal_strength": round(away_goal_strength, 2),
            "goals_model_prob": goals_result['model_prob'],
            "btts_model_prob": btts_result['model_prob'],
        },
        "confidence": confidence,
        "timestamp": datetime.now().isoformat()
    }
    
    return results


def run_all_analyses():
    """Run analysis for Argentina vs Algeria and Iraq vs Norway"""
    
    # ========================================================================
    # MATCH 1: ARGENTINA vs ALGERIA (Group J)
    # ========================================================================
    print("=" * 80)
    print("WORLD CUP GROUP J: ARGENTINA vs ALGERIA")
    print("=" * 80)
    print()
    
    # Argentina (Home)
    # Elite attack: outscored last 3 friendlies 10-0
    # Projected 65-70% possession with Enzo Fernández, Mac Allister
    # Key: Will face compact low block — need to break down 10-man wall
    home_data = {
        'xg_for': 2.40,           # Elite - attacking talent (Messi, Alvarez, etc.)
        'xg_against': 0.70,       # Excellent defense
        'shots': 16.0,            # High shot volume
        'sot': 6.2,               # Great shot quality
        'goals_for': 2.3,         # Strong scoring (10-0 in last 3 friendlies)
        'goals_against': 0.5,     # Excellent defending (3 clean sheets)
        'clean_sheets_last10': 6, # Strong defensive organization
        'missing_attacker': 0,    # Full strength
        'missing_creator': 0,     # Full strength
        'missing_cb': 0,          # Defensive unit intact
        'missing_gk': 0,          # GK available
        'tempo': 0.45,            # Controlled but can accelerate
        'width_crossing': 0.70,   # Good width (Tagliafico, Molina)
        'final_third_pressure': 0.85,  # High pressure in final third
        'possession_pct': 67,     # Projected 65-70% possession
        'must_win': True,         # Group stage — need result
    }
    
    # Algeria (Away)
    # Topped CAF qualifying, rigid defensive unit (Aissa Mandi)
    # 4 consecutive clean sheets entering tournament
    # Will deploy compact low block, rely on Amoura counter-attacks
    # Never won WC match when conceding first (0-2-6)
    away_data = {
        'xg_for': 0.85,           # Low - relies on counter-attacks (Amoura pace)
        'xg_against': 1.10,       # Solid - 4 consecutive clean sheets in qualifying
        'shots': 8.5,             # Low shot volume (defensive setup)
        'sot': 2.8,               # Limited chances
        'goals_for': 0.80,        # Limited scoring output
        'goals_against': 0.70,    # Excellent defending (4 straight clean sheets)
        'clean_sheets_last10': 5, # Strong defensive record
        'missing_attacker': 0,    # Amoura available
        'missing_creator': 1,     # Creative midfielder limited
        'missing_cb': 0,          # Aissa Mandi anchors defense
        'missing_gk': 0,          # GK available
        'tempo': -0.15,           # Deliberate, slow tempo (low block)
        'width_crossing': 0.40,   # Compact, narrow defensively
        'final_third_pressure': 0.30,  # Sit deep, don't press high
        'possession_pct': 33,     # Projected 30-35% possession
        'must_win': False,        # Can play for draw
    }
    
    # Market data (from user)
    market_data_1 = {
        'total': 2.5,
        'moneyline_home': -255,   # Argentina -251 to -260
        'moneyline_away': +770,   # Algeria +738 to +800
        'moneyline_draw': +360,
        'spread_home': -1.5,      # Argentina -1.5 (+115)
        'spread_away': +1.5,      # Algeria +1.5 (-150)
        'over_odds': -104,        # Over 2.5 (-104)
        'under_odds': -118,       # Under 2.5 (-118) — sharp action
    }
    
    result_1 = analyze_soccer_match("Argentina", "Algeria", home_data, away_data, market_data_1, "World Cup Group J")
    
    # Save match 1
    output_path = Path("output/argentina_vs_algeria_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(result_1, f, indent=2)
    print(f"   Detailed results saved to: {output_path}")
    print()
    
    # ========================================================================
    # MATCH 2: IRAQ vs NORWAY
    # ========================================================================
    print("=" * 80)
    print("WORLD CUP: IRAQ vs NORWAY")
    print("=" * 80)
    print()
    
    # Iraq
    # Underdog — defensive, counter-attacking style
    # Will sit deep and try to frustrate Norway
    home_data_2 = {
        'xg_for': 0.90,           # Limited attacking threat
        'xg_against': 1.50,       # Vulnerable defense
        'shots': 8.0,             # Low shot volume
        'sot': 2.9,               # Few chances on target
        'goals_for': 0.85,        # Low scoring
        'goals_against': 1.4,     # Leaky defense
        'clean_sheets_last10': 2, # Few clean sheets
        'missing_attacker': 0,    # Available
        'missing_creator': 1,     # Creative player limited
        'missing_cb': 1,          # Missing defender
        'missing_gk': 0,          # GK available
        'tempo': -0.10,           # Slow tempo
        'width_crossing': 0.40,   # Narrow play
        'final_third_pressure': 0.35,  # Sit deep
        'must_win': True,         # Underdog needs points
    }
    
    # Norway
    # Stronger team — Haaland-led attack
    # Should dominate possession and chances
    away_data_2 = {
        'xg_for': 1.80,           # Strong — Haaland is elite finisher
        'xg_against': 0.95,       # Decent defense
        'shots': 13.5,            # Good shot volume
        'sot': 5.0,               # Solid shot quality
        'goals_for': 1.7,         # Good scoring output
        'goals_against': 0.9,     # Solid defending
        'clean_sheets_last10': 4, # Decent defensive record
        'missing_attacker': 0,    # Haaland available
        'missing_creator': 0,     # Ødegaard available
        'missing_cb': 0,          # Defensive unit intact
        'missing_gk': 0,          # GK available
        'tempo': 0.30,            # Up-tempo
        'width_crossing': 0.65,   # Good width
        'final_third_pressure': 0.70,  # Press in final third
        'possession_pct': 58,     # Should dominate possession
        'must_win': True,         # Need win against lower-ranked opponent
    }
    
    # Market data (estimated for Iraq vs Norway)
    market_data_2 = {
        'total': 2.5,
        'moneyline_home': +400,   # Iraq big underdog
        'moneyline_away': -175,   # Norway favorite
        'moneyline_draw': +300,
        'over_odds': -110,
        'under_odds': -110,
    }
    
    result_2 = analyze_soccer_match("Iraq", "Norway", home_data_2, away_data_2, market_data_2, "World Cup")
    
    # Save match 2
    output_path = Path("output/iraq_vs_norway_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(result_2, f, indent=2)
    print(f"   Detailed results saved to: {output_path}")
    print()
    
    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    print("=" * 80)
    print("WORLD CUP JUNE 16 — MASTER RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    for name, res in [("ARG vs ALG", result_1), ("IRQ vs NOR", result_2)]:
        p = res['projections']
        print(f"  {name}:")
        print(f"    Projected: {res['game_info']['home_team']} {p['home_goals']} - {p['away_goals']} {res['game_info']['away_team']}")
        print(f"    Total Goals: {p['total_goals']} | BTTS: {p['btts_probability']:.1%}")
        print(f"    Goals: {res['recommendations']['goals_total']}")
        print(f"    BTTS: {res['recommendations']['btts']}")
        print(f"    Confidence: {res['confidence']}")
        print()


if __name__ == "__main__":
    run_all_analyses()