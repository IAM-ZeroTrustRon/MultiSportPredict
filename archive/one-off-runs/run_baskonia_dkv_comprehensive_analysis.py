#!/usr/bin/env python
"""
COMPREHENSIVE ANALYSIS - BASKONIA VITORIA vs DKV JOVENTUT
Spanish ACB League - June 7, 2026

This script runs the match through the updated MultiSportModel with:
- Full Game Analysis (Spread, Total, Moneyline)
- First Quarter Analysis (Spread, Total)
- Player Props Analysis (Points, Rebounds, Assists, etc.)
"""

import json
from pathlib import Path
from datetime import datetime
from MultiSportModel import (
    GameContext,
    TeamMetrics,
    PlayerProp,
    eu_build_full_game,
    project_basketball_q1,
    eu_build_prop,
)
from core import confidence_score, bet_recommendation


def run_comprehensive_analysis():
    """Run comprehensive analysis for Baskonia Vitoria vs DKV Joventut"""
    
    print("=" * 100)
    print("COMPREHENSIVE ANALYSIS: BASKONIA VITORIA vs DKV JOVENTUT")
    print("Spanish ACB League - June 7, 2026")
    print("Venue: Fernando Buesa Arena, Vitoria-Gasteiz")
    print("=" * 100)
    print()
    
    # ========================================================================
    # TEAM DATA SETUP
    # ========================================================================
    
    # Baskonia Vitoria (Home)
    home_data = {
        'ortg': 112.0,
        'drtg': 108.0,
        'baseline_net': 4.0,
        'recent_net': 3.5,
        'pace': 72.0,
        'rest_days': 2,
        'travel_km': 0,
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': 4.0,
        'rotation_depth': 9,
        'injury_status': 'green',
        'coach_stability': 'green',
        'motivation': 'green',
    }
    
    # DKV Joventut (Away)
    away_data = {
        'ortg': 110.0,
        'drtg': 109.0,
        'baseline_net': 1.0,
        'recent_net': 1.5,
        'pace': 71.0,
        'rest_days': 2,
        'travel_km': 80,
        'back_to_back': False,
        'three_in_six': False,
        'split_edge': 1.5,
        'rotation_depth': 8,
        'injury_status': 'green',
        'coach_stability': 'green',
        'motivation': 'green',
    }
    
    # Market data (Updated with current lines)
    market_data = {
        'open_line': -5.5,
        'current_line': -6.5,
        'spread': -6.5,
        'total': 186.0,
        'moneyline_home': -250,
        'moneyline_away': +200,
    }
    
    # ========================================================================
    # BUILD GAME CONTEXT AND TEAM METRICS
    # ========================================================================
    
    ctx = GameContext(
        game_id="Baskonia_Vitoria_vs_DKV_Joventut",
        date="2026-06-07",
        league="Spain_ACB",
        record_type="full_game",
        home_team="Baskonia Vitoria",
        away_team="DKV Joventut",
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
    
    # ========================================================================
    # FULL GAME ANALYSIS
    # ========================================================================
    
    print("=" * 50)
    print("FULL GAME ANALYSIS")
    print("=" * 50)
    print()
    
    fg_result = eu_build_full_game(home_tm, away_tm, ctx)
    
    projected_home = fg_result['projected_home_score']
    projected_away = fg_result['projected_away_score']
    projected_total = fg_result['projected_total']
    projected_spread = projected_home - projected_away
    
    print(f"   Projected Score: Baskonia Vitoria {projected_home:.1f} - DKV Joventut {projected_away:.1f}")
    print(f"   Projected Total: {projected_total:.1f}")
    print(f"   Projected Spread: {projected_spread:+.1f}")
    print(f"   Win Probability: Baskonia Vitoria {fg_result['probability']:.1%}")
    print(f"   Model Edge: {fg_result['model_edge']:+.2f}")
    print(f"   Lean: {fg_result['lean']}")
    print()
    
    # Spread Analysis
    spread_edge = projected_spread - market_data['spread']
    spread_confidence = confidence_score(spread_edge, volatility=0.35, market_alignment=0.0)
    spread_rec = bet_recommendation(spread_confidence)
    
    print(f"   SPREAD ({market_data['spread']}): Edge {spread_edge:+.2f}, Confidence {spread_confidence:.1f}%, Rec: {spread_rec}")
    
    # Total Analysis
    total_edge = projected_total - market_data['total']
    total_confidence = confidence_score(total_edge, volatility=0.38, market_alignment=0.0)
    total_rec = bet_recommendation(total_confidence)
    
    print(f"   TOTAL ({market_data['total']}): Edge {total_edge:+.2f}, Confidence {total_confidence:.1f}%, Rec: {total_rec}")
    
    # Moneyline Analysis
    implied_prob_home = market_data['moneyline_home'] / (market_data['moneyline_home'] - 100) if market_data['moneyline_home'] < 0 else 100 / (market_data['moneyline_home'] + 100)
    ml_edge = fg_result['probability'] - implied_prob_home
    ml_confidence = confidence_score(ml_edge * 100, volatility=0.40, market_alignment=0.0)
    ml_rec = bet_recommendation(ml_confidence)
    
    print(f"   MONEYLINE: Edge {ml_edge:+.2%}, Confidence {ml_confidence:.1f}%, Rec: {ml_rec}")
    print()
    
    # ========================================================================
    # FIRST QUARTER ANALYSIS
    # ========================================================================
    
    print("=" * 50)
    print("FIRST QUARTER ANALYSIS")
    print("=" * 50)
    print()
    
    q1_result = project_basketball_q1(home_data, away_data)
    
    q1_home = q1_result['home_q1_points']
    q1_away = q1_result['away_q1_points']
    q1_spread = q1_result['q1_spread']
    q1_total = q1_result['q1_total']
    
    print(f"   Q1 Projected: Baskonia Vitoria {q1_home:.1f} - DKV Joventut {q1_away:.1f}")
    print(f"   Q1 Spread: {q1_spread:+.1f}")
    print(f"   Q1 Total: {q1_total:.1f}")
    print(f"   Q1 Home Win Probability: {q1_result['q1_prob_home_win']:.1%}")
    print()
    
    # Q1 Spread Analysis (Market Q1 spread typically ~ FG spread / 4)
    q1_market_spread = market_data['spread'] / 4
    q1_spread_edge = q1_spread - q1_market_spread
    q1_spread_confidence = confidence_score(q1_spread_edge, volatility=0.42, market_alignment=0.0)
    q1_spread_rec = bet_recommendation(q1_spread_confidence)
    
    print(f"   Q1 SPREAD ({q1_market_spread:+.1f}): Edge {q1_spread_edge:+.2f}, Confidence {q1_spread_confidence:.1f}%, Rec: {q1_spread_rec}")
    
    # Q1 Total Analysis (Market Q1 total typically ~ FG total / 4)
    q1_market_total = market_data['total'] / 4
    q1_total_edge = q1_total - q1_market_total
    q1_total_confidence = confidence_score(q1_total_edge, volatility=0.45, market_alignment=0.0)
    q1_total_rec = bet_recommendation(q1_total_confidence)
    
    print(f"   Q1 TOTAL ({q1_market_total:.1f}): Edge {q1_total_edge:+.2f}, Confidence {q1_total_confidence:.1f}%, Rec: {q1_total_rec}")
    print()
    
    # ========================================================================
    # PLAYER PROPS ANALYSIS
    # ========================================================================
    
    print("=" * 50)
    print("PLAYER PROPS ANALYSIS")
    print("=" * 50)
    print()
    
    # Define key players for both teams with their stats
    players = [
        # Baskonia Vitoria players
        {
            "player_name": "Markus Howard",
            "team": "Baskonia Vitoria",
            "opponent": "DKV Joventut",
            "role": "starter",
            "player_avg": 16.5,
            "minutes_proj": 30.0,
            "usage_rate": 28.0,
            "injury_boost": "green",
            "blowout_risk": "green",
            "props": [
                {"prop_type": "Points", "prop_line": 16.5},
                {"prop_type": "Assists", "prop_line": 3.5},
                {"prop_type": "Rebounds", "prop_line": 2.5},
                {"prop_type": "Threes", "prop_line": 2.5},
            ]
        },
        {
            "player_name": "Chima Moneke",
            "team": "Baskonia Vitoria",
            "opponent": "DKV Joventut",
            "role": "starter",
            "player_avg": 12.8,
            "minutes_proj": 28.0,
            "usage_rate": 22.0,
            "injury_boost": "green",
            "blowout_risk": "green",
            "props": [
                {"prop_type": "Points", "prop_line": 12.5},
                {"prop_type": "Rebounds", "prop_line": 5.5},
                {"prop_type": "Assists", "prop_line": 2.5},
            ]
        },
        {
            "player_name": "Darius Thompson",
            "team": "Baskonia Vitoria",
            "opponent": "DKV Joventut",
            "role": "starter",
            "player_avg": 10.2,
            "minutes_proj": 26.0,
            "usage_rate": 18.0,
            "injury_boost": "green",
            "blowout_risk": "green",
            "props": [
                {"prop_type": "Points", "prop_line": 10.5},
                {"prop_type": "Assists", "prop_line": 4.5},
                {"prop_type": "Rebounds", "prop_line": 3.5},
            ]
        },
        # DKV Joventut players
        {
            "player_name": "Nikola Radicevic",
            "team": "DKV Joventut",
            "opponent": "Baskonia Vitoria",
            "role": "starter",
            "player_avg": 14.2,
            "minutes_proj": 29.0,
            "usage_rate": 25.0,
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "props": [
                {"prop_type": "Points", "prop_line": 14.5},
                {"prop_type": "Assists", "prop_line": 4.5},
                {"prop_type": "Rebounds", "prop_line": 3.5},
            ]
        },
        {
            "player_name": "Ante Tomic",
            "team": "DKV Joventut",
            "opponent": "Baskonia Vitoria",
            "role": "starter",
            "player_avg": 11.5,
            "minutes_proj": 25.0,
            "usage_rate": 20.0,
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "props": [
                {"prop_type": "Points", "prop_line": 11.5},
                {"prop_type": "Rebounds", "prop_line": 6.5},
                {"prop_type": "Assists", "prop_line": 2.5},
            ]
        },
        {
            "player_name": "Pau Ribas",
            "team": "DKV Joventut",
            "opponent": "Baskonia Vitoria",
            "role": "starter",
            "player_avg": 9.8,
            "minutes_proj": 24.0,
            "usage_rate": 16.0,
            "injury_boost": "green",
            "blowout_risk": "yellow",
            "props": [
                {"prop_type": "Points", "prop_line": 9.5},
                {"prop_type": "Assists", "prop_line": 3.5},
                {"prop_type": "Rebounds", "prop_line": 2.5},
            ]
        },
    ]
    
    prop_results = []
    
    for player in players:
        print(f"--- {player['player_name']} ({player['team']}) ---")
        for prop in player['props']:
            player_prop = PlayerProp(
                player_name=player['player_name'],
                team=player['team'],
                opponent=player['opponent'],
                prop_type=prop['prop_type'],
                prop_line=prop['prop_line'],
                player_avg=player['player_avg'],
                minutes_proj=player['minutes_proj'],
                usage_rate=player['usage_rate'],
                game_pace=(home_data['pace'] + away_data['pace']) / 2,
                opp_def_rating=away_data['drtg'] if player['team'] == 'Baskonia Vitoria' else home_data['drtg'],
                opp_position_def_rating=away_data['drtg'] if player['team'] == 'Baskonia Vitoria' else home_data['drtg'],
                injury_boost=player['injury_boost'],
                blowout_risk=player['blowout_risk'],
                role=player['role'],
                open_prop_line=prop['prop_line'] - 0.5,
                current_prop_line=prop['prop_line'],
            )
            
            prop_result = eu_build_prop(player_prop, home_tm if player['team'] == 'Baskonia Vitoria' else away_tm, 
                                        away_tm if player['team'] == 'Baskonia Vitoria' else home_tm,
                                        (home_data['pace'] + away_data['pace']) / 2)
            
            # Calculate confidence
            prop_edge = prop_result['edge']
            prop_confidence = confidence_score(prop_edge, volatility=0.45, market_alignment=0.0)
            
            if prop_edge > 1.0:
                prop_lean = f"Over {prop['prop_line']}"
            elif prop_edge < -1.0:
                prop_lean = f"Under {prop['prop_line']}"
            else:
                prop_lean = "Pass"
            
            print(f"   {prop['prop_type']}: Line {prop['prop_line']}, Projection {prop_result['model_projection']:.1f}, Edge {prop_result['edge']:+.2f}, Rec: {prop_lean}")
            
            prop_results.append({
                "player": player['player_name'],
                "team": player['team'],
                "prop_type": prop['prop_type'],
                "line": prop['prop_line'],
                "projection": prop_result['model_projection'],
                "edge": prop_result['edge'],
                "recommendation": prop_lean,
                "confidence": round(prop_confidence, 1),
            })
        
        print()
    
    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    
    print("=" * 100)
    print("FINAL COMPREHENSIVE SUMMARY")
    print("=" * 100)
    print()
    
    print("   FULL GAME:")
    print(f"   Projected Score: Baskonia Vitoria {projected_home:.1f} - DKV Joventut {projected_away:.1f}")
    print(f"   Spread ({market_data['spread']}): {spread_rec} (Confidence: {spread_confidence:.1f}%)")
    print(f"   Total ({market_data['total']}): {total_rec} (Confidence: {total_confidence:.1f}%)")
    print(f"   Moneyline: {ml_rec} (Confidence: {ml_confidence:.1f}%)")
    print()
    
    print("   FIRST QUARTER:")
    print(f"   Q1 Spread ({q1_market_spread:+.1f}): {q1_spread_rec} (Confidence: {q1_spread_confidence:.1f}%)")
    print(f"   Q1 Total ({q1_market_total:.1f}): {q1_total_rec} (Confidence: {q1_total_confidence:.1f}%)")
    print()
    
    print("   TOP PLAYER PROPS:")
    # Sort props by absolute edge
    top_props = sorted(prop_results, key=lambda x: abs(x['edge']), reverse=True)[:5]
    for prop in top_props:
        print(f"   {prop['player']} {prop['prop_type']}: {prop['recommendation']} (Edge: {prop['edge']:+.2f})")
    print()
    
    # ========================================================================
    # BUILD AND SAVE RESULTS
    # ========================================================================
    
    results = {
        "game_info": {
            "home_team": "Baskonia Vitoria",
            "away_team": "DKV Joventut",
            "league": "Spain_ACB",
            "date": "2026-06-07",
            "venue": "Fernando Buesa Arena, Vitoria-Gasteiz",
        },
        "team_metrics": {
            "home": home_data,
            "away": away_data,
        },
        "market_data": market_data,
        "full_game": {
            "projected_home_score": round(projected_home, 1),
            "projected_away_score": round(projected_away, 1),
            "projected_total": round(projected_total, 1),
            "projected_spread": round(projected_spread, 1),
            "win_probability": fg_result['probability'],
            "model_edge": fg_result['model_edge'],
            "lean": fg_result['lean'],
            "recommendations": {
                "spread": {
                    "line": market_data['spread'],
                    "edge": round(spread_edge, 2),
                    "confidence": round(spread_confidence, 1),
                    "recommendation": spread_rec,
                },
                "total": {
                    "line": market_data['total'],
                    "edge": round(total_edge, 2),
                    "confidence": round(total_confidence, 1),
                    "recommendation": total_rec,
                },
                "moneyline": {
                    "edge": round(ml_edge, 4),
                    "confidence": round(ml_confidence, 1),
                    "recommendation": ml_rec,
                },
            }
        },
        "first_quarter": {
            "projected_home": round(q1_home, 1),
            "projected_away": round(q1_away, 1),
            "projected_total": round(q1_total, 1),
            "projected_spread": round(q1_spread, 1),
            "win_probability": q1_result['q1_prob_home_win'],
            "recommendations": {
                "spread": {
                    "line": round(q1_market_spread, 1),
                    "edge": round(q1_spread_edge, 2),
                    "confidence": round(q1_spread_confidence, 1),
                    "recommendation": q1_spread_rec,
                },
                "total": {
                    "line": round(q1_market_total, 1),
                    "edge": round(q1_total_edge, 2),
                    "confidence": round(q1_total_confidence, 1),
                    "recommendation": q1_total_rec,
                },
            }
        },
        "player_props": prop_results,
        "timestamp": datetime.now().isoformat(),
    }
    
    # Save results
    output_dir = Path("output/basketball")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / "baskonia_vs_dkv_comprehensive_analysis.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Detailed results saved to: {output_path}")
    print()
    
    return results


if __name__ == "__main__":
    results = run_comprehensive_analysis()