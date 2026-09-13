#!/usr/bin/env python
"""
Comprehensive Analysis for Greek Basketball Derby
- Olympiacos vs Panathinaikos
EuroLeague - June 8, 2026
Focus: Spread, Total Points, Q1, and Player Props
"""

import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import math

# Import the updated BasketballPredictor from models
from models.basketball_predictor import (
    BasketballPredictor,
    FIBAContext,
    FIBATeamMetrics,
    fiba_efficiency_gap,
    fiba_historical_gap,
    fiba_rest_travel_score,
    fiba_team_context_score,
    fiba_build_full_game,
    fiba_build_q1,
    fiba_score_to_prob,
    fiba_recommendation,
)


# ============================================================================
# GREEK DERBY ROSTER DATA (Basketball)
# ============================================================================

def get_greek_derby_basketball_rosters() -> Dict[str, List[Dict]]:
    """Get sample roster data for Olympiacos and Panathinaikos basketball teams"""
    
    olympiacos_roster = [
        {"name": "Sasha Vezenkov", "position": "PF", "stats": {
            "ppg": 14.5, "rpg": 6.8, "apg": 1.5, "topg": 1.2,
            "fg_pct": 0.48, "three_pt_pct": 0.42, "ft_pct": 0.85,
            "pts_line": 14.5, "reb_line": 6.5, "ast_line": 1.5
        }},
        {"name": "Nikola Milutinov", "position": "C", "stats": {
            "ppg": 10.2, "rpg": 7.5, "apg": 1.0, "bpg": 1.2,
            "fg_pct": 0.62, "three_pt_pct": 0.0, "ft_pct": 0.72,
            "pts_line": 10.5, "reb_line": 7.5, "ast_line": 1.0
        }},
        {"name": "Thomas Walkup", "position": "PG", "stats": {
            "ppg": 8.5, "rpg": 3.2, "apg": 5.8, "topg": 2.0,
            "fg_pct": 0.45, "three_pt_pct": 0.36, "ft_pct": 0.78,
            "pts_line": 8.5, "reb_line": 3.5, "ast_line": 5.5
        }},
        {"name": "Isaiah Canaan", "position": "SG", "stats": {
            "ppg": 12.8, "rpg": 2.5, "apg": 3.2, "topg": 1.5,
            "fg_pct": 0.42, "three_pt_pct": 0.39, "ft_pct": 0.88,
            "pts_line": 12.5, "reb_line": 2.5, "ast_line": 3.5
        }},
        {"name": "Alec Peters", "position": "SF", "stats": {
            "ppg": 9.5, "rpg": 4.2, "apg": 1.8, "topg": 1.0,
            "fg_pct": 0.46, "three_pt_pct": 0.40, "ft_pct": 0.82,
            "pts_line": 9.5, "reb_line": 4.5, "ast_line": 1.5
        }},
    ]
    
    panathinaikos_roster = [
        {"name": "Kostas Sloukas", "position": "PG", "stats": {
            "ppg": 11.5, "rpg": 2.8, "apg": 6.5, "topg": 2.2,
            "fg_pct": 0.44, "three_pt_pct": 0.38, "ft_pct": 0.86,
            "pts_line": 11.5, "reb_line": 2.5, "ast_line": 6.5
        }},
        {"name": "Mathias Lessort", "position": "C", "stats": {
            "ppg": 11.8, "rpg": 6.2, "apg": 1.2, "bpg": 0.8,
            "fg_pct": 0.58, "three_pt_pct": 0.0, "ft_pct": 0.68,
            "pts_line": 11.5, "reb_line": 6.5, "ast_line": 1.0
        }},
        {"name": "Kendrick Nunn", "position": "SG", "stats": {
            "ppg": 15.2, "rpg": 3.5, "apg": 4.2, "topg": 2.5,
            "fg_pct": 0.45, "three_pt_pct": 0.37, "ft_pct": 0.84,
            "pts_line": 15.5, "reb_line": 3.5, "ast_line": 4.5
        }},
        {"name": "Jerian Grant", "position": "PG", "stats": {
            "ppg": 9.2, "rpg": 2.5, "apg": 5.0, "topg": 1.8,
            "fg_pct": 0.43, "three_pt_pct": 0.35, "ft_pct": 0.80,
            "pts_line": 9.5, "reb_line": 2.5, "ast_line": 5.0
        }},
        {"name": "Luca Vildoza", "position": "SG", "stats": {
            "ppg": 8.8, "rpg": 2.2, "apg": 3.5, "topg": 1.2,
            "fg_pct": 0.44, "three_pt_pct": 0.40, "ft_pct": 0.85,
            "pts_line": 8.5, "reb_line": 2.5, "ast_line": 3.5
        }},
    ]
    
    return {
        "Olympiacos": olympiacos_roster,
        "Panathinaikos": panathinaikos_roster
    }


