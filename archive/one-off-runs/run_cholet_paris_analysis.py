#!/usr/bin/env python
"""
Comprehensive Analysis for Basketball Match
- Cholet vs Paris
French LNB Pro A - June 7, 2026
Focus: Spread, Total, Moneyline, and Q1 Projections
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Import the MultiSportModel functions
from MultiSportModel import (
    GameContext,
    TeamMetrics,
    eu_build_full_game,
    project_basketball_q1,
)
from core import (
    confidence_score,
    bet_recommendation,
    store_prediction,
)


def analyze_basketball_match(
    home_team, away_team, home_data, away_data, market_data, venue,
    date="2026-06-07", league="France_LNB_Pro_A"
):
    """Analyze a basketball match with comprehensive betting analysis"""
    
    print("=" * 80)
    print(f"COMPREHENSIVE MATCH ANALYSIS: {home_team} vs {away_team}")
    print(f"{league} - {date}")
    print(f"Venue: {venue}")
    print("=" * 80)
    print()
    
    # 1. TEAM EFFICIENCY ANALYSIS
    print("1. TEAM EFFICIENCY ANALYSIS")
    print("-" * 40)
    
    home_net = home_data['ortg'] - home_data['drtg']
    away_net = away_data['ortg'] - away_data['drtg']
    
    print(f"   {home_team}:")
    print(f"      ORTG: {home_data['ortg']:.1f} | DRTG: {home_data['drtg']:.1f} | Net: {home_net:+.1f}")
    print(f"      Baseline Net: {home_data['baseline_net']:+.1f} | Recent Net: {home_data['recent_net']:+.1f}")
    print()
    print(f"   {away_team}:")
    print(f"      ORTG: {away_data['ortg']:.1f} | DRTG: {away_data['drtg']:.1f} | Net: {away_net:+.1f}")
    print(f"      Baseline Net: {away_data['baseline_net']:+.1f} | Recent Net: {away_data['recent_net']:+.1f}")
    print()
    
    # 2. PACE ANALYSIS
    print("2. PACE ANALYSIS")
    print("-" * 40)
    
    avg_pace = (home_data['pace'] + away_data['pace']) / 2
    print(f"   {home_team} Pace: {home_data['pace']:.1f}")
    print(f"   {away_team} Pace: {away_data['pace']:.1f}")
    print(f"   Average Pace: {avg_pace:.1f}")
    print()
    
    # 3. REST & TRAVEL ANALYSIS
    print("3. REST & TRAVEL ANALYSIS")
    print("-" * 40)
    
    print(f"   {home_team}: {home_data['rest_days']} rest days, {home_data['travel_km']} km travel")
    print(f"      Back-to-back: {home_data['back_to_back']}")
    print(f"   {away_team}: {away_data['rest_days']} rest days, {away_data['travel_km']} km travel")
    print(f"      Back-to-back: {away_data['back_to_back']}")
    print()
    
    # 4. BUILD MODEL PREDICTIONS
    print("4. MODEL PROJECTIONS")
    print("-" * 40)
    
    ctx = GameContext(
        game_id=f"{home_team.replace(' ', '_')}_vs_{away_team.replace(' ', '_')}",
        date=date,
        league=league,
        record_type="full_game",
        home_team=home_team,
        away_team=away_team,
        market_line=market_data['spread'],
        current_line=market_data['current_line'],
        open_line=market_data['open_line'],
    )
    
    home_tm = TeamMetrics(
        ortg=home_data['ortg'],
        drtg=home_data['drtg'],
        baseline_net=home_data['baseline_net'],
        recent_net=home_data['recent_net'],
        pace=home_data['pace'],
        rest_days=home_data['rest_days'],
        travel_km=home_data['travel_km'],
        back_to_back=home_data['back_to_back'],
        three_in_six=home_data['three_in_six'],
        split_edge=home_data['split_edge'],
        rotation_depth=home_data['rotation_depth'],
        injury_status=home_data['injury_status'],
        coach_stability=home_data['coach_stability'],
        motivation=home_data['motivation'],
        open_line=market_data['open_line'],
        current_line=market_data['current_line'],
    )
    
    away_tm = TeamMetrics(
        ortg=away_data['ortg'],
        drtg=away_data['drtg'],
        baseline_net=away_data['baseline_net'],
        recent_net=away_data['recent_net'],
        pace=away_data['pace'],
        rest_days=away_data['rest_days'],
        travel_km=away_data['travel_km'],
        back_to_back=away_data['back_to_back'],
        three_in_six=away_data['three_in_six'],
        split_edge=away_data['split_edge'],
        rotation_depth=away_data['rotation_depth'],
        injury_status=away_data['injury_status'],
        coach_stability=away_data['coach_stability'],
        motivation=away_data['motivation'],
        open_line=-market_data['open_line'],
        current_line=-market_data['current_line'],
    )
    
    result = eu_build_full_game(home_tm, away_tm, ctx)
    q1_proj = project_basketball_q1(home_data, away_data)
    
    projected_home = result['projected_home_score']
    projected_away = result['projected_away_score']
    projected_total = result['projected_total']
    projected_spread = projected_home - projected_away
    
    print(f"   Projected Score: {home_team} {projected_home:.1f} - {away_team} {projected_away:.1f}")
    print(f"   Projected Total: {projected_total:.1f}")
    print(f"   Projected Spread: {projected_spread:+.1f}")
    print(f"   Win Probability: {home_team} {result['probability']:.1%}")
    print(f"   Model Edge: {result['model_edge']:+.2f}")
    print(f"   Lean: {result['lean']}")
    print()
    
    # 5. Q1 PROJECTION
    print("5. FIRST QUARTER PROJECTION")
    print("-" * 40)
    
    q1_spread = q1_proj['q1_spread']
    q1_total = q1_proj['q1_total']
    q1_home = q1_proj['home_q1_points']
    q1_away = q1_proj['away_q1_points']
    
    print(f"   Q1 Projected: {home_team} {q1_home:.1f} - {away_team} {q1_away:.1f}")
    print(f"   Q1 Spread: {q1_spread:+.1f}")
    print(f"   Q1 Total: {q1_total:.1f}")
    print()
    
    # 6. CONFIDENCE SCORING
    print("6. CONFIDENCE SCORING")
    print("-" * 40)
    
    spread_edge = projected_spread - market_data['spread']
    total_edge = projected_total - market_data['total']
    
    spread_confidence = confidence_score(spread_edge, volatility=0.35, market_alignment=0.0)
    total_confidence = confidence_score(total_edge, volatility=0.38, market_alignment=0.0)
    
    spread_rec = bet_recommendation(spread_confidence)
    total_rec = bet_recommendation(total_confidence)
    
    print(f"   Spread ({market_data['spread']}): Edge {spread_edge:+.2f}, Confidence {spread_confidence:.1f}%, Rec: {spread_rec}")
    print(f"   Total ({market_data['total']}): Edge {total_edge:+.2f}, Confidence {total_confidence:.1f}%, Rec: {total_rec}")
    print()
    
    # 7. KEY HANDICAPPING FACTORS
    print("7. KEY HANDICAPPING FACTORS")
    print("-" * 40)
    print()
    
    print(f"   FACTORS FAVORING {home_team.upper()}:")
    if home_net > away_net:
        print(f"   [+] Better net rating ({home_net:+.1f} vs {away_net:+.1f})")
    if home_data['ortg'] > away_data['ortg']:
        print(f"   [+] Better offense (ORTG: {home_data['ortg']:.1f} vs {away_data['ortg']:.1f})")
    if home_data['drtg'] < away_data['drtg']:
        print(f"   [+] Better defense (DRTG: {home_data['drtg']:.1f} vs {away_data['drtg']:.1f})")
    if home_data['rest_days'] > away_data['rest_days']:
        print(f"   [+] More rest ({home_data['rest_days']} vs {away_data['rest_days']} days)")
    if home_data['split_edge'] > away_data['split_edge']:
        print(f"   [+] Better home/away split ({home_data['split_edge']:+.1f} vs {away_data['split_edge']:+.1f})")
    print()
    
    print(f"   FACTORS FAVORING {away_team.upper()}:")
    if away_net > home_net:
        print(f"   [+] Better net rating ({away_net:+.1f} vs {home_net:+.1f})")
    if away_data['ortg'] > home_data['ortg']:
        print(f"   [+] Better offense (ORTG: {away_data['ortg']:.1f} vs {home_data['ortg']:.1f})")
    if away_data['drtg'] < home_data['drtg']:
        print(f"   [+] Better defense (DRTG: {away_data['drtg']:.1f} vs {home_data['drtg']:.1f})")
    if away_data['rest_days'] > home_data['rest_days']:
        print(f"   [+] More rest ({away_data['rest_days']} vs {home_data['rest_days']} days)")
    print()
    
    # FINAL SUMMARY
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Match: {home_team} vs {away_team}")
    print(f"   Projected Score: {home_team} {projected_home:.1f} - {away_team} {projected_away:.1f}")
    print(f"   Projected Total: {projected_total:.1f}")
    print(f"   Projected Spread: {projected_spread:+.1f}")
    print()
    print("   === BETTING RECOMMENDATIONS ===")
    print(f"   Spread ({market_data['spread']}): {spread_rec} (Confidence: {spread_confidence:.1f}%)")
    print(f"   Total ({market_data['total']}): {total_rec} (Confidence: {total_confidence:.1f}%)")
    print(f"   Moneyline: {result['lean']} (Win Prob: {result['probability']:.1%})")
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
            "home_score": round(projected_home, 1),
            "away_score": round(projected_away, 1),
            "total": round(projected_total, 1),
            "spread": round(projected_spread, 1),
            "win_probability": round(result['probability'], 3),
            "model_edge": round(result['model_edge'], 2),
        },
        "q1_projections": q1_proj,
        "recommendations": {
            "spread": {
                "recommendation": spread_rec,
                "confidence": round(spread_confidence, 1),
                "edge": round(spread_edge, 2),
            },
            "total": {
                "recommendation": total_rec,
                "confidence": round(total_confidence, 1),
                "edge": round(total_edge, 2),
            },
            "moneyline": {
                "lean": result['lean'],
                "win_probability": round(result['probability'], 3),
            }
        },
        "timestamp": datetime.now().isoformat()
    }
    
    return results


def run_cholet_paris_analysis():
    """Run analysis for Cholet vs Paris"""
    
    print("\n" + "=" * 80)
    print("FRENCH LNB PRO A: CHOLET vs PARIS")
    print("June 7, 2026")
    print("=" * 80 + "\n")
    
    # Cholet (Home)
    home_data = {
        'ortg': 107.0,
        'drtg': 109.0,
        'baseline_net': -2.0,
        'recent_net': -1.0,
        'pace': 68.0,
        'rest_days': 2,
        'travel_km': 0,
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': 2.0,
        'rotation_depth': 8,
        'injury_status': 'green',
        'coach_stability': 'green',
        'motivation': 'green',
    }
    
    # Paris (Away)
    away_data = {
        'ortg': 111.0,
        'drtg': 106.0,
        'baseline_net': 5.0,
        'recent_net': 4.5,
        'pace': 71.0,
        'rest_days': 2,
        'travel_km': 300,
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': 3.0,
        'rotation_depth': 9,
        'injury_status': 'green',
        'coach_stability': 'green',
        'motivation': 'green',
    }
    
    market_data = {
        'open_line': 2.5,
        'current_line': 3.0,
        'spread': 3.0,
        'total': 160.5,
    }
    
    result = analyze_basketball_match(
        home_team="Cholet",
        away_team="Paris",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="La Meilleraie, Cholet",
        date="2026-06-07",
        league="France_LNB_Pro_A"
    )
    
    return result


if __name__ == "__main__":
    result = run_cholet_paris_analysis()
    
    # Save results
    output_dir = Path("output/basketball")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / "cholet_vs_paris_analysis.json", 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_dir / 'cholet_vs_paris_analysis.json'}")