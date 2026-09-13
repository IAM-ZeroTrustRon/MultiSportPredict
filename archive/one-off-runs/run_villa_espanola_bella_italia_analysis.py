#!/usr/bin/env python
"""
Comprehensive Analysis for Soccer Match
- Villa Espanola vs Sportivo Bella Italia

Focus: Match Outcome, Goals O/U, BTTS, Corners, and Expected Goals
"""

import sys
import json
from datetime import datetime
from pathlib import Path
import math

def poisson_probability(lam, k):
    """Calculate Poisson probability for k events with lambda lam"""
    return (math.exp(-lam) * lam**k) / math.factorial(k)

def analyze_soccer_match(home_team, away_team, home_data, away_data, market_data, venue, date="2026-06-06", league="Uruguay Segunda Division"):
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
    
    home_xg_for = home_data['goals_scored'] / home_data['matches_played']
    home_xg_against = home_data['goals_conceded'] / home_data['matches_played']
    away_xg_for = away_data['goals_scored'] / away_data['matches_played']
    away_xg_against = away_data['goals_conceded'] / away_data['matches_played']
    
    print(f"   {home_team}:")
    print(f"      Goals For/Match: {home_xg_for:.2f}")
    print(f"      Goals Against/Match: {home_xg_against:.2f}")
    print(f"      Home Form: {home_data['home_wins']}-{home_data['home_draws']}-{home_data['home_losses']}")
    print()
    print(f"   {away_team}:")
    print(f"      Goals For/Match: {away_xg_for:.2f}")
    print(f"      Goals Against/Match: {away_xg_against:.2f}")
    print(f"      Away Form: {away_data['away_wins']}-{away_data['away_draws']}-{away_data['away_losses']}")
    print()
    
    # 2. EXPECTED GOALS CALCULATION
    print("2. EXPECTED GOALS CALCULATION")
    print("-" * 40)
    
    league_avg_goals = 2.35  # Uruguay Segunda Division average
    
    home_expected = (home_xg_for / league_avg_goals) * (away_xg_against / league_avg_goals) * league_avg_goals
    away_expected = (away_xg_for / league_avg_goals) * (home_xg_against / league_avg_goals) * league_avg_goals
    
    # Apply home advantage
    home_expected *= 1.15
    away_expected *= 0.95
    
    home_expected = round(home_expected, 2)
    away_expected = round(away_expected, 2)
    
    print(f"   {home_team} Expected Goals: {home_expected:.2f}")
    print(f"   {away_team} Expected Goals: {away_expected:.2f}")
    print(f"   Total Expected Goals: {home_expected + away_expected:.2f}")
    print()
    
    # 3. MATCH OUTCOME PROBABILITIES (Poisson Distribution)
    print("3. MATCH OUTCOME PROBABILITIES")
    print("-" * 40)
    
    home_win_prob = 0
    draw_prob = 0
    away_win_prob = 0
    
    for h in range(6):
        for a in range(6):
            prob = poisson_probability(home_expected, h) * poisson_probability(away_expected, a)
            if h > a:
                home_win_prob += prob
            elif h == a:
                draw_prob += prob
            else:
                away_win_prob += prob
    
    # Normalize
    total = home_win_prob + draw_prob + away_win_prob
    home_win_prob /= total
    draw_prob /= total
    away_win_prob /= total
    
    print(f"   {home_team} Win: {home_win_prob:.3f} ({home_win_prob*100:.1f}%)")
    print(f"   Draw: {draw_prob:.3f} ({draw_prob*100:.1f}%)")
    print(f"   {away_team} Win: {away_win_prob:.3f} ({away_win_prob*100:.1f}%)")
    print()
    
    # 4. GOALS O/U ANALYSIS
    print("4. GOALS OVER/UNDER ANALYSIS")
    print("-" * 40)
    
    total_expected = home_expected + away_expected
    
    # Calculate probabilities for different goal totals
    over_25_prob = 0
    under_25_prob = 0
    
    for h in range(6):
        for a in range(6):
            prob = poisson_probability(home_expected, h) * poisson_probability(away_expected, a)
            total_goals = h + a
            if total_goals > 2.5:
                over_25_prob += prob
            else:
                under_25_prob += prob
    
    over_25_prob /= (over_25_prob + under_25_prob)
    under_25_prob /= (over_25_prob + under_25_prob)
    
    print(f"   Total Expected Goals: {total_expected:.2f}")
    print(f"   Over 2.5 Goals: {over_25_prob:.3f} ({over_25_prob*100:.1f}%)")
    print(f"   Under 2.5 Goals: {under_25_prob:.3f} ({under_25_prob*100:.1f}%)")
    
    if over_25_prob > 0.55:
        goals_lean = f"Over 2.5"
    elif under_25_prob > 0.55:
        goals_lean = f"Under 2.5"
    else:
        goals_lean = "Pass"
    
    print(f"   Goals O/U Recommendation: {goals_lean}")
    print()
    
    # 5. BTTS ANALYSIS
    print("5. BOTH TEAMS TO SCORE (BTTS) ANALYSIS")
    print("-" * 40)
    
    home_score_prob = 1 - poisson_probability(home_expected, 0)
    away_score_prob = 1 - poisson_probability(away_expected, 0)
    
    btts_yes_prob = home_score_prob * away_score_prob
    btts_no_prob = 1 - btts_yes_prob
    
    print(f"   {home_team} to Score: {home_score_prob:.3f} ({home_score_prob*100:.1f}%)")
    print(f"   {away_team} to Score: {away_score_prob:.3f} ({away_score_prob*100:.1f}%)")
    print(f"   BTTS Yes: {btts_yes_prob:.3f} ({btts_yes_prob*100:.1f}%)")
    print(f"   BTTS No: {btts_no_prob:.3f} ({btts_no_prob*100:.1f}%)")
    
    if btts_yes_prob > 0.55:
        btts_lean = "BTTS Yes"
    elif btts_no_prob > 0.55:
        btts_lean = "BTTS No"
    else:
        btts_lean = "Pass"
    
    print(f"   BTTS Recommendation: {btts_lean}")
    print()
    
    # 6. CORNERS ANALYSIS
    print("6. CORNERS ANALYSIS")
    print("-" * 40)
    
    avg_corners_per_match = 9.0
    
    home_corners_expected = home_data.get('avg_corners_for', 4.8)
    away_corners_expected = away_data.get('avg_corners_for', 4.2)
    
    total_corners_expected = home_corners_expected + away_corners_expected
    
    if total_corners_expected > avg_corners_per_match + 1:
        corners_lean = f"Over {avg_corners_per_match:.1f}"
    elif total_corners_expected < avg_corners_per_match - 1:
        corners_lean = f"Under {avg_corners_per_match:.1f}"
    else:
        corners_lean = "Pass"
    
    print(f"   Expected Total Corners: {total_corners_expected:.1f}")
    print(f"   Corners Recommendation: {corners_lean}")
    print()
    
    # 7. MATCH OUTCOME RECOMMENDATION
    print("7. MATCH OUTCOME RECOMMENDATION")
    print("-" * 40)
    
    if home_win_prob > 0.50:
        outcome_lean = f"Home Win ({home_team})"
    elif away_win_prob > 0.45:
        outcome_lean = f"Away Win ({away_team})"
    elif draw_prob > 0.30:
        outcome_lean = "Draw"
    else:
        outcome_lean = "Pass"
    
    print(f"   Primary Recommendation: {outcome_lean}")
    print()
    
    # FINAL SUMMARY
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Match: {home_team} vs {away_team}")
    print(f"   Projected Score: {home_team} {home_expected:.0f} - {away_team} {away_expected:.0f}")
    print(f"   Total Expected Goals: {total_expected:.2f}")
    print()
    print("   === BETTING RECOMMENDATIONS ===")
    print(f"   Match Outcome: {outcome_lean}")
    print(f"   Goals O/U 2.5: {goals_lean}")
    print(f"   BTTS: {btts_lean}")
    print(f"   Corners: {corners_lean}")
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
        "team_data": {
            "home": home_data,
            "away": away_data
        },
        "expected_goals": {
            "home": home_expected,
            "away": away_expected,
            "total": round(total_expected, 2)
        },
        "probabilities": {
            "home_win": round(home_win_prob, 3),
            "draw": round(draw_prob, 3),
            "away_win": round(away_win_prob, 3),
            "over_25": round(over_25_prob, 3),
            "under_25": round(under_25_prob, 3),
            "btts_yes": round(btts_yes_prob, 3),
            "btts_no": round(btts_no_prob, 3)
        },
        "recommendations": {
            "match_outcome": outcome_lean,
            "goals_ou": goals_lean,
            "btts": btts_lean,
            "corners": corners_lean
        },
        "projected_score": f"{home_expected:.0f}-{away_expected:.0f}",
        "timestamp": datetime.now().isoformat()
    }
    
    return results