def generate_basketball_player_props(home_team: str, away_team: str, home_roster: List[Dict], away_roster: List[Dict]) -> Dict[str, Any]:
    """Generate basketball player props for the match"""
    
    props = {
        "sport": "basketball",
        "matchup": f"{home_team} vs {away_team}",
        "player_props": [],
        "top_recommendations": []
    }
    
    # Generate props for each player
    for player in home_roster + away_roster:
        team = home_team if player in home_roster else away_team
        stats = player.get("stats", {})
        
        # Points prop
        if "ppg" in stats:
            ppg = stats["ppg"]
            line = stats.get("pts_line", round(ppg * 2) / 2)  # Round to nearest 0.5
            
            # Derby adjustment - typically tighter defense
            adjustment = 0.95
            projection = ppg * adjustment
            
            edge = projection - line
            confidence = min(100, max(0, 50 + edge * 12))
            recommendation = "Over" if edge > 1.0 else "Under" if edge < -1.0 else "Pass"
            
            props["player_props"].append({
                "player_name": player["name"],
                "team": team,
                "position": player["position"],
                "prop_type": "Points",
                "line": line,
                "projection": round(projection, 1),
                "edge": round(edge, 2),
                "confidence": round(confidence, 1),
                "recommendation": recommendation,
            })
        
        # Rebounds prop (for bigs)
        if player["position"] in ["C", "PF", "SF"] and "rpg" in stats:
            rpg = stats["rpg"]
            line = stats.get("reb_line", round(rpg * 2) / 2)
            
            projection = rpg * 0.98  # Slight adjustment
            edge = projection - line
            confidence = min(100, max(0, 50 + edge * 15))
            recommendation = "Over" if edge > 0.5 else "Under" if edge < -0.5 else "Pass"
            
            props["player_props"].append({
                "player_name": player["name"],
                "team": team,
                "position": player["position"],
                "prop_type": "Rebounds",
                "line": line,
                "projection": round(projection, 1),
                "edge": round(edge, 2),
                "confidence": round(confidence, 1),
                "recommendation": recommendation,
            })
        
        # Assists prop (for guards)
        if player["position"] in ["PG", "SG"] and "apg" in stats:
            apg = stats["apg"]
            line = stats.get("ast_line", round(apg * 2) / 2)
            
            projection = apg * 1.02  # Slight boost for derby intensity
            edge = projection - line
            confidence = min(100, max(0, 50 + edge * 15))
            recommendation = "Over" if edge > 0.5 else "Under" if edge < -0.5 else "Pass"
            
            props["player_props"].append({
                "player_name": player["name"],
                "team": team,
                "position": player["position"],
                "prop_type": "Assists",
                "line": line,
                "projection": round(projection, 1),
                "edge": round(edge, 2),
                "confidence": round(confidence, 1),
                "recommendation": recommendation,
            })
    
    # Find top recommendations
    all_props = props["player_props"]
    top_props = sorted(all_props, key=lambda x: abs(x.get("edge", 0)), reverse=True)
    props["top_recommendations"] = top_props[:8]
    
    return props


