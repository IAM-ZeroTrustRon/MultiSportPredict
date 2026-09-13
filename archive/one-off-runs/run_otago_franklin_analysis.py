#!/usr/bin/env python
"""
Comprehensive Analysis for New Zealand NBL Game
- Otago Nuggets vs Franklin Bulls
Focus: 1Q (First Quarter) Projections and FG (Field Goals) Analysis
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
    process_basketball_q1,
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
    date="2026-06-05", league="NZ_NBL"
):
    """Analyze a single basketball match and return results with focus on 1Q and FG"""
    
    print("=" * 80)
    print(f"COMPREHENSIVE MATCH ANALYSIS: {home_team} vs {away_team}")
    print(f"{league} - {date}")
    print(f"Venue: {venue}")
    print("Focus: 1Q Projections & FG Analysis")
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
    
    # 6. RUN THE MODEL - Full Game
    print("6. MODEL PROJECTION (Full Game)")
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
    
    # 7. Q1 PROJECTION (PRIMARY FOCUS)
    print("7. FIRST QUARTER PROJECTION (PRIMARY FOCUS)")
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
    print(f"   Q1 Pace Factor: {q1_proj['q1_pace_factor']:.2f}")
    print(f"   Q1 Context Adjustment: {q1_proj['q1_ctx_adjustment']:+.2f}")
    print()
    
    # 8. FG (FIELD GOAL) ANALYSIS
    print("8. FIELD GOAL (FG) ANALYSIS")
    print("-" * 40)
    
    # Calculate expected FG percentages based on offensive/defensive ratings
    league_avg_fg_pct = 0.455  # Typical basketball FG%
    
    home_fg_offense_factor = home_data['ortg'] / 110.0  # Normalize to league average
    home_fg_defense_factor = 110.0 / home_data['drtg']  # Lower DRTG = better defense
    away_fg_offense_factor = away_data['ortg'] / 110.0
    away_fg_defense_factor = 110.0 / away_data['drtg']
    
    # Projected FG% for each team
    home_proj_fg_pct = league_avg_fg_pct * home_fg_offense_factor * away_fg_defense_factor
    away_proj_fg_pct = league_avg_fg_pct * away_fg_offense_factor * home_fg_defense_factor
    
    # Adjust for home court
    home_proj_fg_pct *= 1.02  # Small home court boost
    
    # Q1 FG% tends to be slightly lower (teams feeling each other out)
    home_q1_fg_pct = home_proj_fg_pct * 0.97
    away_q1_fg_pct = away_proj_fg_pct * 0.97
    
    print(f"   {home_team}:")
    print(f"      Projected FG%: {home_proj_fg_pct:.3f} ({home_proj_fg_pct*100:.1f}%)")
    print(f"      Q1 Projected FG%: {home_q1_fg_pct:.3f} ({home_q1_fg_pct*100:.1f}%)")
    print(f"      Offense Factor: {home_fg_offense_factor:.3f}")
    print(f"      Defense Factor (vs opponent): {away_fg_defense_factor:.3f}")
    print()
    print(f"   {away_team}:")
    print(f"      Projected FG%: {away_proj_fg_pct:.3f} ({away_proj_fg_pct*100:.1f}%)")
    print(f"      Q1 Projected FG%: {away_q1_fg_pct:.3f} ({away_q1_fg_pct*100:.1f}%)")
    print(f"      Offense Factor: {away_fg_offense_factor:.3f}")
    print(f"      Defense Factor (vs opponent): {home_fg_defense_factor:.3f}")
    print()
    
    # FG% edge analysis
    fg_edge = home_proj_fg_pct - away_proj_fg_pct
    q1_fg_edge = home_q1_fg_pct - away_q1_fg_pct
    
    print(f"   FG% Edge: {home_team} +{fg_edge:.3f} (full game)")
    print(f"   Q1 FG% Edge: {home_team} +{q1_fg_edge:.3f}")
    print()
    
    # 9. PROJECTED SCORES
    print("9. PROJECTED FINAL SCORE")
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
    
    # 10. MARKET LINE ANALYSIS
    print("10. MARKET LINE ANALYSIS")
    print("-" * 40)
    
    print(f"   Spread Line: {market_data['spread']} ({home_team} favored)" if market_data['spread'] > 0 else f"   Spread Line: {market_data['spread']} ({away_team} favored)")
    print(f"   Open Line: {market_data['open_line']}")
    print(f"   Current Line: {market_data['current_line']}")
    print(f"   Line Movement: {market_data['current_line'] - market_data['open_line']:+.1f}")
    print(f"   Total Line: {market_data['total']}")
    print()
    
    # 11. Q1-SPECIFIC HANDICAPPING FACTORS
    print("11. Q1-SPECIFIC HANDICAPPING FACTORS")
    print("-" * 40)
    print()
    
    # Analyze factors that specifically affect Q1 performance
    print(f"   Q1 FACTORS FAVORING {home_team.upper()}:")
    if home_data['rest_days'] > away_data['rest_days']:
        print(f"   [+] More rest ({home_data['rest_days']} vs {away_data['rest_days']} days) - fresher start")
    if home_data['split_edge'] > away_data['split_edge']:
        print(f"   [+] Better home/away split ({home_data['split_edge']:+.1f} vs {away_data['split_edge']:+.1f})")
    if home_ctx > away_ctx:
        print(f"   [+] Better contextual factors (rotation, injuries, coaching)")
    if home_data['ortg'] > away_data['ortg']:
        print(f"   [+] Better offense - may start stronger (ORTG: {home_data['ortg']:.1f} vs {away_data['ortg']:.1f})")
    print()
    
    print(f"   Q1 FACTORS FAVORING {away_team.upper()}:")
    if away_data['rest_days'] > home_data['rest_days']:
        print(f"   [+] More rest ({away_data['rest_days']} vs {home_data['rest_days']} days) - fresher start")
    if away_data['split_edge'] > home_data['split_edge']:
        print(f"   [+] Better road performance ({away_data['split_edge']:+.1f} vs {home_data['split_edge']:+.1f})")
    if away_ctx > home_ctx:
        print(f"   [+] Better contextual factors (rotation, injuries, coaching)")
    if away_data['ortg'] > home_data['ortg']:
        print(f"   [+] Better offense - may start stronger (ORTG: {away_data['ortg']:.1f} vs {home_data['ortg']:.1f})")
    print()
    
    # 12. FG-SPECIFIC HANDICAPPING FACTORS
    print("12. FG-SPECIFIC HANDICAPPING FACTORS")
    print("-" * 40)
    print()
    
    print(f"   FG FACTORS FAVORING {home_team.upper()}:")
    if home_proj_fg_pct > away_proj_fg_pct:
        print(f"   [+] Higher projected FG% ({home_proj_fg_pct:.3f} vs {away_proj_fg_pct:.3f})")
    if home_data['drtg'] < away_data['drtg']:
        print(f"   [+] Better defense limits opponent FG% (DRTG: {home_data['drtg']:.1f} vs {away_data['drtg']:.1f})")
    if home_data['ortg'] > away_data['ortg']:
        print(f"   [+] Better offense creates better shots (ORTG: {home_data['ortg']:.1f} vs {away_data['ortg']:.1f})")
    print()
    
    print(f"   FG FACTORS FAVORING {away_team.upper()}:")
    if away_proj_fg_pct > home_proj_fg_pct:
        print(f"   [+] Higher projected FG% ({away_proj_fg_pct:.3f} vs {home_proj_fg_pct:.3f})")
    if away_data['drtg'] < home_data['drtg']:
        print(f"   [+] Better defense limits opponent FG% (DRTG: {away_data['drtg']:.1f} vs {home_data['drtg']:.1f})")
    if away_data['ortg'] > home_data['ortg']:
        print(f"   [+] Better offense creates better shots (ORTG: {away_data['ortg']:.1f} vs {home_data['ortg']:.1f})")
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
    print("   === 1Q PROJECTIONS ===")
    print(f"   Q1 Projected: {home_team} {q1_proj['home_q1_points']:.1f} - {away_team} {q1_proj['away_q1_points']:.1f}")
    print(f"   Q1 Spread: {q1_proj['q1_spread']:+.1f}")
    print(f"   Q1 Total: {q1_proj['q1_total']:.1f}")
    print(f"   Q1 Home Win Prob: {q1_proj['q1_prob_home_win']:.1%}")
    print()
    print("   === FG PROJECTIONS ===")
    print(f"   {home_team} FG%: {home_proj_fg_pct:.3f} | Q1 FG%: {home_q1_fg_pct:.3f}")
    print(f"   {away_team} FG%: {away_proj_fg_pct:.3f} | Q1 FG%: {away_q1_fg_pct:.3f}")
    print()
    print(f"   RECOMMENDATION: {lean}")
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
        "q1_projections": {
            **q1_proj,
            "home_fg_pct": round(home_q1_fg_pct, 4),
            "away_fg_pct": round(away_q1_fg_pct, 4),
        },
        "fg_analysis": {
            "home_full_game_fg_pct": round(home_proj_fg_pct, 4),
            "away_full_game_fg_pct": round(away_proj_fg_pct, 4),
            "home_q1_fg_pct": round(home_q1_fg_pct, 4),
            "away_q1_fg_pct": round(away_q1_fg_pct, 4),
            "fg_edge": round(fg_edge, 4),
            "q1_fg_edge": round(q1_fg_edge, 4),
            "league_avg_fg_pct": league_avg_fg_pct,
        },
        "recommendations": {
            "full_game_spread": lean,
            "full_game_total": f"Over {market_data['total']}" if projected_total > market_data['total'] else f"Under {market_data['total']}",
            "q1_spread": f"{'Home' if q1_proj['q1_spread'] > 0 else 'Away'} Q1 {abs(q1_proj['q1_spread']):.1f}",
            "q1_total": f"Over {q1_proj['q1_total']:.1f}" if q1_proj['q1_total'] > market_data.get('q1_total', q1_proj['q1_total']) else f"Under {q1_proj['q1_total']:.1f}",
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


def run_otago_franklin_analysis():
    """Run comprehensive analysis for Otago Nuggets vs Franklin Bulls"""
    
    print("=" * 80)
    print("COMPREHENSIVE ANALYSIS: OTAGO NUGGETS vs FRANKLIN BULLS")
    print("New Zealand NBL - June 5, 2026")
    print("Focus: 1Q Projections & FG Analysis")
    print("=" * 80)
    print()
    
    # Define team data based on NZ NBL metrics
    # Otago Nuggets (Home) - Based in Dunedin
    home_data = {
        'ortg': 108.5,        # Offensive Rating
        'drtg': 112.3,        # Defensive Rating
        'baseline_net': -3.8,  # Baseline net rating
        'recent_net': -2.1,    # Recent net rating (last 10 games)
        'pace': 96.0,          # Pace (possessions per 48 min)
        'rest_days': 3,
        'travel_km': 0,        # Home team, no travel
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': 4.5,     # Home court advantage factor (strong at home)
        'rotation_depth': 9,   # Number of regular rotation players
        'injury_status': 'yellow',  # Some minor injuries
        'coach_stability': 'green',
        'motivation': 'green',  # Playing for playoff positioning
    }
    
    # Franklin Bulls (Away) - Based in Auckland region
    away_data = {
        'ortg': 113.2,        # Offensive Rating
        'drtg': 109.8,        # Defensive Rating
        'baseline_net': 3.4,   # Baseline net rating
        'recent_net': 4.1,     # Recent net rating (last 10 games)
        'pace': 98.5,          # Pace (possessions per 48 min)
        'rest_days': 2,
        'travel_km': 650,      # Travel from Auckland to Dunedin
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': -0.8,    # Road performance factor
        'rotation_depth': 10,  # Number of regular rotation players
        'injury_status': 'green',  # Healthy roster
        'coach_stability': 'green',
        'motivation': 'green',  # Playing for playoff seeding
    }
    
    # Market data
    market_data = {
        'open_line': 2.5,      # Franklin Bulls opened as slight favorites
        'current_line': 1.5,   # Current line moved towards Otago
        'spread': 1.5,         # Franklin Bulls favored by 1.5
        'total': 185.5,        # Over/Under total
    }
    
    # Run analysis
    result = analyze_basketball_match(
        home_team="Otago Nuggets",
        away_team="Franklin Bulls",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Edgar Centre, Dunedin",
        date="2026-06-05",
        league="NZ_NBL"
    )
    
    # Save results
    output_path = Path("output/otago_nuggets_vs_franklin_bulls_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print("=" * 80)
    print(f"Detailed results saved to: {output_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    run_otago_franklin_analysis()