#!/usr/bin/env python
"""
Comprehensive Analysis for NBL Game
- Hawke's Bay Hawks vs Nelson Giants
NBL (New Zealand) - June 3, 2026
Includes: Full Game, Q1, and Player Props Analysis
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


def analyze_basketball_match(
    home_team, away_team, home_data, away_data, market_data, venue, 
    date="2026-06-03", league="NZNBL"
):
    """Analyze a single basketball match and return results"""
    
    print("=" * 80)
    print(f"COMPREHENSIVE MATCH ANALYSIS: {home_team} vs {away_team}")
    print(f"{league} - {date}")
    print(f"Venue: {venue}")
    print("=" * 80)
    print()
    
    # 1. TEAM OFFENSIVE/DEFENSIVE EFFICIENCY ANALYSIS
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
    
    # Calculate efficiency gap
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
    
    # 2. PACE ANALYSIS
    print("2. PACE ANALYSIS")
    print("-" * 40)
    
    pace_gap = pace_edge(home_data['pace'], away_data['pace'])
    avg_pace = (home_data['pace'] + away_data['pace']) / 2
    
    print(f"   {home_team} Pace: {home_data['pace']:.1f}")
    print(f"   {away_team} Pace: {away_data['pace']:.1f}")
    print(f"   Average Pace: {avg_pace:.1f}")
    print(f"   Pace Edge: {pace_gap:+.2f} (positive favors {home_team})")
    print()
    
    # 3. REST & TRAVEL ANALYSIS
    print("3. REST & TRAVEL ANALYSIS")
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
    
    print(f"   {home_team}: {home_data['rest_days']} rest days, {home_data['travel_km']} km travel")
    print(f"      Back-to-back: {home_data['back_to_back']} | Rest Score: {home_rest_score:+.1f}")
    print(f"   {away_team}: {away_data['rest_days']} rest days, {away_data['travel_km']} km travel")
    print(f"      Back-to-back: {away_data['back_to_back']} | Rest Score: {away_rest_score:+.1f}")
    print(f"   Rest Gap: {rest_gap:+.2f} (positive favors {home_team})")
    print()
    
    # 4. HOME/AWAY SPLIT ANALYSIS
    print("4. HOME/AWAY SPLIT ANALYSIS")
    print("-" * 40)
    
    split_gap = home_away_score(home_data['split_edge'], away_data['split_edge'])
    
    print(f"   {home_team} Home/Away Split Edge: {home_data['split_edge']:+.1f}")
    print(f"   {away_team} Home/Away Split Edge: {away_data['split_edge']:+.1f}")
    print(f"   Split Gap: {split_gap:+.2f} (positive favors {home_team})")
    print()
    
    # 5. CONTEXTUAL FACTORS
    print("5. CONTEXTUAL FACTORS")
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
    
    print(f"   {home_team}:")
    print(f"      Rotation Depth: {home_data['rotation_depth']} | Injury Status: {home_data['injury_status']}")
    print(f"      Coach Stability: {home_data['coach_stability']} | Motivation: {home_data['motivation']}")
    print(f"      Context Score: {home_ctx:+.1f}")
    print()
    print(f"   {away_team}:")
    print(f"      Rotation Depth: {away_data['rotation_depth']} | Injury Status: {away_data['injury_status']}")
    print(f"      Coach Stability: {away_data['coach_stability']} | Motivation: {away_data['motivation']}")
    print(f"      Context Score: {away_ctx:+.1f}")
    print()
    print(f"   Context Gap: {ctx_gap:+.2f} (positive favors {home_team})")
    print()
    
    # 6. RUN THE MODEL
    print("6. MODEL PROJECTION")
    print("-" * 40)
    
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
    lean = result['lean']
    
    print(f"   Model Score: {model_score:+.2f}")
    print(f"   Home Win Probability: {model_prob:.3f}")
    print(f"   Recommendation: {lean}")
    print()
    
    # 7. Q1 AND FIRST HALF PROJECTION
    print("7. FIRST QUARTER & FIRST HALF PROJECTION")
    print("-" * 40)
    
    q1_proj = project_basketball_q1(
        {
            "ortg": home_data['ortg'],
            "drtg": home_data['drtg'],
            "pace": home_data['pace'],
            "rotation_depth": home_data['rotation_depth'],
            "injury_status": home_data['injury_status'],
            "coach_stability": home_data['coach_stability'],
            "motivation": home_data['motivation'],
        },
        {
            "ortg": away_data['ortg'],
            "drtg": away_data['drtg'],
            "pace": away_data['pace'],
            "rotation_depth": away_data['rotation_depth'],
            "injury_status": away_data['injury_status'],
            "coach_stability": away_data['coach_stability'],
            "motivation": away_data['motivation'],
        }
    )
    
    # Calculate First Half projections (approximately 2x Q1 with adjustments)
    q1_home = q1_proj['home_q1_points']
    q1_away = q1_proj['away_q1_points']
    
    # First half typically sees slight efficiency adjustments
    # Teams adjust at halftime, so Q2 is often slightly different
    q2_home = q1_home * 1.02  # Slight adjustment for Q2
    q2_away = q1_away * 0.98
    
    q1_total = q1_home + q1_away
    first_half_home = q1_home + q2_home
    first_half_away = q1_away + q2_away
    first_half_total = first_half_home + first_half_away
    first_half_spread = first_half_home - first_half_away
    
    # Calculate first half probability using similar methodology as Q1
    from MultiSportModel import sigmoid, clamp
    first_half_score = first_half_spread * 0.65
    first_half_prob = clamp(sigmoid(first_half_score / 3.5))
    
    print(f"   FIRST QUARTER:")
    print(f"      Projected Q1 Score: {home_team} {q1_home:.1f} - {away_team} {q1_away:.1f}")
    print(f"      Q1 Spread: {q1_proj['q1_spread']:+.1f}")
    print(f"      Q1 Total: {q1_total:.1f}")
    print(f"      Q1 Home Win Probability: {q1_proj['q1_prob_home_win']:.3f}")
    print()
    print(f"   FIRST HALF:")
    print(f"      Projected 1H Score: {home_team} {first_half_home:.1f} - {away_team} {first_half_away:.1f}")
    print(f"      1H Spread: {first_half_spread:+.1f}")
    print(f"      1H Total: {first_half_total:.1f}")
    print(f"      1H Home Win Probability: {first_half_prob:.3f}")
    print()
    
    # 8. PROJECTED SCORES
    print("8. PROJECTED FINAL SCORE")
    print("-" * 40)
    
    # Use the European template projections if available
    projected_home = result.get('projected_home_score', 0)
    projected_away = result.get('projected_away_score', 0)
    projected_total = result.get('projected_total', 0)
    
    # Calculate based on model if not available
    if projected_home == 0:
        avg_pace_factor = avg_pace / 70
        projected_home = (home_data['ortg'] / 100) * avg_pace_factor * 50 + (model_score * 2)
        projected_away = (away_data['ortg'] / 100) * avg_pace_factor * 50 - (model_score * 1)
        projected_total = projected_home + projected_away
    
    print(f"   Projected Score: {home_team} {projected_home:.1f} - {away_team} {projected_away:.1f}")
    print(f"   Projected Total: {projected_total:.1f}")
    print(f"   Projected Spread: {projected_home - projected_away:+.1f}")
    print()
    
    # 9. MARKET ANALYSIS
    print("9. MARKET LINE ANALYSIS")
    print("-" * 40)
    
    print(f"   Spread Line: {market_data['spread']} ({home_team} favored)")
    print(f"   Open Line: {market_data['open_line']}")
    print(f"   Current Line: {market_data['current_line']}")
    print(f"   Line Movement: {market_data['current_line'] - market_data['open_line']:+.1f}")
    print(f"   Total Line: {market_data['total']}")
    print()
    
    # 10. KEY HANDICAPPING FACTORS
    print("10. KEY HANDICAPPING FACTORS")
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
    if home_ctx > away_ctx:
        print(f"   [+] Better contextual factors (rotation, injuries, coaching)")
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
    if away_data['split_edge'] > home_data['split_edge']:
        print(f"   [+] Better home/away split ({away_data['split_edge']:+.1f} vs {home_data['split_edge']:+.1f})")
    if away_ctx > home_ctx:
        print(f"   [+] Better contextual factors (rotation, injuries, coaching)")
    print()
    
    # Determine confidence
    if abs(model_score) >= 4.0:
        confidence = "HIGH"
    elif abs(model_score) >= 2.0:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    
    # FINAL SUMMARY
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Projected Score: {home_team} {projected_home:.1f} - {away_team} {projected_away:.1f}")
    print(f"   Projected Total: {projected_total:.1f}")
    print(f"   Spread: {projected_home - projected_away:+.1f}")
    print(f"   Model Score: {model_score:+.2f}")
    print(f"   Home Win Probability: {model_prob:.1%}")
    print()
    print(f"   RECOMMENDATION: {lean}")
    print(f"   Q1 Spread: {q1_proj['q1_spread']:+.1f}")
    print()
    print(f"   CONFIDENCE LEVEL: {confidence}")
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
            "home": {
                "ortg": home_data['ortg'],
                "drtg": home_data['drtg'],
                "baseline_net": home_data['baseline_net'],
                "recent_net": home_data['recent_net'],
                "pace": home_data['pace'],
                "rest_days": home_data['rest_days'],
                "travel_km": home_data['travel_km'],
                "back_to_back": home_data['back_to_back'],
                "three_in_six": home_data['three_in_six'],
                "split_edge": home_data['split_edge'],
                "rotation_depth": home_data['rotation_depth'],
                "injury_status": home_data['injury_status'],
                "coach_stability": home_data['coach_stability'],
                "motivation": home_data['motivation'],
            },
            "away": {
                "ortg": away_data['ortg'],
                "drtg": away_data['drtg'],
                "baseline_net": away_data['baseline_net'],
                "recent_net": away_data['recent_net'],
                "pace": away_data['pace'],
                "rest_days": away_data['rest_days'],
                "travel_km": away_data['travel_km'],
                "back_to_back": away_data['back_to_back'],
                "three_in_six": away_data['three_in_six'],
                "split_edge": away_data['split_edge'],
                "rotation_depth": away_data['rotation_depth'],
                "injury_status": away_data['injury_status'],
                "coach_stability": away_data['coach_stability'],
                "motivation": away_data['motivation'],
            }
        },
        "market_data": {
            "open_line": market_data['open_line'],
            "current_line": market_data['current_line'],
            "spread": market_data['spread'],
            "total": market_data['total'],
        },
        "projections": {
            "home_score": round(projected_home, 1),
            "away_score": round(projected_away, 1),
            "total": round(projected_total, 1),
            "spread": round(projected_home - projected_away, 1),
            "home_win_prob": round(model_prob, 3),
            "away_win_prob": round(1 - model_prob, 3),
        },
        "q1_projections": q1_proj,
        "recommendations": {
            "full_game_spread": lean,
            "full_game_total": f"Over {market_data['total']}" if projected_total > market_data['total'] else f"Under {market_data['total']}",
            "q1_spread": f"{'Home' if q1_proj['q1_spread'] > 0 else 'Away'} Q1 {abs(q1_proj['q1_spread']):.1f}",
        },
        "model_details": {
            "efficiency_gap": round(eff_gap, 2),
            "historical_gap": round(hist_gap, 2),
            "pace_gap": round(pace_gap, 2),
            "rest_gap": round(rest_gap, 2),
            "split_gap": round(split_gap, 2),
            "context_gap": round(ctx_gap, 2),
            "model_score": round(model_score, 4),
            "model_prob": round(model_prob, 4),
        },
        "confidence": confidence,
        "timestamp": datetime.now().isoformat()
    }
    
    return results


def run_hawks_giants_analysis():
    """Run comprehensive analysis for Hawks vs Giants"""
    
    print("=" * 80)
    print("COMPREHENSIVE ANALYSIS: HAWKE'S BAY HAWKS vs NELSON GIANTS")
    print("NZNBL - June 3, 2026")
    print("=" * 80)
    print()
    
    # Define team data based on NZNBL metrics
    # Hawke's Bay Hawks (Home)
    home_data = {
        'ortg': 108.5,        # Offensive Rating
        'drtg': 106.2,        # Defensive Rating
        'baseline_net': 2.3,   # Baseline net rating
        'recent_net': 3.5,     # Recent net rating (last 10 games)
        'pace': 72.5,          # Pace (possessions per 40 min - FIBA)
        'rest_days': 3,
        'travel_km': 0,        # Home team, no travel
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': 4.2,     # Home court advantage factor
        'rotation_depth': 9,   # Number of regular rotation players
        'injury_status': 'green',  # Healthy roster
        'coach_stability': 'green',
        'motivation': 'green',  # Playing for playoff positioning
    }
    
    # Nelson Giants (Away)
    away_data = {
        'ortg': 105.8,        # Offensive Rating
        'drtg': 108.5,        # Defensive Rating
        'baseline_net': -2.7,  # Baseline net rating
        'recent_net': -1.8,    # Recent net rating (last 10 games)
        'pace': 70.8,          # Pace (possessions per 40 min - FIBA)
        'rest_days': 2,
        'travel_km': 280,      # Travel from Nelson to Napier
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': -2.5,    # Road performance factor
        'rotation_depth': 8,   # Number of regular rotation players
        'injury_status': 'yellow',  # Minor injury concerns
        'coach_stability': 'green',
        'motivation': 'yellow',  # Fighting for playoff spot
    }
    
    # Market data
    market_data = {
        'open_line': -5.5,     # Hawks opened as 5.5 point favorites
        'current_line': -6.5,  # Current line moved to Hawks -6.5
        'spread': -6.5,        # Hawks favored by 6.5
        'total': 162.5,        # Over/Under total
    }
    
    # Run analysis
    result = analyze_basketball_match(
        home_team="Hawke's Bay Hawks",
        away_team="Nelson Giants",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Pettigrew Green Arena, Napier",
        date="2026-06-03",
        league="NZNBL"
    )
    
    # ==========================================
    # PLAYER PROPS ANALYSIS
    # ==========================================
    print()
    print("=" * 80)
    print("PLAYER PROPS ANALYSIS")
    print("=" * 80)
    print()
    
    # Calculate average pace for props
    avg_pace = (home_data['pace'] + away_data['pace']) / 2
    
    # Define player props data for key players (NZNBL)
    player_props = [
        # Hawke's Bay Hawks Players
        {
            "player_name": "Tom Vodanovich",
            "team": "Hawke's Bay Hawks",
            "opponent": "Nelson Giants",
            "prop_type": "Points",
            "prop_line": 18.5,
            "player_avg": 19.2,
            "minutes_proj": 30.0,
            "usage_rate": 26.0,
            "game_pace": avg_pace,
            "opp_def_rating": 108.5,
            "opp_position_def_rating": 107.0,
            "injury_boost": "green",
            "blowout_risk": "green",
            "role": "starter",
            "open_prop_line": 18.0,
            "current_prop_line": 18.5,
        },
        {
            "player_name": "Tom Vodanovich",
            "team": "Hawke's Bay Hawks",
            "opponent": "Nelson Giants",
            "prop_type": "Rebounds",
            "prop_line": 7.5,
            "player_avg": 8.1,
            "minutes_proj": 30.0,
            "usage_rate": 26.0,
            "game_pace": avg_pace,
            "opp_def_rating": 108.5,
            "opp_position_def_rating": 110.0,
            "injury_boost": "green",
            "blowout_risk": "green",
            "role": "starter",
            "open_prop_line": 7.5,
            "current_prop_line": 7.5,
        },
        {
            "player_name": "Quintin Berry",
            "team": "Hawke's Bay Hawks",
            "opponent": "Nelson Giants",
            "prop_type": "Points",
            "prop_line": 16.5,
            "player_avg": 17.5,
            "minutes_proj": 28.0,
            "usage_rate": 24.0,
            "game_pace": avg_pace,
            "opp_def_rating": 108.5,
            "opp_position_def_rating": 109.0,
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 16.0,
            "current_prop_line": 16.5,
        },
        {
            "player_name": "Quintin Berry",
            "team": "Hawke's Bay Hawks",
            "opponent": "Nelson Giants",
            "prop_type": "Assists",
            "prop_line": 5.5,
            "player_avg": 6.2,
            "minutes_proj": 28.0,
            "usage_rate": 24.0,
            "game_pace": avg_pace,
            "opp_def_rating": 108.5,
            "opp_position_def_rating": 107.0,
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 5.5,
            "current_prop_line": 5.5,
        },
        # Nelson Giants Players
        {
            "player_name": "Dominic Kelman",
            "team": "Nelson Giants",
            "opponent": "Hawke's Bay Hawks",
            "prop_type": "Points",
            "prop_line": 20.5,
            "player_avg": 21.8,
            "minutes_proj": 34.0,
            "usage_rate": 30.0,
            "game_pace": avg_pace,
            "opp_def_rating": 106.2,
            "opp_position_def_rating": 105.0,  # Hawks defend guards well
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 20.0,
            "current_prop_line": 20.5,
        },
        {
            "player_name": "Dominic Kelman",
            "team": "Nelson Giants",
            "opponent": "Hawke's Bay Hawks",
            "prop_type": "Assists",
            "prop_line": 4.5,
            "player_avg": 5.1,
            "minutes_proj": 34.0,
            "usage_rate": 30.0,
            "game_pace": avg_pace,
            "opp_def_rating": 106.2,
            "opp_position_def_rating": 105.0,
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 4.5,
            "current_prop_line": 4.5,
        },
        {
            "player_name": "Michael Ane",
            "team": "Nelson Giants",
            "opponent": "Hawke's Bay Hawks",
            "prop_type": "Points",
            "prop_line": 14.5,
            "player_avg": 15.2,
            "minutes_proj": 26.0,
            "usage_rate": 22.0,
            "game_pace": avg_pace,
            "opp_def_rating": 106.2,
            "opp_position_def_rating": 108.0,
            "injury_boost": "yellow",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 14.0,
            "current_prop_line": 14.5,
        },
        {
            "player_name": "Michael Ane",
            "team": "Nelson Giants",
            "opponent": "Hawke's Bay Hawks",
            "prop_type": "Rebounds",
            "prop_line": 6.5,
            "player_avg": 7.0,
            "minutes_proj": 26.0,
            "usage_rate": 22.0,
            "game_pace": avg_pace,
            "opp_def_rating": 106.2,
            "opp_position_def_rating": 104.0,  # Hawks strong inside
            "injury_boost": "yellow",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 6.5,
            "current_prop_line": 6.5,
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
        
        # Extract model projection from details
        proj_value = prop['player_avg']  # Use average as base projection
        
        props_results.append({
            "player_name": prop['player_name'],
            "team": prop['team'],
            "prop_type": prop['prop_type'],
            "prop_line": prop['prop_line'],
            "model_projection": round(proj_value, 1),
            "edge": round(edge, 2),
            "model_prob": round(prob, 3),
            "lean": lean,
            "details": projection,
        })
        
        print(f"{prop['player_name']:<25} {prop['prop_type']:<15} {prop['prop_line']:>6.1f} {proj_value:>6.1f} {edge:>+6.2f} {lean:<25}")
    
    print()
    print("=" * 80)
    
    # Add props to results
    result['player_props'] = props_results
    
    # Summary of best props
    strong_leans = [p for p in props_results if 'Lean' in p['lean']]
    if strong_leans:
        print()
        print("TOP PLAYER PROP RECOMMENDATIONS:")
        print("-" * 50)
        for p in sorted(strong_leans, key=lambda x: abs(x['edge']), reverse=True)[:5]:
            print(f"  {p['lean']} | {p['player_name']} {p['prop_type']} (Line: {p['prop_line']}, Edge: {p['edge']:+.2f})")
        print()
    
    # Save results
    output_path = Path("output/hawks_vs_giants_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"Detailed results saved to: {output_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    run_hawks_giants_analysis()