def run_villa_espanola_bella_italia_analysis():
    """Run comprehensive analysis for Villa Espanola vs Sportivo Bella Italia"""
    
    print("\n" + "=" * 80)
    print("URUGUAY SEGUNDA DIVISION: VILLA ESPANOLA vs SPORTIVO BELLA ITALIA")
    print("Uruguay Segunda Division - June 6, 2026")
    print("=" * 80 + "\n")
    
    # Villa Espanola (Home)
    home_data = {
        'matches_played': 14,
        'goals_scored': 18,
        'goals_conceded': 16,
        'home_wins': 5,
        'home_draws': 2,
        'home_losses': 0,
        'avg_corners_for': 5.0,
        'form': 'W-D-W-W-D',
    }
    
    # Sportivo Bella Italia (Away)
    away_data = {
        'matches_played': 14,
        'goals_scored': 12,
        'goals_conceded': 20,
        'away_wins': 2,
        'away_draws': 3,
        'away_losses': 2,
        'avg_corners_for': 3.8,
        'form': 'L-D-L-W-L',
    }
    
    market_data = {
        'home_ml': 2.00,
        'draw': 3.10,
        'away_ml': 3.80,
        'over_25': 2.05,
        'under_25': 1.75,
        'btts_yes': 1.95,
        'btts_no': 1.85,
        'corners_line': 8.5,
    }
    
    result = analyze_soccer_match(
        home_team="Villa Espanola",
        away_team="Sportivo Bella Italia",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Estadio Jose Pedro Damiani, Montevideo",
        date="2026-06-06",
        league="Uruguay Segunda Division"
    )
    
    return result


def main():
    """Run Villa Espanola vs Sportivo Bella Italia analysis"""
    
    print("=" * 80)
    print("URUGUAY SEGUNDA DIVISION COMPREHENSIVE ANALYSIS")
    print("June 6, 2026")
    print("=" * 80)
    
    result = run_villa_espanola_bella_italia_analysis()
    
    # Save results
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / "villa_espanola_vs_bella_italia_analysis.json", 'w') as f:
        json.dump(result, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()
    print("Villa Espanola vs Sportivo Bella Italia:")
    print(f"  Match Outcome: {result['recommendations']['match_outcome']}")
    print(f"  Goals O/U: {result['recommendations']['goals_ou']}")
    print(f"  BTTS: {result['recommendations']['btts']}")
    print(f"  Corners: {result['recommendations']['corners']}")
    print()
    print(f"Results saved to: output/villa_espanola_vs_bella_italia_analysis.json")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()