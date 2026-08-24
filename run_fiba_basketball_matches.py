#!/usr/bin/env python
"""
FIBA Basketball Match Analysis
==============================
Runs predictions for:
1. Uruguay vs Argentina
2. Panama vs Cuba

Uses the MultiSportModel's European basketball template for FIBA international matches.
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
    poisson_over_prob,
    GameContext,
    TeamMetrics,
    eu_build_full_game,
    eu_build_q1,
    eu_build_prop,
    eu_efficiency_gap,
    eu_historical_gap,
    eu_rest_travel_score,
    eu_team_context_score,
    eu_home_away_split,
    eu_market_filter,
    eu_score_to_prob,
    eu_recommendation,
)


def analyze_fiba_match(
    home_team, away_team, home_data, away_data, market_data, venue,
    date="2026-07-02", league="FIBA"
):
    """Analyze a FIBA basketball match and return results"""
    
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
    
    # 6. RUN THE MODEL (European template)
    print("6. MODEL PROJECTION (European Template)")
    print("-" * 40)
    
    # Build GameContext
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
    
    # Build TeamMetrics
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
    
    # Get base predictions from sophisticated model
    result = eu_build_full_game(home_tm, away_tm, ctx)
    
    model_score = result['model_edge']
    model_prob = result['probability']
    lean = result['lean']
    projected_home = result['projected_home_score']
    projected_away = result['projected_away_score']
    projected_total = result['projected_total']
    
    print(f"   Model Score: {model_score:+.2f}")
    print(f"   Home Win Probability: {model_prob:.3f}")
    print(f"   Recommendation: {lean}")
    print(f"   Projected Score: {home_team} {projected_home:.1f} - {away_team} {projected_away:.1f}")
    print(f"   Projected Total: {projected_total:.1f}")
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
    
    # 8. TEAM TOTALS
    print("8. TEAM TOTALS")
    print("-" * 40)
    
    # Home team totals
    p_home_over_70 = poisson_over_prob(projected_home, 70)
    p_home_over_75 = poisson_over_prob(projected_home, 75)
    p_home_over_80 = poisson_over_prob(projected_home, 80)
    p_home_over_85 = poisson_over_prob(projected_home, 85)
    
    print(f"   {home_team}:")
    print(f"      Over 70 Points: {p_home_over_70:.3f} ({p_home_over_70*100:.1f}%)")
    print(f"      Over 75 Points: {p_home_over_75:.3f} ({p_home_over_75*100:.1f}%)")
    print(f"      Over 80 Points: {p_home_over_80:.3f} ({p_home_over_80*100:.1f}%)")
    print(f"      Over 85 Points: {p_home_over_85:.3f} ({p_home_over_85*100:.1f}%)")
    print()
    
    # Away team totals
    p_away_over_70 = poisson_over_prob(projected_away, 70)
    p_away_over_75 = poisson_over_prob(projected_away, 75)
    p_away_over_80 = poisson_over_prob(projected_away, 80)
    p_away_over_85 = poisson_over_prob(projected_away, 85)
    
    print(f"   {away_team}:")
    print(f"      Over 70 Points: {p_away_over_70:.3f} ({p_away_over_70*100:.1f}%)")
    print(f"      Over 75 Points: {p_away_over_75:.3f} ({p_away_over_75*100:.1f}%)")
    print(f"      Over 80 Points: {p_away_over_80:.3f} ({p_away_over_80*100:.1f}%)")
    print(f"      Over 85 Points: {p_away_over_85:.3f} ({p_away_over_85*100:.1f}%)")
    print()
    
    # 9. FULL GAME TOTALS
    print("9. FULL GAME TOTALS")
    print("-" * 40)
    
    p_over_140 = poisson_over_prob(projected_total, 140)
    p_over_145 = poisson_over_prob(projected_total, 145)
    p_over_150 = poisson_over_prob(projected_total, 150)
    p_over_155 = poisson_over_prob(projected_total, 155)
    p_over_160 = poisson_over_prob(projected_total, 160)
    p_over_165 = poisson_over_prob(projected_total, 165)
    p_over_170 = poisson_over_prob(projected_total, 170)
    
    print(f"   Over 140 Points: {p_over_140:.3f} ({p_over_140*100:.1f}%)")
    print(f"   Over 145 Points: {p_over_145:.3f} ({p_over_145*100:.1f}%)")
    print(f"   Over 150 Points: {p_over_150:.3f} ({p_over_150*100:.1f}%)")
    print(f"   Over 155 Points: {p_over_155:.3f} ({p_over_155*100:.1f}%)")
    print(f"   Over 160 Points: {p_over_160:.3f} ({p_over_160*100:.1f}%)")
    print(f"   Over 165 Points: {p_over_165:.3f} ({p_over_165*100:.1f}%)")
    print(f"   Over 170 Points: {p_over_170:.3f} ({p_over_170*100:.1f}%)")
    print()
    
    # 10. MARKET ANALYSIS
    print("10. MARKET LINE ANALYSIS")
    print("-" * 40)
    
    print(f"   Spread Line: {market_data['spread']} ({home_team} favored)" if market_data['spread'] < 0 else f"   Spread Line: {market_data['spread']} ({away_team} favored)")
    print(f"   Open Line: {market_data['open_line']}")
    print(f"   Current Line: {market_data['current_line']}")
    print(f"   Line Movement: {market_data['current_line'] - market_data['open_line']:+.1f}")
    print(f"   Total Line: {market_data.get('total', 'N/A')}")
    print()
    
    # 11. KEY HANDICAPPING FACTORS
    print("11. KEY HANDICAPPING FACTORS")
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
                "over_70": round(p_home_over_70, 4),
                "over_75": round(p_home_over_75, 4),
                "over_80": round(p_home_over_80, 4),
                "over_85": round(p_home_over_85, 4),
            },
            "away": {
                "over_70": round(p_away_over_70, 4),
                "over_75": round(p_away_over_75, 4),
                "over_80": round(p_away_over_80, 4),
                "over_85": round(p_away_over_85, 4),
            }
        },
        "full_game_totals": {
            "over_140": round(p_over_140, 4),
            "over_145": round(p_over_145, 4),
            "over_150": round(p_over_150, 4),
            "over_155": round(p_over_155, 4),
            "over_160": round(p_over_160, 4),
            "over_165": round(p_over_165, 4),
            "over_170": round(p_over_170, 4),
        },
        "recommendations": {
            "full_game_spread": lean,
            "full_game_total": "Pass",
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


def run_uruguay_argentina_analysis():
    """Run comprehensive analysis for Uruguay vs Argentina (FIBA)"""
    
    print("=" * 80)
    print("COMPREHENSIVE ANALYSIS: URUGUAY vs ARGENTINA")
    print("FIBA International - July 2, 2026")
    print("=" * 80)
    print()
    
    # Uruguay (Home) - Based on FIBA Americas rankings and recent form
    # Uruguay is typically a mid-tier FIBA Americas team
    home_data = {
        'ortg': 104.5,        # Offensive Rating (FIBA scale)
        'drtg': 108.0,        # Defensive Rating
        'baseline_net': -3.5,  # Baseline net rating
        'recent_net': -2.0,    # Recent net rating (last 5 games)
        'pace': 72.5,          # Pace (possessions per 40 min - FIBA)
        'rest_days': 3,
        'travel_km': 0,        # Home team, no travel
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': 3.5,     # Home court advantage factor
        'rotation_depth': 9,   # Number of regular rotation players
        'injury_status': 'green',  # Healthy roster
        'coach_stability': 'green',
        'motivation': 'green',  # Playing in front of home crowd
    }
    
    # Argentina (Away) - Historically stronger FIBA team
    # Argentina has a strong basketball tradition with deep talent pool
    away_data = {
        'ortg': 112.0,        # Offensive Rating (FIBA scale)
        'drtg': 104.5,        # Defensive Rating
        'baseline_net': 7.5,   # Baseline net rating
        'recent_net': 6.0,     # Recent net rating (last 5 games)
        'pace': 74.0,          # Pace (possessions per 40 min - FIBA)
        'rest_days': 2,
        'travel_km': 200,      # Travel from Argentina to Uruguay
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': -2.0,    # Road performance factor (still strong on road)
        'rotation_depth': 10,  # Number of regular rotation players
        'injury_status': 'green',  # Healthy roster
        'coach_stability': 'green',
        'motivation': 'green',  # Rivalry match
    }
    
    # Market data
    market_data = {
        'open_line': -5.5,     # Argentina opened as 5.5 point favorites
        'current_line': -6.5,  # Current line moved to Argentina -6.5
        'spread': -6.5,        # Argentina favored by 6.5
        'total': 155.0,        # Over/Under total
    }
    
    # Run analysis
    result = analyze_fiba_match(
        home_team="Uruguay",
        away_team="Argentina",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Estadio Antel, Montevideo, Uruguay",
        date="2026-07-02",
        league="FIBA Americas"
    )
    
    return result


def run_panama_cuba_analysis():
    """Run comprehensive analysis for Panama vs Cuba (FIBA)"""
    
    print("=" * 80)
    print("COMPREHENSIVE ANALYSIS: PANAMA vs CUBA")
    print("FIBA International - July 2, 2026")
    print("=" * 80)
    print()
    
    # Panama (Home) - Emerging FIBA team
    home_data = {
        'ortg': 101.0,        # Offensive Rating (FIBA scale)
        'drtg': 106.5,        # Defensive Rating
        'baseline_net': -5.5,  # Baseline net rating
        'recent_net': -4.0,    # Recent net rating (last 5 games)
        'pace': 71.0,          # Pace (possessions per 40 min - FIBA)
        'rest_days': 3,
        'travel_km': 0,        # Home team, no travel
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': 3.0,     # Home court advantage factor
        'rotation_depth': 8,   # Number of regular rotation players
        'injury_status': 'yellow',  # Minor injury concerns
        'coach_stability': 'yellow',
        'motivation': 'green',  # Playing at home
    }
    
    # Cuba (Away) - Similar level to Panama
    away_data = {
        'ortg': 102.5,        # Offensive Rating (FIBA scale)
        'drtg': 105.0,        # Defensive Rating
        'baseline_net': -2.5,  # Baseline net rating
        'recent_net': -3.0,    # Recent net rating (last 5 games)
        'pace': 70.5,          # Pace (possessions per 40 min - FIBA)
        'rest_days': 2,
        'travel_km': 1800,     # Travel from Cuba to Panama
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': -1.5,    # Road performance factor
        'rotation_depth': 8,   # Number of regular rotation players
        'injury_status': 'green',  # Healthy roster
        'coach_stability': 'yellow',
        'motivation': 'yellow',  # Long travel
    }
    
    # Market data
    market_data = {
        'open_line': -1.5,     # Panama opened as 1.5 point favorites
        'current_line': -2.5,  # Current line moved to Panama -2.5
        'spread': -2.5,        # Panama favored by 2.5
        'total': 148.0,        # Over/Under total
    }
    
    # Run analysis
    result = analyze_fiba_match(
        home_team="Panama",
        away_team="Cuba",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Arena Roberto Duran, Panama City, Panama",
        date="2026-07-02",
        league="FIBA Americas"
    )
    
    return result


def main():
    """Run both FIBA basketball match analyses"""
    
    print("=" * 80)
    print("FIBA BASKETBALL MATCH ANALYSIS - July 2, 2026")
    print("=" * 80)
    print()
    
    all_results = {}
    
    # Match 1: Uruguay vs Argentina
    print("\n")
    print("#" * 80)
    print("# MATCH 1: URUGUAY vs ARGENTINA")
    print("#" * 80)
    print()
    result1 = run_uruguay_argentina_analysis()
    all_results["uruguay_vs_argentina"] = result1
    
    # Match 2: Panama vs Cuba
    print("\n")
    print("#" * 80)
    print("# MATCH 2: PANAMA vs CUBA")
    print("#" * 80)
    print()
    result2 = run_panama_cuba_analysis()
    all_results["panama_vs_cuba"] = result2
    
    # Save combined results
    output_path = Path("output/fiba_matches_july2_2026.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print("\n")
    print("=" * 80)
    print("COMBINED RESULTS SUMMARY")
    print("=" * 80)
    print()
    
    for match_key, match_result in all_results.items():
        gi = match_result['game_info']
        proj = match_result['projections']
        recs = match_result['recommendations']
        conf = match_result['confidence']
        
        print(f"  {gi['home_team']} vs {gi['away_team']}:")
        print(f"    Projected: {gi['home_team']} {proj['home_score']:.1f} - {gi['away_team']} {proj['away_score']:.1f}")
        print(f"    Total: {proj['total']:.1f}")
        print(f"    Home Win Prob: {proj['home_win_prob']:.1%}")
        print(f"    Recommendation: {recs['full_game_spread']}")
        print(f"    Confidence: {conf}")
        print()
    
    print(f"Detailed results saved to: {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()