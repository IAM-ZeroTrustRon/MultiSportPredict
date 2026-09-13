#!/usr/bin/env python
"""
Comprehensive Analysis for Soccer Matches - June 9, 2026
- Philippines vs Myanmar (International Friendly / AFC Qualifier)
- China PR vs Thailand (International Friendly / AFC Qualifier)

Focus: Goals, Corners, BTTS, and Match Outcome
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Import the MultiSportModel functions
from MultiSportModel import (
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
    market_recommendation,
    btts_recommendation,
    get_league_config,
    SoccerHandicapper,
)


def analyze_soccer_match(
    home_team, away_team, home_data, away_data, market_data, venue,
    date="2026-06-09", league="International_Friendly"
):
    """Analyze a soccer match with comprehensive betting analysis"""
    
    print("=" * 80)
    print(f"COMPREHENSIVE MATCH ANALYSIS: {home_team} vs {away_team}")
    print(f"{league} - {date}")
    print(f"Venue: {venue}")
    print("=" * 80)
    print()
    
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
    
    btts_prob = estimate_btts_prob(home_data['xg_for'], away_data['xg_for'], 
                                    home_btts_strength, away_btts_strength)
    
    # Adjustments
    defensive_weakness = (home_data['xg_against'] + away_data['xg_against'] - 2.5) * 0.05
    btts_prob = max(0, min(1, btts_prob + defensive_weakness))
    
    missing_defenders = (home_data['missing_cb'] + home_data['missing_gk'] + 
                         away_data['missing_cb'] + away_data['missing_gk']) * 0.02
    btts_prob = max(0, min(1, btts_prob + missing_defenders))
    
    tempo_factor = (home_data['tempo'] + away_data['tempo']) * 0.03
    btts_prob = max(0, min(1, btts_prob + tempo_factor))
    
    btts_lean = btts_recommendation(btts_prob)
    
    print(f"   {home_team} BTTS Strength: {home_btts_strength:+.2f}")
    print(f"   {away_team} BTTS Strength: {away_btts_strength:+.2f}")
    print(f"   BTTS Probability: {btts_prob:.3f}")
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
    
    # Simple win/draw/loss probability based on expected goals
    home_win_prob = home_lam / (home_lam + away_lam) * 0.85 + 0.10  # Home advantage
    away_win_prob = away_lam / (home_lam + away_lam) * 0.85 + 0.05
    draw_prob = 1 - home_win_prob - away_win_prob
    
    # Adjust for draw
    if draw_prob < 0.15:
        draw_prob = 0.15
        home_win_prob *= (1 - draw_prob) / (home_win_prob + away_win_prob)
        away_win_prob *= (1 - draw_prob) / (home_win_prob + away_win_prob)
    
    print(f"   {home_team} Win Probability: {home_win_prob:.3f}")
    print(f"   Draw Probability: {draw_prob:.3f}")
    print(f"   {away_team} Win Probability: {away_win_prob:.3f}")
    
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
    
    # 8. KEY HANDICAPPING FACTORS
    print("8. KEY HANDICAPPING FACTORS")
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
            "recommendation": goals_lean,
        },
        "btts_analysis": {
            "home_btts_strength": round(home_btts_strength, 2),
            "away_btts_strength": round(away_btts_strength, 2),
            "btts_probability": round(btts_prob, 3),
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
            "recommendation": corners_lean,
        },
        "recommendations": {
            "match_outcome": outcome_lean,
            "goals": goals_lean,
            "btts": btts_lean,
            "corners": corners_lean,
        },
        "goal_strength": {
            "home": round(home_goal_strength, 2),
            "away": round(away_goal_strength, 2),
        },
        "timestamp": datetime.now().isoformat()
    }
    
    return results


def run_philippines_vs_myanmar():
    """Run analysis for Philippines vs Myanmar"""
    
    print("\n" + "=" * 80)
    print("INTERNATIONAL MATCH: PHILIPPINES vs MYANMAR")
    print("International Friendly / AFC Qualifier - June 9, 2026")
    print("=" * 80 + "\n")
    
    # Philippines (Home) - Known for defensive organization, counter-attacking
    # Rely on physical play, set pieces, and quick transitions
    home_data = {
        'xg_for': 1.15,      # Modest attacking output
        'xg_against': 1.45,  # Vulnerable defense against better teams
        'shots': 10.0,       # Lower shot volume
        'sot': 3.2,          # Limited shots on target
        'goals_for': 1.0,    # Low scoring
        'goals_against': 1.4, # Concede regularly
        'clean_sheets': 3,   # Occasional clean sheets
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': -0.1,       # Prefer slower, defensive game
        'width_crossing': 0.45, # Limited wing play
        'final_third_pressure': 0.35, # Low pressure in final third
    }
    
    # Myanmar (Away) - Developing football nation, technical but physically outmatched
    # Try to play possession but often struggle against physical teams
    away_data = {
        'xg_for': 1.05,      # Limited attacking threat
        'xg_against': 1.65,  # Weak defense
        'shots': 9.5,        # Low shot volume
        'sot': 3.0,          # Few shots on target
        'goals_for': 0.9,    # Very low scoring
        'goals_against': 1.6, # Concede frequently
        'clean_sheets': 2,   # Rarely keep clean sheets
        'missing_attacker': 0,
        'missing_creator': 1, # Missing a creative player
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.0,        # Average tempo
        'width_crossing': 0.40, # Limited width
        'final_third_pressure': 0.30, # Low final third pressure
    }
    
    market_data = {
        'goals_line': 2.5,
        'corners_line': 8.5,
        'weather_penalty': 0,
        'referee_flow': 0,
        'must_win_home': 0,
        'must_win_away': 0,
    }
    
    result = analyze_soccer_match(
        home_team="Philippines",
        away_team="Myanmar",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Rizal Memorial Stadium, Manila",
        date="2026-06-09",
        league="International_Friendly"
    )
    
    return result


def run_china_vs_thailand():
    """Run analysis for China PR vs Thailand"""
    
    print("\n" + "=" * 80)
    print("INTERNATIONAL MATCH: CHINA PR vs THAILAND")
    print("International Friendly / AFC Qualifier - June 9, 2026")
    print("=" * 80 + "\n")
    
    # China PR (Home) - Physically strong, organized defense
    # Historically stronger than Thailand, home advantage significant
    home_data = {
        'xg_for': 1.55,      # Decent attacking output
        'xg_against': 1.10,  # Solid defense
        'shots': 13.0,       # Good shot volume
        'sot': 4.5,          # Decent shots on target
        'goals_for': 1.5,    # Moderate scoring
        'goals_against': 1.0, # Good defensive record
        'clean_sheets': 5,   # Regular clean sheets
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.2,        # Moderate tempo
        'width_crossing': 0.55, # Good use of width
        'final_third_pressure': 0.55, # Good pressure in final third
    }
    
    # Thailand (Away) - Technical, possession-based style
    # Skilled but often outmuscled by bigger teams
    away_data = {
        'xg_for': 1.35,      # Decent attacking ability
        'xg_against': 1.35,  # Average defense
        'shots': 12.0,       # Good ball possession leads to shots
        'sot': 4.0,          # Decent accuracy
        'goals_for': 1.3,    # Moderate scoring
        'goals_against': 1.3, # Average defensive record
        'clean_sheets': 3,   # Occasional clean sheets
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.3,        # Higher tempo, possession game
        'width_crossing': 0.50, # Good width play
        'final_third_pressure': 0.50, # Good final third presence
    }
    
    market_data = {
        'goals_line': 2.5,
        'corners_line': 9.5,
        'weather_penalty': 0,
        'referee_flow': 0,
        'must_win_home': 1,  # China likely needs to win at home
        'must_win_away': 0,
    }
    
    result = analyze_soccer_match(
        home_team="China PR",
        away_team="Thailand",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Workers' Stadium, Beijing",
        date="2026-06-09",
        league="International_Friendly"
    )
    
    return result


def main():
    """Run both international soccer match analyses"""
    
    print("=" * 80)
    print("INTERNATIONAL SOCCER MATCHES COMPREHENSIVE ANALYSIS")
    print("June 9, 2026")
    print("=" * 80)
    
    # Run Philippines vs Myanmar
    phil_myan_result = run_philippines_vs_myanmar()
    
    # Run China PR vs Thailand
    china_thai_result = run_china_vs_thailand()
    
    # Save results
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / "philippines_vs_myanmar_analysis.json", 'w') as f:
        json.dump(phil_myan_result, f, indent=2)
    
    with open(output_dir / "china_pr_vs_thailand_analysis.json", 'w') as f:
        json.dump(china_thai_result, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()
    print("Philippines vs Myanmar:")
    print(f"  Projected Score: Philippines {phil_myan_result['projections']['home_expected_goals']:.1f} - Myanmar {phil_myan_result['projections']['away_expected_goals']:.1f}")
    print(f"  Outcome: {phil_myan_result['recommendations']['match_outcome']}")
    print(f"  Goals: {phil_myan_result['recommendations']['goals']}")
    print(f"  BTTS: {phil_myan_result['recommendations']['btts']}")
    print(f"  Corners: {phil_myan_result['recommendations']['corners']}")
    print()
    print("China PR vs Thailand:")
    print(f"  Projected Score: China PR {china_thai_result['projections']['home_expected_goals']:.1f} - Thailand {china_thai_result['projections']['away_expected_goals']:.1f}")
    print(f"  Outcome: {china_thai_result['recommendations']['match_outcome']}")
    print(f"  Goals: {china_thai_result['recommendations']['goals']}")
    print(f"  BTTS: {china_thai_result['recommendations']['btts']}")
    print(f"  Corners: {china_thai_result['recommendations']['corners']}")
    print()
    print(f"Results saved to:")
    print(f"  - output/philippines_vs_myanmar_analysis.json")
    print(f"  - output/china_pr_vs_thailand_analysis.json")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()