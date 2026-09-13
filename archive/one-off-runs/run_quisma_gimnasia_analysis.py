#!/usr/bin/env python
"""
Comprehensive Analysis for Argentine LNB Game
- Asociacion Atletica Quisma vs Gimnasia Esgrima Comodoro Rivadavia

Focus: Full Game, 1Q, 1H, Spreads, Moneyline, Totals
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Import the MultiSportModel functions
from MultiSportModel import (
    run_basketball_game_automated,
    process_basketball_game,
    process_basketball_q1,
    process_basketball_prop,
    project_basketball_q1,
    efficiency_gap,
    historical_efficiency_gap,
    pace_edge,
    rest_travel_score,
    home_away_score,
    context_score,
    eu_build_full_game,
    eu_build_q1,
    eu_build_prop,
    eu_score_to_prob,
    eu_recommendation,
    GameContext,
    TeamMetrics,
    Q1Metrics,
    PlayerProp,
)


def analyze_basketball_match(
    home_team, away_team, home_data, away_data, market_data, venue, 
    date="2026-06-06", league="LNB (Argentina)", player_props_data=None
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
    
    pace_gap = pace_edge(home_data['pace'], away_data['pace'])
    avg_pace = (home_data['pace'] + away_data['pace']) / 2
    
    print(f"   {home_team} Pace: {home_data['pace']:.1f}")
    print(f"   {away_team} Pace: {away_data['pace']:.1f}")
    print(f"   Average Pace: {avg_pace:.1f}")
    print(f"   Pace Edge: {pace_gap:+.2f}")
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
    
    print(f"   {home_team}: {home_data['rest_days']} rest days | Rest Score: {home_rest_score:+.1f}")
    print(f"   {away_team}: {away_data['rest_days']} rest days | Rest Score: {away_rest_score:+.1f}")
    print(f"   Rest Gap: {rest_gap:+.2f}")
    print()
    
    # 4. RUN THE MODEL - Full Game (European Template)
    print("4. FULL GAME PROJECTION (European Template)")
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
        open_line=home_data.get('open_line', market_data['open_line']),
        current_line=home_data.get('current_line', market_data['current_line']),
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
        open_line=away_data.get('open_line', -market_data['open_line']),
        current_line=away_data.get('current_line', -market_data['current_line']),
    )
    
    full_game_result = eu_build_full_game(home_tm, away_tm, ctx)
    
    print(f"   Model Edge: {full_game_result['model_edge']:+.2f}")
    print(f"   Market Score: {full_game_result['market_score']:+.2f}")
    print(f"   Win Probability: {full_game_result['probability']:.3f}")
    print(f"   Projected Score: {home_team} {full_game_result['projected_home_score']:.1f} - {away_team} {full_game_result['projected_away_score']:.1f}")
    print(f"   Projected Total: {full_game_result['projected_total']:.1f}")
    print(f"   Recommendation: {full_game_result['lean']}")
    print()
    
    # 5. Q1 PROJECTION
    print("5. FIRST QUARTER (1Q) PROJECTION")
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
    
    # Q1 Recommendation
    q1_market_line = market_data.get('q1_spread', q1_proj['q1_spread'] * 0.8)
    q1_edge = q1_proj['q1_spread'] - q1_market_line
    if abs(q1_edge) >= 1.5:
        q1_lean = f"{'Home' if q1_edge > 0 else 'Away'} Q1 {abs(q1_market_line):.1f}"
    else:
        q1_lean = "Pass"
    print(f"   Q1 Recommendation: {q1_lean}")
    print()
    
    # 6. FIRST HALF (1H) PROJECTION
    print("6. FIRST HALF (1H) PROJECTION")
    print("-" * 40)
    
    home_1h_points = (q1_proj['home_q1_points'] + full_game_result['projected_home_score'] / 2) / 1.5
    away_1h_points = (q1_proj['away_q1_points'] + full_game_result['projected_away_score'] / 2) / 1.5
    home_1h_points *= 1.8
    away_1h_points *= 1.8
    home_1h_points *= 1.03
    away_1h_points *= 0.97
    
    h1_spread = home_1h_points - away_1h_points
    h1_total = home_1h_points + away_1h_points
    
    h1_score = h1_spread * 0.6
    h1_prob = eu_score_to_prob(h1_score)
    
    h1_market_line = market_data.get('h1_spread', h1_spread * 0.9)
    h1_edge = h1_spread - h1_market_line
    
    if abs(h1_edge) >= 2.0:
        h1_lean = f"{'Home' if h1_edge > 0 else 'Away'} 1H {abs(h1_market_line):.1f}"
    else:
        h1_lean = "Pass"
    
    print(f"   Projected 1H Score: {home_team} {home_1h_points:.1f} - {away_team} {away_1h_points:.1f}")
    print(f"   1H Spread: {h1_spread:+.1f}")
    print(f"   1H Total: {h1_total:.1f}")
    print(f"   1H Home Win Probability: {h1_prob:.3f}")
    print(f"   1H Recommendation: {h1_lean}")
    print()
    
    # 7. FG (FIELD GOAL) ANALYSIS
    print("7. FIELD GOAL (FG) ANALYSIS")
    print("-" * 40)
    
    league_avg_fg_pct = 0.465
    
    home_fg_offense_factor = home_data['ortg'] / 110.0
    home_fg_defense_factor = 110.0 / home_data['drtg']
    away_fg_offense_factor = away_data['ortg'] / 110.0
    away_fg_defense_factor = 110.0 / away_data['drtg']
    
    home_proj_fg_pct = league_avg_fg_pct * home_fg_offense_factor * away_fg_defense_factor
    away_proj_fg_pct = league_avg_fg_pct * away_fg_offense_factor * home_fg_defense_factor
    home_proj_fg_pct *= 1.02
    
    home_q1_fg_pct = home_proj_fg_pct * 0.97
    away_q1_fg_pct = away_proj_fg_pct * 0.97
    
    print(f"   {home_team}:")
    print(f"      Projected FG%: {home_proj_fg_pct:.3f} ({home_proj_fg_pct*100:.1f}%)")
    print(f"      Q1 Projected FG%: {home_q1_fg_pct:.3f} ({home_q1_fg_pct*100:.1f}%)")
    print()
    print(f"   {away_team}:")
    print(f"      Projected FG%: {away_proj_fg_pct:.3f} ({away_proj_fg_pct*100:.1f}%)")
    print(f"      Q1 Projected FG%: {away_q1_fg_pct:.3f} ({away_q1_fg_pct*100:.1f}%)")
    print()
    
    fg_edge = home_proj_fg_pct - away_proj_fg_pct
    print(f"   FG% Edge: {home_team} +{fg_edge:.3f}")
    print()
    
    # 8. SPREAD ANALYSIS
    print("8. SPREAD ANALYSIS")
    print("-" * 40)
    
    spread_line = market_data['spread']
    model_spread = full_game_result['projected_home_score'] - full_game_result['projected_away_score']
    spread_edge = model_spread - spread_line
    
    if spread_edge > 2.0:
        spread_lean = f"Home {spread_line:+.1f}" if spread_line > 0 else f"Home {abs(spread_line):.1f}"
    elif spread_edge < -2.0:
        spread_lean = f"Away {abs(spread_line):.1f}" if spread_line < 0 else f"Away {spread_line:.1f}"
    else:
        spread_lean = "Pass"
    
    print(f"   Market Spread: {spread_line:+.1f} ({home_team} {'favored' if spread_line > 0 else 'underdog'})")
    print(f"   Model Spread: {model_spread:+.1f}")
    print(f"   Edge: {spread_edge:+.1f}")
    print(f"   Spread Recommendation: {spread_lean}")
    print()
    
    # 9. MONEYLINE ANALYSIS
    print("9. MONEYLINE ANALYSIS")
    print("-" * 40)
    
    ml_prob = full_game_result['probability']
    if ml_prob >= 0.60:
        ml_lean = f"Home ML ({home_team})"
    elif ml_prob <= 0.40:
        ml_lean = f"Away ML ({away_team})"
    else:
        ml_lean = "Pass"
    
    print(f"   {home_team} Win Probability: {ml_prob:.3f}")
    print(f"   {away_team} Win Probability: {1 - ml_prob:.3f}")
    print(f"   Moneyline Recommendation: {ml_lean}")
    print()
    
    # 10. TOTALS ANALYSIS
    print("10. TOTALS ANALYSIS")
    print("-" * 40)
    
    model_total = full_game_result['projected_total']
    market_total = market_data['total']
    total_edge = model_total - market_total
    
    if total_edge > 3.0:
        total_lean = f"Over {market_total}"
    elif total_edge < -3.0:
        total_lean = f"Under {market_total}"
    else:
        total_lean = "Pass"
    
    print(f"   Market Total: {market_total}")
    print(f"   Model Total: {model_total:.1f}")
    print(f"   Edge: {total_edge:+.1f}")
    print(f"   Totals Recommendation: {total_lean}")
    print()
    
    # 11. PLAYER PROPS ANALYSIS
    print("11. PLAYER PROPS ANALYSIS")
    print("-" * 40)
    
    props_results = []
    if player_props_data:
        for prop in player_props_data:
            prop_result = process_basketball_prop(prop)
            props_results.append({
                "player_name": prop['player_name'],
                "team": prop['team'],
                "prop_type": prop['prop_type'],
                "prop_line": prop['prop_line'],
                "model_projection": round(prop['player_avg'], 1),
                "edge": round(prop_result.get('model_score', 0), 2),
                "model_prob": round(prop_result.get('model_prob', 0.5), 3),
                "lean": prop_result.get('lean', 'Pass'),
            })
            print(f"   {prop['player_name']:<25} {prop['prop_type']:<15} Line: {prop['prop_line']:>5.1f} | Proj: {prop['player_avg']:>5.1f} | Lean: {prop_result.get('lean', 'Pass')}")
    
    print()
    
    # FINAL SUMMARY
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Match: {home_team} vs {away_team}")
    print(f"   Projected Score: {home_team} {full_game_result['projected_home_score']:.1f} - {away_team} {full_game_result['projected_away_score']:.1f}")
    print(f"   Projected Total: {full_game_result['projected_total']:.1f}")
    print(f"   Win Probability: {home_team} {ml_prob:.1%} | {away_team} {(1-ml_prob):.1%}")
    print()
    print("   === BETTING RECOMMENDATIONS ===")
    print(f"   Spread: {spread_lean}")
    print(f"   Moneyline: {ml_lean}")
    print(f"   Total: {total_lean}")
    print(f"   1Q Spread: {q1_lean}")
    print(f"   1H Spread: {h1_lean}")
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
        "full_game_projection": full_game_result,
        "q1_projection": q1_proj,
        "h1_projection": {
            "home_points": round(home_1h_points, 1),
            "away_points": round(away_1h_points, 1),
            "spread": round(h1_spread, 1),
            "total": round(h1_total, 1),
            "home_win_prob": round(h1_prob, 3),
            "recommendation": h1_lean
        },
        "fg_analysis": {
            "home_full_game_fg_pct": round(home_proj_fg_pct, 4),
            "away_full_game_fg_pct": round(away_proj_fg_pct, 4),
            "home_q1_fg_pct": round(home_q1_fg_pct, 4),
            "away_q1_fg_pct": round(away_q1_fg_pct, 4),
            "fg_edge": round(fg_edge, 4),
        },
        "recommendations": {
            "spread": spread_lean,
            "moneyline": ml_lean,
            "total": total_lean,
            "q1_spread": q1_lean,
            "h1_spread": h1_lean,
        },
        "player_props": props_results,
        "timestamp": datetime.now().isoformat()
    }
    
    return results


def run_quisma_gimnasia_analysis():
    """Run comprehensive analysis for Quisma vs Gimnasia"""
    
    print("\n" + "=" * 80)
    print("ARGENTINE LNB: ASOCIACION ATLETICA QUISMA vs GIMNASIA ESGRIMA COMODORO RIVADAVIA")
    print("LNB (Argentina) - June 6, 2026")
    print("=" * 80 + "\n")
    
    # Quisma (Home) - Strong home team with good offense
    home_data = {
        'ortg': 106.8,
        'drtg': 103.2,
        'baseline_net': 3.6,
        'recent_net': 4.8,
        'pace': 92.5,
        'rest_days': 3,
        'travel_km': 0,
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': 5.2,  # Strong home court advantage
        'rotation_depth': 9,
        'injury_status': 'green',
        'coach_stability': 'green',
        'motivation': 'green',
    }
    
    # Gimnasia Comodoro Rivadavia (Away) - Decent road team
    away_data = {
        'ortg': 102.5,
        'drtg': 105.8,
        'baseline_net': -3.3,
        'recent_net': -2.1,
        'pace': 90.8,
        'rest_days': 2,
        'travel_km': 1200,  # Significant travel from Comodoro Rivadavia
        'back_to_back': False,
        'three_in_six': True,  # Playing 3 games in 6 days
        'split_edge': -1.5,  # Poor road record
        'rotation_depth': 8,
        'injury_status': 'yellow',  # Some minor injuries
        'coach_stability': 'green',
        'motivation': 'yellow',
    }
    
    market_data = {
        'open_line': -3.5,
        'current_line': -4.5,
        'spread': -4.5,  # Quisma favored by 4.5
        'total': 158.5,
        'q1_spread': -1.5,
        'h1_spread': -2.5,
    }
    
    # Player props for key players (typical LNB stats)
    player_props = [
        # Quisma key players
        {
            "player_name": "M. Morales",
            "team": "Quisma",
            "opponent": "Gimnasia CR",
            "prop_type": "Points",
            "prop_line": 16.5,
            "player_avg": 18.2,
            "minutes_proj": 32.0,
            "usage_rate": 26.0,
            "game_pace": 92,
            "opp_def_rating": 105.8,
            "opp_position_def_rating": 104.0,
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 16.0,
            "current_prop_line": 16.5,
        },
        {
            "player_name": "L. Vildoza",
            "team": "Quisma",
            "opponent": "Gimnasia CR",
            "prop_type": "Assists",
            "prop_line": 5.5,
            "player_avg": 6.1,
            "minutes_proj": 28.0,
            "usage_rate": 22.0,
            "game_pace": 92,
            "opp_def_rating": 105.8,
            "opp_position_def_rating": 103.0,
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 5.5,
            "current_prop_line": 5.5,
        },
        # Gimnasia CR key players
        {
            "player_name": "F. Barre",
            "team": "Gimnasia CR",
            "opponent": "Quisma",
            "prop_type": "Points",
            "prop_line": 14.5,
            "player_avg": 15.3,
            "minutes_proj": 30.0,
            "usage_rate": 24.0,
            "game_pace": 92,
            "opp_def_rating": 103.2,
            "opp_position_def_rating": 102.0,
            "injury_boost": "yellow",
            "blowout_risk": "yellow",
            "role": "starter",
            "open_prop_line": 14.5,
            "current_prop_line": 14.5,
        },
        {
            "player_name": "T. Zanzottera",
            "team": "Gimnasia CR",
            "opponent": "Quisma",
            "prop_type": "Rebounds",
            "prop_line": 7.5,
            "player_avg": 8.2,
            "minutes_proj": 26.0,
            "usage_rate": 18.0,
            "game_pace": 92,
            "opp_def_rating": 103.2,
            "opp_position_def_rating": 101.0,
            "injury_boost": "green",
            "blowout_risk": "red",
            "role": "starter",
            "open_prop_line": 7.5,
            "current_prop_line": 7.5,
        },
    ]
    
    result = analyze_basketball_match(
        home_team="Quisma",
        away_team="Gimnasia CR",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Estadio Quisma, Santiago del Estero",
        date="2026-06-06",
        league="LNB (Argentina)",
        player_props_data=player_props
    )
    
    return result


def main():
    """Run Quisma vs Gimnasia analysis"""
    
    print("=" * 80)
    print("ARGENTINE LNB COMPREHENSIVE ANALYSIS")
    print("June 6, 2026")
    print("=" * 80)
    
    result = run_quisma_gimnasia_analysis()
    
    # Save results
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / "quisma_vs_gimnasia_analysis.json", 'w') as f:
        json.dump(result, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()
    print("Quisma vs Gimnasia CR:")
    print(f"  Spread: {result['recommendations']['spread']}")
    print(f"  Moneyline: {result['recommendations']['moneyline']}")
    print(f"  Total: {result['recommendations']['total']}")
    print(f"  1Q: {result['recommendations']['q1_spread']}")
    print(f"  1H: {result['recommendations']['h1_spread']}")
    print()
    print(f"Results saved to: output/quisma_vs_gimnasia_analysis.json")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()