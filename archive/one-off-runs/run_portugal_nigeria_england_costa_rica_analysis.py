#!/usr/bin/env python
"""
Comprehensive Analysis for International Soccer Friendlies
===========================================================
Match 1: Portugal vs Nigeria (World Cup Warm-up)
Match 2: England vs Costa Rica (World Cup Warm-up)

Focus: Goals, BTTS, Match Outcome, and Tactical Analysis
"""

import sys
import json
import math
from datetime import datetime
from pathlib import Path

# Try to import scipy for Poisson calculations
try:
    from scipy.stats import poisson
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("Installing scipy...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "scipy"])
    from scipy.stats import poisson
    HAS_SCIPY = True

# Import the MultiSportModel functions
from MultiSportModel import (
    team_goal_strength,
    team_btts_strength,
    team_corner_strength,
    estimate_team_goals,
    estimate_btts_prob,
    estimate_corner_total,
    poisson_over_prob,
    poisson_at_least_one,
    market_recommendation,
    btts_recommendation,
    get_league_config,
    to_num,
    sigmoid,
    clamp,
)


def analyze_match(
    home_team, away_team, home_data, away_data, market_data, venue,
    date="2026-06-10", league="International_Friendly", context_notes=""
):
    """Analyze a soccer match with comprehensive betting analysis"""
    
    print("=" * 80)
    print(f"COMPREHENSIVE MATCH ANALYSIS: {home_team} vs {away_team}")
    print(f"{league} - {date}")
    print(f"Venue: {venue}")
    if context_notes:
        print(f"Context: {context_notes}")
    print("=" * 80)
    print()
    
    config = get_league_config(league)
    
    # 1. TEAM OFFENSIVE/DEFENSIVE ANALYSIS
    print("1. TEAM OFFENSIVE/DEFENSIVE ANALYSIS")
    print("-" * 40)
    
    print(f"   {home_team}:")
    print(f"      xG For: {home_data['xg_for']:.2f} | xG Against: {home_data['xg_against']:.2f}")
    print(f"      Goals For: {home_data['goals_for']:.1f} | Goals Against: {home_data['goals_against']:.1f}")
    print(f"      Shots: {home_data['shots']:.0f} | SoT: {home_data['sot']:.0f}")
    print(f"      Clean Sheets (last 10): {home_data['clean_sheets']}")
    print(f"      Missing Attackers: {home_data['missing_attacker']} | Creators: {home_data['missing_creator']}")
    print(f"      Tempo: {home_data['tempo']:+.2f} | Final Third Pressure: {home_data['final_third_pressure']:.2f}")
    print()
    print(f"   {away_team}:")
    print(f"      xG For: {away_data['xg_for']:.2f} | xG Against: {away_data['xg_against']:.2f}")
    print(f"      Goals For: {away_data['goals_for']:.1f} | Goals Against: {away_data['goals_against']:.1f}")
    print(f"      Shots: {away_data['shots']:.0f} | SoT: {away_data['sot']:.0f}")
    print(f"      Clean Sheets (last 10): {away_data['clean_sheets']}")
    print(f"      Missing Attackers: {away_data['missing_attacker']} | Creators: {away_data['missing_creator']}")
    print(f"      Tempo: {away_data['tempo']:+.2f} | Final Third Pressure: {away_data['final_third_pressure']:.2f}")
    print()
    
    # 2. GOAL STRENGTH ANALYSIS
    print("2. GOAL STRENGTH ANALYSIS")
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
    
    print(f"   {home_team} Goal Strength: {home_goal_strength_val:+.2f}")
    print(f"   {away_team} Goal Strength: {away_goal_strength_val:+.2f}")
    strength_diff = home_goal_strength_val - away_goal_strength_val
    print(f"   Strength Differential: {strength_diff:+.2f} ({'Home' if strength_diff > 0 else 'Away'} advantage)")
    print()
    
    # 3. EXPECTED GOALS PROJECTION
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
    
    home_lam *= config.get('goal_variance', 1.0)
    away_lam *= config.get('goal_variance', 1.0)
    
    total_lam = home_lam + away_lam
    
    print(f"   {home_team} Expected Goals: {home_lam:.2f}")
    print(f"   {away_team} Expected Goals: {away_lam:.2f}")
    print(f"   Total Expected Goals: {total_lam:.2f}")
    print()
    
    p_over_15 = poisson_over_prob(total_lam, 1.5)
    p_over_25 = poisson_over_prob(total_lam, 2.5)
    p_over_35 = poisson_over_prob(total_lam, 3.5)
    
    print(f"   Over 1.5 Goals Probability: {p_over_15:.3f}")
    print(f"   Over 2.5 Goals Probability: {p_over_25:.3f}")
    print(f"   Over 3.5 Goals Probability: {p_over_35:.3f}")
    print()
    
    # 4. BTTS ANALYSIS
    print("4. BTTS (BOTH TEAMS TO SCORE) ANALYSIS")
    print("-" * 40)
    
    home_btts_str = team_btts_strength(
        home_data['xg_for'], home_data['xg_against'], home_data['goals_for'], home_data['goals_against'],
        home_data['sot'], home_data['tempo'], home_data['final_third_pressure'], 
        home_data['missing_attacker'], home_data['missing_cb'], home_data['missing_gk'], 
        home_data['clean_sheets']
    )
    away_btts_str = team_btts_strength(
        away_data['xg_for'], away_data['xg_against'], away_data['goals_for'], away_data['goals_against'],
        away_data['sot'], away_data['tempo'], away_data['final_third_pressure'],
        away_data['missing_attacker'], away_data['missing_cb'], away_data['missing_gk'],
        away_data['clean_sheets']
    )
    
    btts_prob = estimate_btts_prob(home_data['xg_for'], away_data['xg_for'], 
                                    home_btts_str, away_btts_str)
    
    missing_attackers_impact = (home_data['missing_attacker'] + away_data['missing_attacker']) * -0.04
    btts_prob = max(0, min(1, btts_prob + missing_attackers_impact))
    
    defensive_weakness = (home_data['xg_against'] + away_data['xg_against'] - 2.5) * 0.05
    btts_prob = max(0, min(1, btts_prob + defensive_weakness))
    
    missing_defenders = (home_data['missing_cb'] + home_data['missing_gk'] + 
                         away_data['missing_cb'] + away_data['missing_gk']) * 0.02
    btts_prob = max(0, min(1, btts_prob + missing_defenders))
    
    btts_lean = btts_recommendation(btts_prob)
    
    print(f"   {home_team} BTTS Strength: {home_btts_str:+.2f}")
    print(f"   {away_team} BTTS Strength: {away_btts_str:+.2f}")
    print(f"   BTTS Probability: {btts_prob:.3f}")
    print(f"   BTTS Recommendation: {btts_lean}")
    print()
    
    # 5. CORNERS ANALYSIS
    print("5. CORNERS ANALYSIS")
    print("-" * 40)
    
    home_corner_str = team_corner_strength(
        home_data['shots'], home_data['sot'], home_data['final_third_pressure'], 
        home_data['width_crossing'], home_data['tempo'], 1,
        home_data['missing_cb'], home_data['missing_gk'], home_data['missing_attacker']
    )
    away_corner_str = team_corner_strength(
        away_data['shots'], away_data['sot'], away_data['final_third_pressure'],
        away_data['width_crossing'], away_data['tempo'], 0,
        away_data['missing_cb'], away_data['missing_gk'], away_data['missing_attacker']
    )
    
    corner_total = estimate_corner_total(
        home_corner_str, away_corner_str,
        market_data.get('weather_penalty', 0), market_data.get('referee_flow', 0),
        market_data.get('must_win_home', 0), market_data.get('must_win_away', 0)
    )
    
    p_corners_85 = poisson_over_prob(corner_total, 8.5)
    p_corners_95 = poisson_over_prob(corner_total, 9.5)
    p_corners_105 = poisson_over_prob(corner_total, 10.5)
    
    print(f"   {home_team} Corner Strength: {home_corner_str:+.2f}")
    print(f"   {away_team} Corner Strength: {away_corner_str:+.2f}")
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
    
    corners_lean = market_recommendation(corners_prob, corners_market_line)
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
    
    goals_lean = market_recommendation(goals_prob, goals_market_line)
    
    print(f"   Market Goals Line: {goals_market_line}")
    print(f"   Model Projected Total: {total_lam:.2f}")
    print(f"   Over Probability: {goals_prob:.3f}")
    print(f"   Goals Recommendation: {goals_lean}")
    print()
    
    # 7. MATCH OUTCOME PROJECTION
    print("7. MATCH OUTCOME PROJECTION")
    print("-" * 40)
    
    max_goals = 6
    home_win_prob = 0.0
    draw_prob = 0.0
    away_win_prob = 0.0
    
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            prob = poisson.pmf(h, home_lam) * poisson.pmf(a, away_lam)
            if h > a:
                home_win_prob += prob
            elif h == a:
                draw_prob += prob
            else:
                away_win_prob += prob
    
    total_prob = home_win_prob + draw_prob + away_win_prob
    if total_prob > 0:
        home_win_prob /= total_prob
        draw_prob /= total_prob
        away_win_prob /= total_prob
    
    home_advantage = 0.08
    home_win_prob = min(0.95, home_win_prob + home_advantage * (1 - home_win_prob))
    away_win_prob = max(0.01, away_win_prob - home_advantage * away_win_prob)
    draw_prob = 1 - home_win_prob - away_win_prob
    
    print(f"   {home_team} Win Probability: {home_win_prob:.3f}")
    print(f"   Draw Probability: {draw_prob:.3f}")
    print(f"   {away_team} Win Probability: {away_win_prob:.3f}")
    
    if home_win_prob >= 0.55:
        outcome_lean = f"Home Win ({home_team})"
    elif away_win_prob >= 0.45:
        outcome_lean = f"Away Win ({away_team})"
    elif draw_prob >= 0.30:
        outcome_lean = "Draw"
    else:
        outcome_lean = f"Home Win ({home_team})" if home_win_prob > away_win_prob else f"Away Win ({away_team})"
    
    print(f"   Outcome Recommendation: {outcome_lean}")
    print()
    
    # 8. KEY HANDICAPPING FACTORS
    print("8. KEY HANDICAPPING FACTORS")
    print("-" * 40)
    print()
    
    print(f"   FACTORS FAVORING {home_team.upper()}:")
    if home_goal_strength_val > away_goal_strength_val:
        print(f"   [+] Better goal strength ({home_goal_strength_val:+.2f} vs {away_goal_strength_val:+.2f})")
    if home_data['xg_for'] > away_data['xg_for']:
        print(f"   [+] Higher xG ({home_data['xg_for']:.2f} vs {away_data['xg_for']:.2f})")
    if home_data['xg_against'] < away_data['xg_against']:
        print(f"   [+] Better defensive xG ({home_data['xg_against']:.2f} vs {away_data['xg_against']:.2f})")
    if home_data['clean_sheets'] > away_data['clean_sheets']:
        print(f"   [+] More clean sheets ({home_data['clean_sheets']} vs {away_data['clean_sheets']})")
    if home_data['missing_attacker'] < away_data['missing_attacker']:
        print(f"   [+] More attacking options (missing {home_data['missing_attacker']} vs {away_data['missing_attacker']})")
    print()
    
    print(f"   FACTORS FAVORING {away_team.upper()}:")
    if away_goal_strength_val > home_goal_strength_val:
        print(f"   [+] Better goal strength ({away_goal_strength_val:+.2f} vs {home_goal_strength_val:+.2f})")
    if away_data['xg_for'] > home_data['xg_for']:
        print(f"   [+] Higher xG ({away_data['xg_for']:.2f} vs {home_data['xg_for']:.2f})")
    if away_data['xg_against'] < home_data['xg_against']:
        print(f"   [+] Better defensive xG ({away_data['xg_against']:.2f} vs {home_data['xg_against']:.2f})")
    if away_data['clean_sheets'] > home_data['clean_sheets']:
        print(f"   [+] More clean sheets ({away_data['clean_sheets']} vs {home_data['clean_sheets']})")
    if away_data['missing_attacker'] < home_data['missing_attacker']:
        print(f"   [+] More attacking options (missing {away_data['missing_attacker']} vs {home_data['missing_attacker']})")
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
    print(f"   Goals (O/U {goals_market_line}): {goals_lean}")
    print(f"   BTTS: {btts_lean}")
    print(f"   Corners (O/U {corners_market_line}): {corners_lean}")
    print()
    
    results = {
        "game_info": {
            "home_team": home_team,
            "away_team": away_team,
            "league": league,
            "date": date,
            "venue": venue,
            "context": context_notes
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
            "recommendation": goals_lean,
        },
        "btts_analysis": {
            "home_btts_strength": round(home_btts_str, 2),
            "away_btts_strength": round(away_btts_str, 2),
            "btts_probability": round(btts_prob, 3),
            "recommendation": btts_lean,
        },
        "corners_analysis": {
            "home_corner_strength": round(home_corner_str, 2),
            "away_corner_strength": round(away_corner_str, 2),
            "projected_total": round(corner_total, 1),
            "over_85_prob": round(p_corners_85, 3),
            "over_95_prob": round(p_corners_95, 3),
            "over_105_prob": round(p_corners_105, 3),
            "market_line": corners_market_line,
            "recommendation": corners_lean,
        },
        "recommendations": {
            "match_outcome": outcome_lean,
            "goals": goals_lean,
            "btts": btts_lean,
            "corners": corners_lean,
        },
        "goal_strength": {
            "home": round(home_goal_strength_val, 2),
            "away": round(away_goal_strength_val, 2),
        },
        "timestamp": datetime.now().isoformat()
    }
    
    return results


def run_portugal_vs_nigeria():
    """Run analysis for Portugal vs Nigeria - World Cup Warm-up"""
    
    print("\n" + "=" * 80)
    print("WORLD CUP WARM-UP: PORTUGAL vs NIGERIA")
    print("International Friendly - June 10, 2026")
    print("=" * 80 + "\n")
    
    home_data = {
        'xg_for': 2.10,
        'xg_against': 0.95,
        'shots': 16.0,
        'sot': 5.8,
        'goals_for': 2.0,
        'goals_against': 0.8,
        'clean_sheets': 6,
        'missing_attacker': 1,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.45,
        'width_crossing': 0.70,
        'final_third_pressure': 0.65,
    }
    
    away_data = {
        'xg_for': 0.85,
        'xg_against': 1.65,
        'shots': 8.5,
        'sot': 2.8,
        'goals_for': 0.9,
        'goals_against': 1.4,
        'clean_sheets': 2,
        'missing_attacker': 2,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': -0.15,
        'width_crossing': 0.35,
        'final_third_pressure': 0.25,
    }
    
    market_data = {
        'goals_line': 2.5,
        'corners_line': 9.5,
        'weather_penalty': 0,
        'referee_flow': 0,
        'must_win_home': 1,
        'must_win_away': 0,
    }
    
    context = (
        "Portugal's final World Cup warm-up with PSG core returning. "
        "Nigeria severely depleted without Osimhen and Lookman. "
        "Sharp money on Portugal -1.5 or BTTS No."
    )
    
    result = analyze_match(
        home_team="Portugal",
        away_team="Nigeria",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Estadio Dr. Magalhaes Pessoa, Leiria, Portugal",
        date="2026-06-10",
        league="International_Friendly",
        context_notes=context
    )
    
    return result


def run_england_vs_costa_rica():
    """Run analysis for England vs Costa Rica - World Cup Warm-up"""
    
    print("\n" + "=" * 80)
    print("WORLD CUP WARM-UP: ENGLAND vs COSTA RICA")
    print("International Friendly - June 10, 2026")
    print("=" * 80 + "\n")
    
    home_data = {
        'xg_for': 2.30,
        'xg_against': 0.80,
        'shots': 17.0,
        'sot': 6.2,
        'goals_for': 2.2,
        'goals_against': 0.7,
        'clean_sheets': 7,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.40,
        'width_crossing': 0.55,
        'final_third_pressure': 0.60,
    }
    
    away_data = {
        'xg_for': 0.70,
        'xg_against': 1.80,
        'shots': 7.0,
        'sot': 2.2,
        'goals_for': 0.7,
        'goals_against': 1.6,
        'clean_sheets': 1,
        'missing_attacker': 0,
        'missing_creator': 1,
        'missing_cb': 0,
        'missing_gk': 1,
        'tempo': -0.20,
        'width_crossing': 0.30,
        'final_third_pressure': 0.20,
    }
    
    market_data = {
        'goals_line': 2.5,
        'corners_line': 9.5,
        'weather_penalty': 0,
        'referee_flow': 0,
        'must_win_home': 1,
        'must_win_away': 0,
    }
    
    context = (
        "England demands rebound after unconvincing 1-0 vs New Zealand. "
        "Kane has 11 goals in last 11 appearances. "
        "Costa Rica in transition, winless in 2026, without Navas. "
        "Sharp money on England clean sheet (BTTS No)."
    )
    
    result = analyze_match(
        home_team="England",
        away_team="Costa Rica",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Camping World Stadium, Orlando, USA",
        date="2026-06-10",
        league="International_Friendly",
        context_notes=context
    )
    
    return result


def main():
    """Run both international friendly analyses"""
    
    print("=" * 80)
    print("INTERNATIONAL FRIENDLIES COMPREHENSIVE ANALYSIS")
    print("World Cup Warm-up Matches - June 10, 2026")
    print("=" * 80)
    
    portugal_nigeria_result = run_portugal_vs_nigeria()
    england_costa_rica_result = run_england_vs_costa_rica()
    
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / "portugal_vs_nigeria_analysis.json", 'w') as f:
        json.dump(portugal_nigeria_result, f, indent=2)
    
    with open(output_dir / "england_vs_costa_rica_analysis.json", 'w') as f:
        json.dump(england_costa_rica_result, f, indent=2)
    
    print("\n" + "=" * 80)
    print("COMBINED RESULTS SUMMARY")
    print("=" * 80)
    print()
    
    print("PORTUGAL vs NIGERIA:")
    print(f"  Projected Score: Portugal {portugal_nigeria_result['projections']['home_expected_goals']:.1f} - Nigeria {portugal_nigeria_result['projections']['away_expected_goals']:.1f}")
    print(f"  Portugal Win Prob: {portugal_nigeria_result['projections']['home_win_prob']:.1%}")
    print(f"  Match Outcome: {portugal_nigeria_result['recommendations']['match_outcome']}")
    print(f"  Goals (O/U 2.5): {portugal_nigeria_result['recommendations']['goals']}")
    print(f"  BTTS: {portugal_nigeria_result['recommendations']['btts']}")
    print(f"  Over 2.5 Prob: {portugal_nigeria_result['goals_analysis']['over_25_prob']:.1%}")
    print(f"  BTTS Prob: {portugal_nigeria_result['btts_analysis']['btts_probability']:.1%}")
    print()
    
    print("ENGLAND vs COSTA RICA:")
    print(f"  Projected Score: England {england_costa_rica_result['projections']['home_expected_goals']:.1f} - Costa Rica {england_costa_rica_result['projections']['away_expected_goals']:.1f}")
    print(f"  England Win Prob: {england_costa_rica_result['projections']['home_win_prob']:.1%}")
    print(f"  Match Outcome: {england_costa_rica_result['recommendations']['match_outcome']}")
    print(f"  Goals (O/U 2.5): {england_costa_rica_result['recommendations']['goals']}")
    print(f"  BTTS: {england_costa_rica_result['recommendations']['btts']}")
    print(f"  Over 2.5 Prob: {england_costa_rica_result['goals_analysis']['over_25_prob']:.1%}")
    print(f"  BTTS Prob: {england_costa_rica_result['btts_analysis']['btts_probability']:.1%}")
    print()
    
    print(f"Results saved to:")
    print(f"  - output/portugal_vs_nigeria_analysis.json")
    print(f"  - output/england_vs_costa_rica_analysis.json")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()