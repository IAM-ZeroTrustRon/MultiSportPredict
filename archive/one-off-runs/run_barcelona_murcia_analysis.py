#!/usr/bin/env python
"""
Comprehensive Analysis for Barcelona vs UCAM Murcia
EuroLeague - June 4, 2026
Includes: Full Game, Q1, Player Props, Game & Team Totals
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
    date="2026-06-04", league="EuroLeague"
):
    """Analyze a basketball match and return results"""
    
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
    
    # 7. Q1 PROJECTION
    print("7. FIRST QUARTER PROJECTION")
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
    
    print(f"   Projected Q1 Score: {home_team} {q1_proj['home_q1_points']:.1f} - {away_team} {q1_proj['away_q1_points']:.1f}")
    print(f"   Q1 Spread: {q1_proj['q1_spread']:+.1f}")
    print(f"   Q1 Total: {q1_proj['q1_total']:.1f}")
    print(f"   Q1 Home Win Probability: {q1_proj['q1_prob_home_win']:.3f}")
    print()
    
    # 8. PROJECTED SCORES
    print("8. PROJECTED FINAL SCORE")
    print("-" * 40)
    
    projected_home = result.get('projected_home_score', 0)
    projected_away = result.get('projected_away_score', 0)
    projected_total = result.get('projected_total', 0)
    
    if projected_home == 0:
        avg_pace_factor = avg_pace / 70
        projected_home = (home_data['ortg'] / 100) * avg_pace_factor * 50 + (model_score * 2)
        projected_away = (away_data['ortg'] / 100) * avg_pace_factor * 50 - (model_score * 1)
        projected_total = projected_home + projected_away
    
    print(f"   Projected Score: {home_team} {projected_home:.1f} - {away_team} {projected_away:.1f}")
    print(f"   Projected Total: {projected_total:.1f}")
    print(f"   Projected Spread: {projected_home - projected_away:+.1f}")
    print()
    
    # 9. TEAM TOTALS
    print("9. TEAM TOTALS")
    print("-" * 40)
    
    from MultiSportModel import poisson_over_prob
    
    # Home team totals
    p_home_over_75 = poisson_over_prob(projected_home, 75)
    p_home_over_80 = poisson_over_prob(projected_home, 80)
    p_home_over_85 = poisson_over_prob(projected_home, 85)
    
    print(f"   {home_team}:")
    print(f"      Over 75 Points: {p_home_over_75:.3f} ({p_home_over_75*100:.1f}%)")
    print(f"      Over 80 Points: {p_home_over_80:.3f} ({p_home_over_80*100:.1f}%)")
    print(f"      Over 85 Points: {p_home_over_85:.3f} ({p_home_over_85*100:.1f}%)")
    print()
    
    # Away team totals
    p_away_over_75 = poisson_over_prob(projected_away, 75)
    p_away_over_80 = poisson_over_prob(projected_away, 80)
    p_away_over_85 = poisson_over_prob(projected_away, 85)
    
    print(f"   {away_team}:")
    print(f"      Over 75 Points: {p_away_over_75:.3f} ({p_away_over_75*100:.1f}%)")
    print(f"      Over 80 Points: {p_away_over_80:.3f} ({p_away_over_80*100:.1f}%)")
    print(f"      Over 85 Points: {p_away_over_85:.3f} ({p_away_over_85*100:.1f}%)")
    print()
    
    # 10. FULL GAME TOTALS
    print("10. FULL GAME TOTALS")
    print("-" * 40)
    
    p_over_155 = poisson_over_prob(projected_total, 155)
    p_over_160 = poisson_over_prob(projected_total, 160)
    p_over_165 = poisson_over_prob(projected_total, 165)
    p_over_170 = poisson_over_prob(projected_total, 170)
    p_over_175 = poisson_over_prob(projected_total, 175)
    
    print(f"   Over 155 Points: {p_over_155:.3f} ({p_over_155*100:.1f}%)")
    print(f"   Over 160 Points: {p_over_160:.3f} ({p_over_160*100:.1f}%)")
    print(f"   Over 165 Points: {p_over_165:.3f} ({p_over_165*100:.1f}%)")
    print(f"   Over 170 Points: {p_over_170:.3f} ({p_over_170*100:.1f}%)")
    print(f"   Over 175 Points: {p_over_175:.3f} ({p_over_175*100:.1f}%)")
    
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
    
    totals_lean = market_data.get('total_lean', 'Pass')
    print(f"   Market Total: {total_line}")
    print(f"   Recommendation: {totals_lean}")
    print()
    
    # 11. MARKET ANALYSIS
    print("11. MARKET LINE ANALYSIS")
    print("-" * 40)
    
    print(f"   Spread Line: {market_data['spread']} ({home_team} favored)")
    print(f"   Open Line: {market_data['open_line']}")
    print(f"   Current Line: {market_data['current_line']}")
    print(f"   Line Movement: {market_data['current_line'] - market_data['open_line']:+.1f}")
    print(f"   Total Line: {market_data.get('total', 'N/A')}")
    print()
    
    # 12. KEY HANDICAPPING FACTORS
    print("12. KEY HANDICAPPING FACTORS")
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
            "home": home_data,
            "away": away_data,
        },
        "market_data": market_data,
        "projections": {
            "home_score": round(projected_home, 1),
            "away_score": round(projected_away, 1),
            "total": round(projected_total, 1),
            "spread": round(projected_home - projected_away, 1),
            "home_win_prob": round(model_prob, 3),
            "away_win_prob": round(1 - model_prob, 3),
        },
        "q1_projections": q1_proj,
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
            "full_game_spread": lean,
            "full_game_total": totals_lean,
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


def run_barcelona_murcia_analysis():
    """Run comprehensive analysis for Barcelona vs UCAM Murcia"""
    
    print("=" * 80)
    print("COMPREHENSIVE ANALYSIS: BARCELONA vs UCAM MURCIA")
    print("EuroLeague - June 4, 2026")
    print("=" * 80)
    print()
    
    # Define team data based on EuroLeague metrics
    # Barcelona (Home)
    home_data = {
        'ortg': 118.5,        # Offensive Rating
        'drtg': 108.2,        # Defensive Rating
        'baseline_net': 10.3,  # Baseline net rating
        'recent_net': 9.5,     # Recent net rating (last 10 games)
        'pace': 76.5,          # Pace (possessions per 40 min - FIBA)
        'rest_days': 3,
        'travel_km': 0,        # Home team, no travel
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': 5.2,     # Home court advantage factor (strong at Palau)
        'rotation_depth': 10,  # Number of regular rotation players
        'injury_status': 'green',  # Healthy roster
        'coach_stability': 'green',
        'motivation': 'green',  # Playing for playoff seeding
    }
    
    # UCAM Murcia (Away)
    away_data = {
        'ortg': 108.2,        # Offensive Rating
        'drtg': 112.5,        # Defensive Rating
        'baseline_net': -4.3,  # Baseline net rating
        'recent_net': -3.8,    # Recent net rating (last 10 games)
        'pace': 73.8,          # Pace (possessions per 40 min - FIBA)
        'rest_days': 2,
        'travel_km': 450,      # Travel from Murcia to Barcelona
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': -2.8,    # Road performance factor
        'rotation_depth': 8,   # Number of regular rotation players
        'injury_status': 'yellow',  # Minor injury concerns
        'coach_stability': 'green',
        'motivation': 'yellow',  # Fighting to avoid relegation
    }
    
    # Market data
    market_data = {
        'open_line': -8.5,     # Barcelona opened as 8.5 point favorites
        'current_line': -9.5,  # Current line moved to Barcelona -9.5
        'spread': -9.5,        # Barcelona favored by 9.5
        'total': 162.5,        # Over/Under total
    }
    
    # Run analysis
    result = analyze_basketball_match(
        home_team="Barcelona",
        away_team="UCAM Murcia",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Palau Blaugrana, Barcelona",
        date="2026-06-04",
        league="EuroLeague"
    )
    
    # ==========================================
    # PLAYER PROPS ANALYSIS
    # ==========================================
    print()
    print("=" * 80)
    print("PLAYER PROPS ANALYSIS")
    print("=" * 80)
    print()
    
    avg_pace = (home_data['pace'] + away_data['pace']) / 2
    
    # Define player props data for key players (EuroLeague)
    player_props = [
        # Barcelona Players
        {
            "player_name": "Nikola Mirotic",
            "team": "Barcelona",
            "opponent": "UCAM Murcia",
            "prop_type": "Points",
            "prop_line": 16.5,
            "player_avg": 17.8,
            "minutes_proj": 28.0,
            "usage_rate": 26.0,
            "game_pace": avg_pace,
            "opp_def_rating": 112.5,
            "opp_position_def_rating": 110.0,
            "injury_boost": "green",
            "blowout_risk": "green",
            "role": "starter",
            "open_prop_line": 16.0,
            "current_prop_line": 16.5,
        },
        {
            "player_name": "Nikola Mirotic",
            "team": "Barcelona",
            "opponent": "UCAM Murcia",
            "prop_type": "Rebounds",
            "prop_line": 6.5,
            "player_avg": 7.2,
            "minutes_proj": 28.0,
            "usage_rate": 26.0,
            "game_pace": avg_pace,
            "opp_def_rating": 112.5,
            "opp_position_def_rating": 114.0,
            "injury_boost": "green",
            "blowout_risk": "green",
            "role": "starter",
            "open_prop_line": 6.5,
            "current_prop_line": 6.5,
        },
        {
            "player_name": "Tomas Satoransky",
            "team": "Barcelona",
            "opponent": "UCAM Murcia",
            "prop_type": "Points",
            "prop_line": 12.5,
            "player_avg": 13.5,
            "minutes_proj": 26.0,
            "usage_rate": 20.0,
            "game_pace": avg_pace,
            "opp_def_rating": 112.5,
            "opp_position_def_rating": 111.0,
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 12.0,
            "current_prop_line": 12.5,
        },
        {
            "player_name": "Tomas Satoransky",
            "team": "Barcelona",
            "opponent": "UCAM Murcia",
            "prop_type": "Assists",
            "prop_line": 5.5,
            "player_avg": 6.1,
            "minutes_proj": 26.0,
            "usage_rate": 20.0,
            "game_pace": avg_pace,
            "opp_def_rating": 112.5,
            "opp_position_def_rating": 110.0,
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 5.5,
            "current_prop_line": 5.5,
        },
        # UCAM Murcia Players
        {
            "player_name": "Dylan Osetkowski",
            "team": "UCAM Murcia",
            "opponent": "Barcelona",
            "prop_type": "Points",
            "prop_line": 14.5,
            "player_avg": 15.8,
            "minutes_proj": 30.0,
            "usage_rate": 24.0,
            "game_pace": avg_pace,
            "opp_def_rating": 108.2,
            "opp_position_def_rating": 107.0,  # Barcelona defends well
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 14.0,
            "current_prop_line": 14.5,
        },
        {
            "player_name": "Dylan Osetkowski",
            "team": "UCAM Murcia",
            "opponent": "Barcelona",
            "prop_type": "Rebounds",
            "prop_line": 6.5,
            "player_avg": 7.0,
            "minutes_proj": 30.0,
            "usage_rate": 24.0,
            "game_pace": avg_pace,
            "opp_def_rating": 108.2,
            "opp_position_def_rating": 106.0,  # Barcelona strong inside
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 6.5,
            "current_prop_line": 6.5,
        },
        {
            "player_name": "Tyler Kalinoski",
            "team": "UCAM Murcia",
            "opponent": "Barcelona",
            "prop_type": "Points",
            "prop_line": 11.5,
            "player_avg": 12.2,
            "minutes_proj": 25.0,
            "usage_rate": 18.0,
            "game_pace": avg_pace,
            "opp_def_rating": 108.2,
            "opp_position_def_rating": 109.0,
            "injury_boost": "yellow",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 11.0,
            "current_prop_line": 11.5,
        },
        {
            "player_name": "Tyler Kalinoski",
            "team": "UCAM Murcia",
            "opponent": "Barcelona",
            "prop_type": "3-Pointers Made",
            "prop_line": 2.5,
            "player_avg": 2.8,
            "minutes_proj": 25.0,
            "usage_rate": 18.0,
            "game_pace": avg_pace,
            "opp_def_rating": 108.2,
            "opp_position_def_rating": 107.0,
            "injury_boost": "yellow",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 2.5,
            "current_prop_line": 2.5,
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
        
        proj_value = prop['player_avg']
        
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
    output_path = Path("output/barcelona_vs_murcia_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"Detailed results saved to: {output_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    run_barcelona_murcia_analysis()