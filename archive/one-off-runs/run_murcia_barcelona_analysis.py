#!/usr/bin/env python
"""
Comprehensive Analysis for UCAM Murcia vs FC Barcelona
EuroLeague Game - June 2, 2026
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Import the MultiSportModel functions
from MultiSportModel import (
    run_universal_match,
    process_basketball_game,
    project_basketball_q1,
    efficiency_gap,
    historical_efficiency_gap,
    pace_edge,
    rest_travel_score,
    home_away_score,
    context_score,
    market_filter,
    score_to_prob,
    eu_build_full_game,
    eu_build_q1,
    TeamMetrics,
    GameContext,
    Q1Metrics,
)

def run_comprehensive_analysis():
    """Run comprehensive analysis for Murcia vs Barcelona"""
    
    print("=" * 80)
    print("COMPREHENSIVE GAME ANALYSIS: UCAM MURCIA vs FC BARCELONA")
    print("EuroLeague - June 2, 2026")
    print("=" * 80)
    print()
    
    # ========================================================================
    # TEAM DATA (Estimated based on typical EuroLeague performance)
    # ========================================================================
    
    # Home Team: UCAM Murcia
    home_data = {
        'ortg': 108.5,      # Offensive Rating (points per 100 possessions)
        'drtg': 112.3,      # Defensive Rating
        'baseline_net': -3.8,  # Season-long net rating
        'recent_net': -2.5,    # Last 10 games net rating
        'pace': 73.2,          # Possessions per 40 min
        'rest_days': 2,
        'travel_km': 0,        # Home game
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': 2.1,     # Home court advantage
        'rotation_depth': 8,   # Number of rotation players
        'injury_status': 'yellow',  # Some minor injuries
        'coach_stability': 'green',
        'motivation': 'green',      # Fighting for playoff position
    }
    
    # Away Team: FC Barcelona
    away_data = {
        'ortg': 118.2,      # Elite offensive rating
        'drtg': 105.8,      # Elite defensive rating
        'baseline_net': 12.4,  # One of the best in EuroLeague
        'recent_net': 10.8,    # Strong recent form
        'pace': 76.8,          # Slightly faster pace
        'rest_days': 3,
        'travel_km': 850,     # Travel from Barcelona to Murcia
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': -1.2,   # Slight away disadvantage
        'rotation_depth': 10,  # Deep roster
        'injury_status': 'yellow',  # Some minor injuries
        'coach_stability': 'green',
        'motivation': 'green',      # Fighting for top seed
    }
    
    # Market Data
    market_data = {
        'open_line': 5.5,     # Barcelona -5.5 opened
        'current_line': 6.5,  # Moved to Barcelona -6.5
        'total': 158.5,       # Game total
    }
    
    # Q1 Data
    q1_data = {
        'home_pts_for': 19.5,
        'home_pts_against': 21.2,
        'away_pts_for': 21.2,
        'away_pts_against': 19.5,
        'pace': 72,
        'home_starting_five_net': 3.5,
        'away_starting_five_net': 8.2,
    }
    
    # ========================================================================
    # DETAILED HANDICAPPING ANALYSIS
    # ========================================================================
    
    print("1. TEAM EFFICIENCY ANALYSIS")
    print("-" * 40)
    
    # Calculate efficiency gaps
    home_net = home_data['ortg'] - home_data['drtg']  # -3.8
    away_net = away_data['ortg'] - away_data['drtg']  # 12.4
    current_gap = home_net - away_net  # -16.2
    
    print(f"   UCAM Murcia Net Rating: {home_net:.1f}")
    print(f"   FC Barcelona Net Rating: {away_net:.1f}")
    print(f"   Efficiency Gap: {current_gap:.1f} (favor Barcelona)")
    print()
    
    # Historical efficiency gap
    baseline_gap = home_data['baseline_net'] - away_data['baseline_net']  # -16.2
    recent_gap = home_data['recent_net'] - away_data['recent_net']  # -13.3
    hist_gap = (current_gap - baseline_gap) * 0.6 + (recent_gap - baseline_gap) * 0.4
    
    print(f"   Baseline Gap: {baseline_gap:.1f}")
    print(f"   Recent Gap: {recent_gap:.1f}")
    print(f"   Historical Gap (blended): {hist_gap:.1f}")
    print()
    
    print("2. PACE ANALYSIS")
    print("-" * 40)
    pace_gap = pace_edge(home_data['pace'], away_data['pace'])
    avg_pace = (home_data['pace'] + away_data['pace']) / 2
    print(f"   Murcia Pace: {home_data['pace']}")
    print(f"   Barcelona Pace: {away_data['pace']}")
    print(f"   Pace Gap: {pace_gap:.1f} (positive = home faster)")
    print(f"   Average Pace: {avg_pace:.1f}")
    print()
    
    print("3. REST & TRAVEL FATIGUE")
    print("-" * 40)
    home_rest_score = rest_travel_score(
        home_data['rest_days'], home_data['travel_km'],
        home_data['back_to_back'], home_data['three_in_six']
    )
    away_rest_score = rest_travel_score(
        away_data['rest_days'], away_data['travel_km'],
        away_data['back_to_back'], away_data['three_in_six']
    )
    rest_gap = home_rest_score - away_rest_score
    
    print(f"   Murcia Rest Score: {home_rest_score} (2 days rest, no travel)")
    print(f"   Barcelona Rest Score: {away_rest_score} (3 days rest, 850km travel)")
    print(f"   Rest Gap: {rest_gap:.1f} (positive = home advantage)")
    print()
    
    print("4. HOME/AWAY SPLITS")
    print("-" * 40)
    split_gap = home_away_score(home_data['split_edge'], away_data['split_edge'])
    print(f"   Murcia Home Split Edge: {home_data['split_edge']}")
    print(f"   Barcelona Away Split Edge: {away_data['split_edge']}")
    print(f"   Split Gap: {split_gap:.1f}")
    print()
    
    print("5. CONTEXT FACTORS")
    print("-" * 40)
    home_ctx = context_score(
        home_data['rotation_depth'], home_data['injury_status'],
        home_data['coach_stability'], home_data['motivation']
    )
    away_ctx = context_score(
        away_data['rotation_depth'], away_data['injury_status'],
        away_data['coach_stability'], away_data['motivation']
    )
    ctx_gap = home_ctx - away_ctx
    
    print(f"   Murcia Context Score: {home_ctx} (Rotation: {home_data['rotation_depth']}, Injuries: {home_data['injury_status']})")
    print(f"   Barcelona Context Score: {away_ctx} (Rotation: {away_data['rotation_depth']}, Injuries: {away_data['injury_status']})")
    print(f"   Context Gap: {ctx_gap:.1f}")
    print()
    
    print("6. MARKET LINE ANALYSIS")
    print("-" * 40)
    line_movement = market_data['current_line'] - market_data['open_line']
    print(f"   Opening Line: Barcelona -{market_data['open_line']}")
    print(f"   Current Line: Barcelona -{market_data['current_line']}")
    print(f"   Line Movement: {line_movement:+.1f} (positive = moved toward Barcelona)")
    print()
    
    # ========================================================================
    # MODEL CALCULATIONS
    # ========================================================================
    
    print("7. MODEL EDGE CALCULATION")
    print("-" * 40)
    
    # Weight the factors
    model_edge = (
        hist_gap * 0.8 +      # Efficiency is most important
        rest_gap * 0.9 +      # Rest/travel very important
        split_gap * 0.6 +     # Home/away splits
        ctx_gap * 0.8 +       # Context factors
        pace_gap * 0.15       # Pace is minor factor
    )
    
    # Market filter
    market_score, market_text = market_filter(
        market_data['open_line'], market_data['current_line'], model_edge
    )
    
    total_score = model_edge + market_score * 0.9
    prob_home = score_to_prob(total_score)
    
    print(f"   Historical Gap Contribution: {hist_gap * 0.8:.2f}")
    print(f"   Rest Gap Contribution: {rest_gap * 0.9:.2f}")
    print(f"   Split Gap Contribution: {split_gap * 0.6:.2f}")
    print(f"   Context Gap Contribution: {ctx_gap * 0.8:.2f}")
    print(f"   Pace Gap Contribution: {pace_gap * 0.15:.2f}")
    print(f"   Raw Model Edge: {model_edge:.2f}")
    print(f"   Market Score: {market_score}")
    print(f"   Total Score: {total_score:.2f}")
    print(f"   Home Win Probability: {prob_home:.3f}")
    print()
    
    # ========================================================================
    # FULL GAME PROJECTIONS
    # ========================================================================
    
    print("8. FULL GAME PROJECTIONS")
    print("-" * 40)
    
    # Project scores
    projected_home_score = 80 + total_score * 2.0
    projected_away_score = 78 - total_score * 1.0
    projected_total = projected_home_score + projected_away_score
    
    # Adjust based on pace
    pace_adjustment = (avg_pace - 70) / 70 * 0.05
    projected_home_score *= (1 + pace_adjustment)
    projected_away_score *= (1 + pace_adjustment)
    projected_total = projected_home_score + projected_away_score
    
    print(f"   Projected Murcia Score: {projected_home_score:.1f}")
    print(f"   Projected Barcelona Score: {projected_away_score:.1f}")
    print(f"   Projected Total: {projected_total:.1f}")
    print()
    
    # Spread analysis
    model_spread = projected_home_score - projected_away_score
    current_spread = -market_data['current_line']  # Negative because Barcelona is favored
    
    print(f"   Model Spread: Murcia {model_spread:+.1f}")
    print(f"   Current Spread: Murcia {current_spread:+.1f}")
    print(f"   Edge vs Spread: {(model_spread - current_spread):.1f}")
    print()
    
    # ========================================================================
    # FIRST QUARTER PROJECTIONS
    # ========================================================================
    
    print("9. FIRST QUARTER PROJECTIONS")
    print("-" * 40)
    
    q1_proj = project_basketball_q1(home_data, away_data)
    
    print(f"   Projected Q1 Murcia: {q1_proj['home_q1_points']:.1f}")
    print(f"   Projected Q1 Barcelona: {q1_proj['away_q1_points']:.1f}")
    print(f"   Q1 Spread: Murcia {q1_proj['q1_spread']:+.1f}")
    print(f"   Q1 Total: {q1_proj['q1_total']:.1f}")
    print(f"   Q1 Home Win Prob: {q1_proj['q1_prob_home_win']:.3f}")
    print()
    
    # ========================================================================
    # BETTING RECOMMENDATIONS
    # ========================================================================
    
    print("10. BETTING RECOMMENDATIONS")
    print("-" * 40)
    
    # Full Game Spread
    spread_edge = model_spread - current_spread
    if abs(spread_edge) >= 2.0:
        if spread_edge > 0:
            spread_lean = f"LEAN MURCIA +{market_data['current_line']}"
        else:
            spread_lean = f"LEAN BARCELONA -{market_data['current_line']}"
    else:
        spread_lean = "PASS"
    
    # Full Game Total
    total_edge = projected_total - market_data['total']
    if abs(total_edge) >= 3.0:
        if total_edge > 0:
            total_lean = f"LEAN OVER {market_data['total']}"
        else:
            total_lean = f"LEAN UNDER {market_data['total']}"
    else:
        total_lean = "PASS"
    
    # Moneyline
    if prob_home >= 0.60:
        ml_lean = "LEAN MURCIA ML"
    elif prob_home <= 0.40:
        ml_lean = "LEAN BARCELONA ML"
    else:
        ml_lean = "PASS"
    
    # Q1 Spread
    q1_market_line = -market_data['current_line'] * 0.4  # Approximate Q1 line
    q1_edge = q1_proj['q1_spread'] - q1_market_line
    if abs(q1_edge) >= 1.5:
        if q1_edge > 0:
            q1_lean = f"LEAN MURCIA Q1 {q1_market_line:+.1f}"
        else:
            q1_lean = f"LEAN BARCELONA Q1 {q1_market_line:+.1f}"
    else:
        q1_lean = "PASS"
    
    # Q1 Total
    q1_total_market = market_data['total'] * 0.25  # Approximate Q1 total
    q1_total_edge = q1_proj['q1_total'] - q1_total_market
    if abs(q1_total_edge) >= 1.5:
        if q1_total_edge > 0:
            q1_total_lean = f"LEAN OVER Q1 {q1_total_market:.1f}"
        else:
            q1_total_lean = f"LEAN UNDER Q1 {q1_total_market:.1f}"
    else:
        q1_total_lean = "PASS"
    
    print(f"   Full Game Spread: {spread_lean}")
    print(f"   Full Game Total: {total_lean}")
    print(f"   Full Game Moneyline: {ml_lean}")
    print(f"   Q1 Spread: {q1_lean}")
    print(f"   Q1 Total: {q1_total_lean}")
    print()
    
    # ========================================================================
    # PLAYER PROPS TO CONSIDER
    # ========================================================================
    
    print("11. PLAYER PROPS WORTH NOTING")
    print("-" * 40)
    print("   Based on pace and matchup analysis:")
    print()
    print("   Barcelona Players:")
    print("   - Nikola Mirotic: Consider OVER on points (Murcia allows 112.3 ORTG)")
    print("   - Tomas Satoransky: Consider OVER on assists (fast pace game)")
    print("   - Jan Vesely: Consider OVER on rebounds (Murcia weak inside)")
    print()
    print("   Murcia Players:")
    print("   - Tyler Kalinoski: Consider OVER on 3PM (high pace, trailing often)")
    print("   - Augustas Marciulionis: Consider OVER on points (increased usage)")
    print()
    
    # ========================================================================
    # KEY FACTORS SUMMARY
    # ========================================================================
    
    print("12. KEY HANDICAPPING FACTORS SUMMARY")
    print("-" * 40)
    print()
    print("   FACTORS FAVORING BARCELONA:")
    print("   [+] Superior efficiency (NET +12.4 vs -3.8)")
    print("   [+] Deeper roster (10 rotation players vs 8)")
    print("   [+] Better recent form")
    print("   [+] More rest (3 days vs 2 days)")
    print("   [+] Line movement supporting (opened -5.5, now -6.5)")
    print()
    print("   FACTORS FAVORING MURCIA:")
    print("   [+] Home court advantage")
    print("   [+] Barcelona travel fatigue (850km)")
    print("   [+] Potential letdown spot for Barcelona")
    print("   [+] Nothing to lose mentality")
    print()
    print("   NEUTRAL/CONCERNS:")
    print("   - Both teams dealing with minor injuries")
    print("   - Pace should be above average (favoring OVER)")
    print("   - Barcelona may rest starters if big lead")
    print()
    
    # ========================================================================
    # FINAL RECOMMENDATION
    # ========================================================================
    
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Model Win Probability: Barcelona {1-prob_home:.1%} vs Murcia {prob_home:.1%}")
    print(f"   Projected Score: Murcia {projected_home_score:.0f} - Barcelona {projected_away_score:.0f}")
    print(f"   Projected Total: {projected_total:.0f}")
    print()
    print("   PRIMARY RECOMMENDATIONS:")
    print(f"   1. {spread_lean}")
    print(f"   2. {total_lean}")
    print(f"   3. {ml_lean}")
    print()
    print("   CONFIDENCE LEVEL: " + ("HIGH" if abs(spread_edge) >= 3 else "MEDIUM" if abs(spread_edge) >= 2 else "LOW"))
    print()
    
    # ========================================================================
    # SAVE RESULTS TO JSON
    # ========================================================================
    
    results = {
        "game_info": {
            "home_team": "UCAM Murcia",
            "away_team": "FC Barcelona",
            "league": "EuroLeague",
            "date": "2026-06-02",
            "venue": "Palacio de Deportes de Murcia"
        },
        "team_metrics": {
            "home": home_data,
            "away": away_data
        },
        "market_data": market_data,
        "projections": {
            "home_score": round(projected_home_score, 1),
            "away_score": round(projected_away_score, 1),
            "total": round(projected_total, 1),
            "spread": round(model_spread, 1),
            "home_win_prob": round(prob_home, 3),
            "away_win_prob": round(1 - prob_home, 3)
        },
        "q1_projections": q1_proj,
        "recommendations": {
            "full_game_spread": spread_lean,
            "full_game_total": total_lean,
            "full_game_moneyline": ml_lean,
            "q1_spread": q1_lean,
            "q1_total": q1_total_lean
        },
        "model_details": {
            "efficiency_gap": round(current_gap, 2),
            "historical_gap": round(hist_gap, 2),
            "rest_gap": round(rest_gap, 2),
            "split_gap": round(split_gap, 2),
            "context_gap": round(ctx_gap, 2),
            "pace_gap": round(pace_gap, 2),
            "model_edge": round(model_edge, 2),
            "market_score": market_score,
            "total_score": round(total_score, 2)
        },
        "timestamp": datetime.now().isoformat()
    }
    
    # Save to output
    output_path = Path("output/murcia_vs_barcelona_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"   Detailed results saved to: {output_path}")
    print()
    print("=" * 80)

if __name__ == "__main__":
    run_comprehensive_analysis()