def analyze_basketball_match_with_props(
    home_team, away_team, home_metrics, away_metrics, market_data, venue,
    home_roster, away_roster,
    date="2026-06-08", league="EuroLeague"
):
    """Analyze a basketball match with comprehensive betting analysis and player props"""
    
    print("=" * 80)
    print(f"GREEK BASKETBALL DERBY ANALYSIS: {home_team} vs {away_team}")
    print(f"{league} - {date}")
    print(f"Venue: {venue}")
    print("=" * 80)
    print()
    
    # Use the updated BasketballPredictor
    predictor = BasketballPredictor(league=league)
    
    # Create FIBA context
    ctx = FIBAContext(
        game_id=f"{home_team.replace(' ', '_')}_vs_{away_team.replace(' ', '_')}",
        date=date,
        league=league,
        home_team=home_team,
        away_team=away_team,
        market_line=market_data.get('spread', 0),
        current_line=market_data.get('current_line', market_data.get('spread', 0)),
        open_line=market_data.get('open_line', market_data.get('spread', 0)),
    )
    
    # 1. TEAM METRICS ANALYSIS
    print("1. TEAM METRICS ANALYSIS")
    print("-" * 40)
    
    print(f"   {home_team}:")
    print(f"      ORTG: {home_metrics.ortg_per_100:.1f} | DRTG: {home_metrics.drtg_per_100:.1f}")
    print(f"      Net Rating: {home_metrics.ortg_per_100 - home_metrics.drtg_per_100:+.1f}")
    print(f"      Pace: {home_metrics.pace_per_40:.1f} | 3PT%: {home_metrics.three_pt_pct:.1%}")
    print(f"      Rest: {home_metrics.rest_days} days | Rotation: {home_metrics.rotation_depth}")
    print()
    print(f"   {away_team}:")
    print(f"      ORTG: {away_metrics.ortg_per_100:.1f} | DRTG: {away_metrics.drtg_per_100:.1f}")
    print(f"      Net Rating: {away_metrics.ortg_per_100 - away_metrics.drtg_per_100:+.1f}")
    print(f"      Pace: {away_metrics.pace_per_40:.1f} | 3PT%: {away_metrics.three_pt_pct:.1%}")
    print(f"      Rest: {away_metrics.rest_days} days | Rotation: {away_metrics.rotation_depth}")
    print()
    
    # 2. EFFICIENCY GAP ANALYSIS
    print("2. EFFICIENCY GAP ANALYSIS")
    print("-" * 40)
    
    current_gap = fiba_efficiency_gap(home_metrics, away_metrics)
    baseline_gap = home_metrics.baseline_net_per_100 - away_metrics.baseline_net_per_100
    recent_gap = home_metrics.recent_net_per_100 - away_metrics.recent_net_per_100
    hist_gap = fiba_historical_gap(current_gap, baseline_gap, recent_gap)
    
    print(f"   Current Efficiency Gap: {current_gap:+.2f}")
    print(f"   Baseline Efficiency Gap: {baseline_gap:+.2f}")
    print(f"   Recent Efficiency Gap: {recent_gap:+.2f}")
    print(f"   Historical Gap (Blended): {hist_gap:+.2f}")
    print()
    
    # 3. REST & TRAVEL ANALYSIS
    print("3. REST & TRAVEL ANALYSIS")
    print("-" * 40)
    
    home_rest_score = fiba_rest_travel_score(
        home_metrics.rest_days, home_metrics.travel_km, 
        home_metrics.back_to_back, home_metrics.three_in_six
    )
    away_rest_score = fiba_rest_travel_score(
        away_metrics.rest_days, away_metrics.travel_km,
        away_metrics.back_to_back, away_metrics.three_in_six
    )
    rest_gap = home_rest_score - away_rest_score
    
    print(f"   {home_team} Rest Score: {home_rest_score:+.1f}")
    print(f"   {away_team} Rest Score: {away_rest_score:+.1f}")
    print(f"   Rest Advantage: {'Home' if rest_gap > 0 else 'Away'} ({abs(rest_gap):.1f})")
    print()
    
    # 4. TEAM CONTEXT ANALYSIS
    print("4. TEAM CONTEXT ANALYSIS")
    print("-" * 40)
    
    home_ctx_score = fiba_team_context_score(
        home_metrics.rotation_depth, home_metrics.injury_status,
        home_metrics.coach_stability, home_metrics.motivation
    )
    away_ctx_score = fiba_team_context_score(
        away_metrics.rotation_depth, away_metrics.injury_status,
        away_metrics.coach_stability, away_metrics.motivation
    )
    ctx_gap = home_ctx_score - away_ctx_score
    
    print(f"   {home_team} Context Score: {home_ctx_score:+.1f}")
    print(f"      Injury Status: {home_metrics.injury_status}")
    print(f"      Coach Stability: {home_metrics.coach_stability}")
    print(f"      Motivation: {home_metrics.motivation}")
    print()
    print(f"   {away_team} Context Score: {away_ctx_score:+.1f}")
    print(f"      Injury Status: {away_metrics.injury_status}")
    print(f"      Coach Stability: {away_metrics.coach_stability}")
    print(f"      Motivation: {away_metrics.motivation}")
    print()
    
    # 5. FULL GAME PREDICTION
    print("5. FULL GAME PREDICTION")
    print("-" * 40)
    
    full_game_result = fiba_build_full_game(home_metrics, away_metrics, ctx)
    
    print(f"   Projected Score: {home_team} {full_game_result['projected_home_score']:.1f} - {away_team} {full_game_result['projected_away_score']:.1f}")
    print(f"   Projected Total: {full_game_result['projected_total']:.1f}")
    print(f"   Model Edge: {full_game_result['model_edge']:+.2f}")
    print(f"   Win Probability: {full_game_result['probability']:.1%}")
    print(f"   Lean: {full_game_result['lean']}")
    print()
    
    # 6. Q1 PREDICTION
    print("6. FIRST QUARTER PREDICTION")
    print("-" * 40)
    
    home_q1_metrics = {
        'pts_for': home_metrics.ortg_per_100 * 0.2,
        'pts_against': home_metrics.drtg_per_100 * 0.2,
        'home_edge': 2.5,  # Home court advantage in derby
        'coach_fast_start': home_metrics.motivation,
        'injury_status': home_metrics.injury_status,
        'starting_five_net': home_ctx_score,
    }
    away_q1_metrics = {
        'pts_for': away_metrics.ortg_per_100 * 0.2,
        'pts_against': away_metrics.drtg_per_100 * 0.2,
        'home_edge': 0.0,
        'coach_fast_start': away_metrics.motivation,
        'injury_status': away_metrics.injury_status,
        'starting_five_net': away_ctx_score,
    }
    
    q1_result = fiba_build_q1(home_metrics, away_metrics, home_q1_metrics, away_q1_metrics, ctx)
    
    print(f"   Projected Q1 Score: {home_team} {q1_result['projected_q1_home']:.1f} - {away_team} {q1_result['projected_q1_away']:.1f}")
    print(f"   Projected Q1 Total: {q1_result['projected_q1_total']:.1f}")
    print(f"   Q1 Lean: {q1_result['lean']}")
    print()
    
    # 7. MARKET ANALYSIS
    print("7. MARKET ANALYSIS")
    print("-" * 40)
    
    spread = market_data.get('spread', 0)
    total_line = market_data.get('total', 155.5)
    
    model_spread = full_game_result['projected_home_score'] - full_game_result['projected_away_score']
    spread_edge = model_spread - spread
    spread_confidence = min(100, max(0, 50 + spread_edge * 8))
    spread_rec = "BET" if spread_confidence > 60 else "PASS"
    spread_lean = home_team if spread_edge > 0 else away_team
    
    total_edge = full_game_result['projected_total'] - total_line
    total_confidence = min(100, max(0, 50 + total_edge * 6))
    total_rec = "BET" if total_confidence > 60 else "PASS"
    total_lean = "OVER" if total_edge > 0 else "UNDER"
    
    print(f"   Spread: {home_team} {spread}")
    print(f"   Model Spread: {model_spread:+.1f}")
    print(f"   Spread Edge: {spread_edge:+.1f}")
    print(f"   Spread Confidence: {spread_confidence:.1f}%")
    print(f"   Spread Recommendation: {spread_rec} {spread_lean}")
    print()
    print(f"   Total: {total_line}")
    print(f"   Model Total: {full_game_result['projected_total']:.1f}")
    print(f"   Total Edge: {total_edge:+.1f}")
    print(f"   Total Confidence: {total_confidence:.1f}%")
    print(f"   Total Recommendation: {total_rec} {total_lean}")
    print()
    
    # 8. PLAYER PROPS ANALYSIS
    print("=" * 80)
    print("PLAYER PROPS ANALYSIS")
    print("=" * 80)
    print()
    
    player_props = generate_basketball_player_props(home_team, away_team, home_roster, away_roster)
    
    # Display top recommendations
    print("   === TOP PLAYER PROP RECOMMENDATIONS ===")
    print()
    
    for i, prop in enumerate(player_props["top_recommendations"][:6], 1):
        print(f"   {i}. {prop['player_name']} ({prop['team']}) - {prop['prop_type']}")
        print(f"      Line: {prop['line']}, Projection: {prop['projection']}")
        print(f"      Edge: {prop['edge']:+.2f}, Confidence: {prop['confidence']:.1f}%")
        print(f"      Recommendation: {prop['recommendation']}")
        print()
    
    # Display by category
    print("   === POINTS PROPS ===")
    pts_props = [p for p in player_props["player_props"] if p["prop_type"] == "Points"]
    for prop in sorted(pts_props, key=lambda x: abs(x["edge"]), reverse=True)[:5]:
        print(f"   {prop['player_name']} ({prop['team']}): O/U {prop['line']} -> {prop['recommendation']} ({prop['confidence']:.0f}% conf)")
    print()
    
    print("   === REBOUNDS PROPS ===")
    reb_props = [p for p in player_props["player_props"] if p["prop_type"] == "Rebounds"]
    for prop in sorted(reb_props, key=lambda x: abs(x["edge"]), reverse=True)[:5]:
        print(f"   {prop['player_name']} ({prop['team']}): O/U {prop['line']} -> {prop['recommendation']} ({prop['confidence']:.0f}% conf)")
    print()
    
    print("   === ASSISTS PROPS ===")
    ast_props = [p for p in player_props["player_props"] if p["prop_type"] == "Assists"]
    for prop in sorted(ast_props, key=lambda x: abs(x["edge"]), reverse=True)[:5]:
        print(f"   {prop['player_name']} ({prop['team']}): O/U {prop['line']} -> {prop['recommendation']} ({prop['confidence']:.0f}% conf)")
    print()
    
    # FINAL SUMMARY
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Match: {home_team} vs {away_team}")
    print(f"   Projected Score: {home_team} {full_game_result['projected_home_score']:.0f} - {away_team} {full_game_result['projected_away_score']:.0f}")
    print(f"   Projected Total: {full_game_result['projected_total']:.1f}")
    print()
    print("   === BETTING RECOMMENDATIONS ===")
    print(f"   Spread ({spread}): {spread_rec} {spread_lean} (Confidence: {spread_confidence:.1f}%)")
    print(f"   Total ({total_line}): {total_rec} {total_lean} (Confidence: {total_confidence:.1f}%)")
    print(f"   Q1: {q1_result['lean']}")
    print()
    print("   === TOP PLAYER PROPS ===")
    for prop in player_props["top_recommendations"][:3]:
        print(f"   {prop['player_name']} - {prop['prop_type']}: {prop['recommendation']} (Conf: {prop['confidence']:.0f}%)")
    print()
    
    # Build results dictionary
    results = {
        "game_info": {
            "home_team": home_team,
            "away_team": away_team,
            "league": league,
            "date": date,
            "venue": venue,
            "match_type": "Greek Basketball Derby"
        },
        "team_metrics": {
            "home": {
                "ortg_per_100": home_metrics.ortg_per_100,
                "drtg_per_100": home_metrics.drtg_per_100,
                "net_rating": home_metrics.ortg_per_100 - home_metrics.drtg_per_100,
                "pace": home_metrics.pace_per_40,
                "three_pt_pct": home_metrics.three_pt_pct,
                "rest_days": home_metrics.rest_days,
                "rotation_depth": home_metrics.rotation_depth,
                "injury_status": home_metrics.injury_status,
            },
            "away": {
                "ortg_per_100": away_metrics.ortg_per_100,
                "drtg_per_100": away_metrics.drtg_per_100,
                "net_rating": away_metrics.ortg_per_100 - away_metrics.drtg_per_100,
                "pace": away_metrics.pace_per_40,
                "three_pt_pct": away_metrics.three_pt_pct,
                "rest_days": away_metrics.rest_days,
                "rotation_depth": away_metrics.rotation_depth,
                "injury_status": away_metrics.injury_status,
            }
        },
        "efficiency_gaps": {
            "current": round(current_gap, 2),
            "baseline": round(baseline_gap, 2),
            "recent": round(recent_gap, 2),
            "historical": round(hist_gap, 2),
            "rest": round(rest_gap, 2),
            "context": round(ctx_gap, 2),
        },
        "projections": {
            "home_score": full_game_result['projected_home_score'],
            "away_score": full_game_result['projected_away_score'],
            "total": full_game_result['projected_total'],
            "home_win_prob": full_game_result['probability'],
        },
        "q1_projection": {
            "home_score": q1_result['projected_q1_home'],
            "away_score": q1_result['projected_q1_away'],
            "total": q1_result['projected_q1_total'],
            "lean": q1_result['lean'],
        },
        "market_analysis": {
            "spread": {
                "line": spread,
                "model_spread": round(model_spread, 1),
                "edge": round(spread_edge, 1),
                "confidence": round(spread_confidence, 1),
                "recommendation": spread_rec,
                "lean": spread_lean,
            },
            "total": {
                "line": total_line,
                "model_total": full_game_result['projected_total'],
                "edge": round(total_edge, 1),
                "confidence": round(total_confidence, 1),
                "recommendation": total_rec,
                "lean": total_lean,
            },
        },
        "player_props": player_props,
        "recommendations": {
            "spread": {"recommendation": spread_rec, "lean": spread_lean, "confidence": round(spread_confidence, 1)},
            "total": {"recommendation": total_rec, "lean": total_lean, "confidence": round(total_confidence, 1)},
            "q1": q1_result['lean'],
        },
        "model_info": {
            "type": "FIBA/European Basketball Model",
            "league": league,
            "notes": "40-minute game format, per-100 possession metrics, tournament fatigue tracking",
        },
        "timestamp": datetime.now().isoformat()
    }
    
    return results


