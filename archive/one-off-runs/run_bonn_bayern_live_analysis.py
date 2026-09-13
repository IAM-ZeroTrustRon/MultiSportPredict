#!/usr/bin/env python
"""
Live Game Analysis for Telekom Baskets Bonn vs Bayern Munich
BBL (Basketball Bundesliga) - Live - June 4, 2026
Current: 1Q tied 13-13
Includes: 1H, FG, Player Props, Game & Team Totals
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Import the MultiSportModel functions
from MultiSportModel import (
    run_basketball_game_automated,
    run_universal_match,
    process_basketball_game,
    process_basketball_prop,
    project_basketball_q1,
    efficiency_gap,
    historical_efficiency_gap,
    pace_edge,
    rest_travel_score,
    home_away_score,
    context_score,
    market_filter,
    score_to_prob,
)


def analyze_live_basketball_match(
    home_team, away_team, home_data, away_data, market_data, venue,
    current_score, current_quarter, date="2026-06-04", league="BBL"
):
    """Analyze a live basketball match with in-game adjustments"""
    
    print("=" * 80)
    print(f"LIVE GAME ANALYSIS: {home_team} vs {away_team}")
    print(f"{league} - {date}")
    print(f"Venue: {venue}")
    print(f"CURRENT SCORE: {home_team} {current_score['home']} - {away_team} {current_score['away']} (End of Q{current_quarter})")
    print("=" * 80)
    print()
    
    # Calculate in-game adjustments based on current performance
    q1_total = current_score['home'] + current_score['away']
    q1_pace_factor = q1_total / (home_data['pace'] + away_data['pace']) * 2  # Normalize
    
    print(f"IN-GAME ADJUSTMENTS:")
    print(f"   Q1 Total Points: {q1_total}")
    print(f"   Expected Q1 Total (based on pace): {(home_data['pace'] + away_data['pace']) / 2:.1f}")
    print(f"   Pace Factor: {q1_pace_factor:.2f} ({'Faster' if q1_pace_factor > 1 else 'Slower'} than expected)")
    print()
    
    # Adjust projections based on live data
    # If Q1 was lower scoring, adjust full game total down
    live_adjustment = (q1_pace_factor - 1) * 0.3  # 30% weight to live data
    
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
    
    eff_gap = efficiency_gap(
        home_data['ortg'], home_data['drtg'],
        away_data['ortg'], away_data['drtg']
    )
    hist_gap = historical_efficiency_gap(
        eff_gap, 
        home_data['baseline_net'] - away_data['baseline_net'],
        home_data['recent_net'] - away_data['recent_net']
    )
    
    print(f"   Efficiency Gap: {eff_gap:+.2f} (positive favors {home_team})")
    print(f"   Historical Gap: {hist_gap:+.2f}")
    print()
    
    # 2. LIVE FIRST HALF PROJECTION
    print("2. FIRST HALF PROJECTION (LIVE)")
    print("-" * 40)
    
    # Q1 actual: 13-13, project Q2 based on team strengths
    # Home team typically gets slight boost in Q2 at home
    q2_home_proj = (home_data['ortg'] / 100) * (home_data['pace'] / 2) * 0.25 + 2
    q2_away_proj = (away_data['ortg'] / 100) * (away_data['pace'] / 2) * 0.25 + 2
    
    # Apply live adjustment
    q2_home_proj *= (1 + live_adjustment * 0.5)
    q2_away_proj *= (1 + live_adjustment * 0.5)
    
    first_half_home = current_score['home'] + q2_home_proj
    first_half_away = current_score['away'] + q2_away_proj
    first_half_total = first_half_home + first_half_away
    first_half_spread = first_half_home - first_half_away
    
    # Calculate 1H win probability
    from MultiSportModel import sigmoid, clamp
    first_half_score = first_half_spread * 0.65
    first_half_prob = clamp(sigmoid(first_half_score / 3.5))
    
    print(f"   Q1 Actual: {home_team} {current_score['home']} - {away_team} {current_score['away']}")
    print(f"   Q2 Projection: {home_team} {q2_home_proj:.1f} - {away_team} {q2_away_proj:.1f}")
    print(f"   Projected 1H Score: {home_team} {first_half_home:.1f} - {away_team} {first_half_away:.1f}")
    print(f"   1H Spread: {first_half_spread:+.1f}")
    print(f"   1H Total: {first_half_total:.1f}")
    print(f"   1H Home Win Probability: {first_half_prob:.3f}")
    print()
    
    # 3. FULL GAME PROJECTION (LIVE)
    print("3. FULL GAME PROJECTION (LIVE)")
    print("-" * 40)
    
    # Run the base model
    result = run_basketball_game_automated(
        home_team=home_team,
        away_team=away_team,
        league=league,
        date=date,
        market_line=market_data['spread'],
        current_line=market_data['current_line'],
        open_line=market_data['open_line'],
        home_params=home_data,
        away_params=away_data,
    )
    
    model_score = result['model_score']
    model_prob = result['model_prob']
    
    # Adjust full game projection based on live data
    base_projected_home = result.get('projected_home_score', 0)
    base_projected_away = result.get('projected_away_score', 0)
    base_projected_total = result.get('projected_total', 0)
    
    if base_projected_home == 0:
        avg_pace = (home_data['pace'] + away_data['pace']) / 2
        avg_pace_factor = avg_pace / 70
        base_projected_home = (home_data['ortg'] / 100) * avg_pace_factor * 50 + (model_score * 2)
        base_projected_away = (away_data['ortg'] / 100) * avg_pace_factor * 50 - (model_score * 1)
        base_projected_total = base_projected_home + base_projected_away
    
    # Apply live adjustment (Q1 performance suggests different pace)
    live_projected_home = base_projected_home * (1 + live_adjustment * 0.4)
    live_projected_away = base_projected_away * (1 + live_adjustment * 0.4)
    live_projected_total = live_projected_home + live_projected_away
    
    # Calculate FG win probability with live adjustment
    live_win_prob = model_prob + (current_score['home'] - current_score['away']) * 0.005
    
    print(f"   Base Model Projection: {home_team} {base_projected_home:.1f} - {away_team} {base_projected_away:.1f}")
    print(f"   Live Adjustment: {live_adjustment:+.2f}")
    print(f"   Live Projection: {home_team} {live_projected_home:.1f} - {away_team} {live_projected_away:.1f}")
    print(f"   Live Projected Total: {live_projected_total:.1f}")
    print(f"   Live Spread: {live_projected_home - live_projected_away:+.1f}")
    print(f"   Home Win Probability (Live): {live_win_prob:.3f}")
    print()
    
    # 4. TEAM TOTALS (LIVE)
    print("4. TEAM TOTALS (LIVE)")
    print("-" * 40)
    
    from MultiSportModel import poisson_over_prob
    
    # Home team totals (using Poisson distribution)
    home_lam_live = live_projected_home
    p_home_over_75 = poisson_over_prob(home_lam_live, 75)
    p_home_over_80 = poisson_over_prob(home_lam_live, 80)
    p_home_over_85 = poisson_over_prob(home_lam_live, 85)
    
    print(f"   {home_team}:")
    print(f"      Over 75 Points: {p_home_over_75:.3f} ({p_home_over_75*100:.1f}%)")
    print(f"      Over 80 Points: {p_home_over_80:.3f} ({p_home_over_80*100:.1f}%)")
    print(f"      Over 85 Points: {p_home_over_85:.3f} ({p_home_over_85*100:.1f}%)")
    print()
    
    # Away team totals
    away_lam_live = live_projected_away
    p_away_over_75 = poisson_over_prob(away_lam_live, 75)
    p_away_over_80 = poisson_over_prob(away_lam_live, 80)
    p_away_over_85 = poisson_over_prob(away_lam_live, 85)
    
    print(f"   {away_team}:")
    print(f"      Over 75 Points: {p_away_over_75:.3f} ({p_away_over_75*100:.1f}%)")
    print(f"      Over 80 Points: {p_away_over_80:.3f} ({p_away_over_80*100:.1f}%)")
    print(f"      Over 85 Points: {p_away_over_85:.3f} ({p_away_over_85*100:.1f}%)")
    print()
    
    # 5. FULL GAME TOTALS (LIVE)
    print("5. FULL GAME TOTALS (LIVE)")
    print("-" * 40)
    
    p_over_155 = poisson_over_prob(live_projected_total, 155)
    p_over_160 = poisson_over_prob(live_projected_total, 160)
    p_over_165 = poisson_over_prob(live_projected_total, 165)
    p_over_170 = poisson_over_prob(live_projected_total, 170)
    p_over_175 = poisson_over_prob(live_projected_total, 175)
    
    print(f"   Over 155 Points: {p_over_155:.3f} ({p_over_155*100:.1f}%)")
    print(f"   Over 160 Points: {p_over_160:.3f} ({p_over_160*100:.1f}%)")
    print(f"   Over 165 Points: {p_over_165:.3f} ({p_over_165*100:.1f}%)")
    print(f"   Over 170 Points: {p_over_170:.3f} ({p_over_170*100:.1f}%)")
    print(f"   Over 175 Points: {p_over_175:.3f} ({p_over_175*100:.1f}%)")
    
    # Market recommendation
    total_line = market_data.get('total', 165)
    if total_line <= 155:
        prob_over = p_over_155
    elif total_line <= 160:
        prob_over = p_over_160
    elif total_line <= 165:
        prob_over = p_over_165
    elif total_line <= 170:
        prob_over = p_over_170
    else:
        prob_over = p_over_175
    
    from MultiSportModel import market_recommendation
    totals_lean = market_recommendation(prob_over, total_line)
    print(f"   Market Total: {total_line}")
    print(f"   Recommendation: {totals_lean}")
    print()
    
    # 6. PLAYER PROPS (LIVE ADJUSTED)
    print("6. PLAYER PROPS (LIVE ADJUSTED)")
    print("-" * 40)
    
    avg_pace = (home_data['pace'] + away_data['pace']) / 2
    
    # Define player props data for key players (BBL)
    player_props = [
        # Telekom Baskets Bonn Players
        {
            "player_name": "TJ DiLeo",
            "team": "Telekom Baskets Bonn",
            "opponent": "Bayern Munich",
            "prop_type": "Points",
            "prop_line": 14.5,
            "player_avg": 15.2,
            "minutes_proj": 28.0,
            "usage_rate": 24.0,
            "game_pace": avg_pace,
            "opp_def_rating": 108.5,
            "opp_position_def_rating": 107.0,
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 14.0,
            "current_prop_line": 14.5,
        },
        {
            "player_name": "TJ DiLeo",
            "team": "Telekom Baskets Bonn",
            "opponent": "Bayern Munich",
            "prop_type": "Assists",
            "prop_line": 4.5,
            "player_avg": 5.1,
            "minutes_proj": 28.0,
            "usage_rate": 24.0,
            "game_pace": avg_pace,
            "opp_def_rating": 108.5,
            "opp_position_def_rating": 107.0,
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 4.5,
            "current_prop_line": 4.5,
        },
        {
            "player_name": "Louis Olinde",
            "team": "Telekom Baskets Bonn",
            "opponent": "Bayern Munich",
            "prop_type": "Points",
            "prop_line": 12.5,
            "player_avg": 13.5,
            "minutes_proj": 25.0,
            "usage_rate": 20.0,
            "game_pace": avg_pace,
            "opp_def_rating": 108.5,
            "opp_position_def_rating": 110.0,
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 12.0,
            "current_prop_line": 12.5,
        },
        # Bayern Munich Players
        {
            "player_name": "Carsen Edwards",
            "team": "Bayern Munich",
            "opponent": "Telekom Baskets Bonn",
            "prop_type": "Points",
            "prop_line": 18.5,
            "player_avg": 19.8,
            "minutes_proj": 30.0,
            "usage_rate": 28.0,
            "game_pace": avg_pace,
            "opp_def_rating": 110.2,
            "opp_position_def_rating": 109.0,
            "injury_boost": "green",
            "blowout_risk": "green",
            "role": "starter",
            "open_prop_line": 18.0,
            "current_prop_line": 18.5,
        },
        {
            "player_name": "Carsen Edwards",
            "team": "Bayern Munich",
            "opponent": "Telekom Baskets Bonn",
            "prop_type": "3-Pointers Made",
            "prop_line": 3.5,
            "player_avg": 3.9,
            "minutes_proj": 30.0,
            "usage_rate": 28.0,
            "game_pace": avg_pace,
            "opp_def_rating": 110.2,
            "opp_position_def_rating": 111.0,
            "injury_boost": "green",
            "blowout_risk": "green",
            "role": "starter",
            "open_prop_line": 3.5,
            "current_prop_line": 3.5,
        },
        {
            "player_name": "Vladimir Lucic",
            "team": "Bayern Munich",
            "opponent": "Telekom Baskets Bonn",
            "prop_type": "Points",
            "prop_line": 13.5,
            "player_avg": 14.2,
            "minutes_proj": 26.0,
            "usage_rate": 22.0,
            "game_pace": avg_pace,
            "opp_def_rating": 110.2,
            "opp_position_def_rating": 108.0,
            "injury_boost": "green",
            "blowout_risk": "green",
            "role": "starter",
            "open_prop_line": 13.0,
            "current_prop_line": 13.5,
        },
        {
            "player_name": "Niels Giffey",
            "team": "Bayern Munich",
            "opponent": "Telekom Baskets Bonn",
            "prop_type": "Rebounds",
            "prop_line": 4.5,
            "player_avg": 5.0,
            "minutes_proj": 24.0,
            "usage_rate": 16.0,
            "game_pace": avg_pace,
            "opp_def_rating": 110.2,
            "opp_position_def_rating": 108.0,
            "injury_boost": "green",
            "blowout_risk": "green",
            "role": "starter",
            "open_prop_line": 4.5,
            "current_prop_line": 4.5,
        },
    ]
    
    props_results = []
    print(f"{'Player':<25} {'Prop':<15} {'Line':>6} {'Proj':>6} {'Edge':>6} {'Lean':<25}")
    print("-" * 85)
    
    for prop in player_props:
        # Run prop through the model
        prop_result = process_basketball_prop(prop)
        
        edge = prop_result.get('model_score', 0)
        prob = prop_result.get('model_prob', 0.5)
        lean = prop_result.get('lean', 'Pass')
        projection = prop_result.get('details', '')
        
        # Adjust for live game (Q1 performance)
        # If Q1 was high scoring, adjust player props up slightly
        live_edge = edge * (1 + live_adjustment * 0.3)
        
        proj_value = prop['player_avg']
        
        props_results.append({
            "player_name": prop['player_name'],
            "team": prop['team'],
            "prop_type": prop['prop_type'],
            "prop_line": prop['prop_line'],
            "model_projection": round(proj_value, 1),
            "edge": round(edge, 2),
            "live_edge": round(live_edge, 2),
            "model_prob": round(prob, 3),
            "lean": lean,
            "details": projection,
        })
        
        print(f"{prop['player_name']:<25} {prop['prop_type']:<15} {prop['prop_line']:>6.1f} {proj_value:>6.1f} {edge:>+6.2f} {lean:<25}")
    
    print()
    
    # Summary of best props
    strong_leans = [p for p in props_results if 'Lean' in p['lean']]
    if strong_leans:
        print("TOP PLAYER PROP RECOMMENDATIONS:")
        print("-" * 50)
        for p in sorted(strong_leans, key=lambda x: abs(x['edge']), reverse=True)[:5]:
            print(f"  {p['lean']} | {p['player_name']} {p['prop_type']} (Line: {p['prop_line']}, Edge: {p['edge']:+.2f})")
        print()
    
    # FINAL SUMMARY
    print("=" * 80)
    print("LIVE GAME FINAL SUMMARY")
    print("=" * 80)
    print()
    print(f"   CURRENT SCORE: {home_team} {current_score['home']} - {away_team} {current_score['away']} (End Q1)")
    print()
    print("   FIRST HALF PROJECTION:")
    print(f"      Projected 1H Score: {home_team} {first_half_home:.1f} - {away_team} {first_half_away:.1f}")
    print(f"      1H Spread: {first_half_spread:+.1f} | 1H Total: {first_half_total:.1f}")
    print()
    print("   FULL GAME PROJECTION:")
    print(f"      Projected FG Score: {home_team} {live_projected_home:.1f} - {away_team} {live_projected_away:.1f}")
    print(f"      FG Spread: {live_projected_home - live_projected_away:+.1f} | FG Total: {live_projected_total:.1f}")
    print(f"      Home Win Probability: {live_win_prob:.1%}")
    print()
    print("   RECOMMENDATIONS:")
    print(f"      Full Game Total: {totals_lean}")
    if strong_leans:
        print(f"      Top Player Prop: {strong_leans[0]['lean']}")
    print()
    
    # Determine confidence
    max_prob = max(prob_over, abs(live_win_prob - 0.5) + 0.5)
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
            "venue": venue,
            "live_status": True,
            "current_quarter": current_quarter,
            "current_score": current_score,
        },
        "team_metrics": {
            "home": home_data,
            "away": away_data,
        },
        "market_data": market_data,
        "live_adjustments": {
            "q1_pace_factor": round(q1_pace_factor, 2),
            "live_adjustment": round(live_adjustment, 3),
        },
        "projections": {
            "first_half": {
                "home_score": round(first_half_home, 1),
                "away_score": round(first_half_away, 1),
                "total": round(first_half_total, 1),
                "spread": round(first_half_spread, 1),
                "home_win_prob": round(first_half_prob, 3),
            },
            "full_game": {
                "home_score": round(live_projected_home, 1),
                "away_score": round(live_projected_away, 1),
                "total": round(live_projected_total, 1),
                "spread": round(live_projected_home - live_projected_away, 1),
                "home_win_prob": round(live_win_prob, 3),
            }
        },
        "team_totals": {
            "home": {
                "over_75": round(p_home_over_75, 4),
                "over_80": round(p_home_over_80, 4),
                "over_85": round(p_home_over_85, 4),
            },
            "away": {
                "over_75": round(p_away_over_75, 4),
                "over_80": round(p_away_over_80, 4),
                "over_85": round(p_away_over_85, 4),
            }
        },
        "full_game_totals": {
            "over_155": round(p_over_155, 4),
            "over_160": round(p_over_160, 4),
            "over_165": round(p_over_165, 4),
            "over_170": round(p_over_170, 4),
            "over_175": round(p_over_175, 4),
        },
        "recommendations": {
            "full_game_total": totals_lean,
        },
        "player_props": props_results,
        "confidence": confidence,
        "timestamp": datetime.now().isoformat()
    }
    
    return results


def run_bonn_bayern_live_analysis():
    """Run live analysis for Bonn vs Bayern"""
    
    print("=" * 80)
    print("LIVE GAME ANALYSIS: TELEKOM BASKETS BONN vs BAYERN MUNICH")
    print("BBL (Basketball Bundesliga) - June 4, 2026")
    print("=" * 80)
    print()
    
    # Define team data based on BBL metrics
    # Telekom Baskets Bonn (Home)
    home_data = {
        'ortg': 110.5,        # Offensive Rating
        'drtg': 108.2,        # Defensive Rating
        'baseline_net': 2.3,   # Baseline net rating
        'recent_net': 3.1,     # Recent net rating (last 10 games)
        'pace': 72.5,          # Pace (possessions per 40 min - FIBA)
        'rest_days': 2,
        'travel_km': 0,        # Home team, no travel
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': 3.8,     # Home court advantage factor
        'rotation_depth': 9,   # Number of regular rotation players
        'injury_status': 'green',  # Healthy roster
        'coach_stability': 'green',
        'motivation': 'green',  # Playing for playoff positioning
    }
    
    # Bayern Munich (Away)
    away_data = {
        'ortg': 115.2,        # Offensive Rating
        'drtg': 106.8,        # Defensive Rating
        'baseline_net': 8.4,   # Baseline net rating
        'recent_net': 7.5,     # Recent net rating (last 10 games)
        'pace': 71.8,          # Pace (possessions per 40 min - FIBA)
        'rest_days': 3,
        'travel_km': 350,      # Travel from Munich to Bonn
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': -2.2,    # Road performance factor
        'rotation_depth': 10,  # Number of regular rotation players
        'injury_status': 'green',  # Healthy roster
        'coach_stability': 'green',
        'motivation': 'green',  # Playing for championship
    }
    
    # Current game state
    current_score = {'home': 13, 'away': 13}
    current_quarter = 1
    
    # Market data
    market_data = {
        'open_line': -4.5,     # Bayern opened as 4.5 point favorites
        'current_line': -3.5,  # Current line moved to Bayern -3.5
        'spread': -3.5,        # Bayern favored by 3.5
        'total': 162.5,        # Over/Under total
    }
    
    # Run analysis
    result = analyze_live_basketball_match(
        home_team="Telekom Baskets Bonn",
        away_team="Bayern Munich",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Telekom Dome, Bonn",
        current_score=current_score,
        current_quarter=current_quarter,
        date="2026-06-04",
        league="BBL"
    )
    
    # Save results
    output_path = Path("output/bonn_vs_bayern_live_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"Detailed results saved to: {output_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    run_bonn_bayern_live_analysis()