def run_olympiacos_panathinaikos_basketball_analysis():
    """Run basketball analysis for Olympiacos vs Panathinaikos Greek Derby"""
    
    print("\n" + "=" * 80)
    print("EUROLEAGUE GREEK DERBY: OLYMPIACOS vs PANATHINAIKOS")
    print("June 8, 2026")
    print("=" * 80 + "\n")
    
    # Olympiacos (Home) - Strong home team with EuroLeague experience
    home_metrics = FIBATeamMetrics(
        ortg_per_100=112.5,
        drtg_per_100=105.2,
        baseline_net_per_100=7.5,
        recent_net_per_100=8.2,
        pace_per_40=71.0,
        rest_days=3,
        travel_km=200.0,
        back_to_back=False,
        three_in_six=False,
        split_edge=3.5,
        rotation_depth=10,
        injury_status='green',
        coach_stability='green',
        motivation='green',
        three_pt_pct=0.39,
        orb_pct=0.32,
    )
    
    # Panathinaikos (Away) - Strong away team but with travel fatigue
    away_metrics = FIBATeamMetrics(
        ortg_per_100=110.8,
        drtg_per_100=106.5,
        baseline_net_per_100=4.5,
        recent_net_per_100=3.8,
        pace_per_40=69.5,
        rest_days=1,
        travel_km=800.0,
        back_to_back=True,
        three_in_six=True,
        split_edge=1.0,
        rotation_depth=9,
        injury_status='yellow',
        coach_stability='green',
        motivation='green',
        three_pt_pct=0.37,
        orb_pct=0.28,
    )
    
    market_data = {
        'spread': -3.5,  # Olympiacos favored by 3.5
        'current_line': -4.0,
        'open_line': -3.0,
        'total': 155.5,
    }
    
    # Get roster data
    rosters = get_greek_derby_basketball_rosters()
    home_roster = rosters["Olympiacos"]
    away_roster = rosters["Panathinaikos"]
    
    result = analyze_basketball_match_with_props(
        home_team="Olympiacos",
        away_team="Panathinaikos",
        home_metrics=home_metrics,
        away_metrics=away_metrics,
        market_data=market_data,
        home_roster=home_roster,
        away_roster=away_roster,
        venue="Peace and Friendship Stadium, Piraeus",
        date="2026-06-08",
        league="EuroLeague"
    )
    
    return result


if __name__ == "__main__":
    result = run_olympiacos_panathinaikos_basketball_analysis()
    
    # Save results
    output_dir = Path("output/basketball")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "olympiacos_vs_panathinaikos_basketball_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")