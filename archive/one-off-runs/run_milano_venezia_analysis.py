#!/usr/bin/env python
"""
Comprehensive Analysis: Olimpia Milano vs Reyer Venezia
EuroLeague Matchup
Focus: Totals, Sides, 1Q, 1H, Full Game, and Player Props
"""

import sys
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from models.basketball_predictor import BasketballPredictor, FIBATeamMetrics, fiba_build_full_game, fiba_build_q1, FIBAContext
from models.props_engine import PropsEngine, generate_player_props
from core.confidence_engine import confidence_score, bet_recommendation
from core.utils import sigmoid, clamp

# If confidence_engine is not available, provide fallbacks
try:
    from core.confidence_engine import confidence_score, bet_recommendation
except ImportError:
    def confidence_score(edge, volatility=0.5):
        return min(100, max(0, 50 + edge * 10 / volatility))
    def bet_recommendation(conf, market="default"):
        return "BET" if conf > 60 else "PASS"


# ============================================================================
# TEAM METRICS (Based on analysis narrative)
# ============================================================================

def get_milano_metrics() -> Dict:
    """
    Olimpia Milano metrics
    - Methodical, defensively elite
    - Depth Delta advantage (10-11 rotation players)
    - Pace suppression specialists
    - Half-court execution
    """
    return {
        "team": "Olimpia Milano",
        "ortg_per_100": 115.2,
        "drtg_per_100": 101.8,
        "baseline_net_per_100": 6.5,
        "recent_net_per_100": 8.2,
        "pace_per_40": 68.5,
        "rest_days": 3,
        "travel_km": 400.0,
        "back_to_back": False,
        "three_in_six": False,
        "split_edge": 2.5,
        "rotation_depth": 11,
        "injury_status": "green",
        "coach_stability": "green",
        "motivation": "green",
        "three_pt_pct": 0.365,
        "orb_pct": 0.28,
    }


def get_venezia_metrics() -> Dict:
    """
    Reyer Venezia metrics
    - High variance, 3-point dependent
    - Home adrenaline advantage
    - Fatigue risk (heavy usage ball handlers)
    - Worse perimeter defense
    """
    return {
        "team": "Reyer Venezia",
        "ortg_per_100": 108.5,
        "drtg_per_100": 106.2,
        "baseline_net_per_100": 1.5,
        "recent_net_per_100": 2.8,
        "pace_per_40": 74.0,
        "rest_days": 2,
        "travel_km": 50.0,
        "back_to_back": False,
        "three_in_six": False,
        "split_edge": 3.0,
        "rotation_depth": 8,
        "injury_status": "yellow",
        "coach_stability": "green",
        "motivation": "green",
        "three_pt_pct": 0.352,
        "orb_pct": 0.24,
    }


# ============================================================================
# PLAYER ROSTERS (Sample data)
# ============================================================================

def get_milano_roster() -> List[Dict]:
    """Olimpia Milano key players"""
    return [
        {"name": "Nicolo Melli", "position": "PF", "ppg": 9.5, "rpg": 5.2, "apg": 1.8, "pts_line": 9.5, "reb_line": 5.0, "ast_line": 1.5},
        {"name": "Shavon Shields", "position": "SF", "ppg": 11.2, "rpg": 3.8, "apg": 1.5, "pts_line": 11.0, "reb_line": 3.5, "ast_line": 1.5},
        {"name": "Kevin Punter", "position": "SG", "ppg": 14.8, "rpg": 2.2, "apg": 2.0, "pts_line": 14.5, "reb_line": 2.5, "ast_line": 2.0},
        {"name": "Sergio Rodriguez", "position": "PG", "ppg": 8.5, "rpg": 2.0, "apg": 5.5, "pts_line": 8.5, "reb_line": 2.0, "ast_line": 5.5},
        {"name": "Cleveland Melvin", "position": "C", "ppg": 10.2, "rpg": 4.5, "apg": 0.8, "pts_line": 10.0, "reb_line": 4.5, "ast_line": 1.0},
    ]


def get_venezia_roster() -> List[Dict]:
    """Reyer Venezia key players"""
    return [
        {"name": "Michele Vitali", "position": "SG", "ppg": 12.5, "rpg": 2.8, "apg": 2.2, "pts_line": 12.5, "reb_line": 2.5, "ast_line": 2.0},
        {"name": "Jordan Theodore", "position": "PG", "ppg": 13.0, "rpg": 3.0, "apg": 5.8, "pts_line": 13.0, "reb_line": 3.0, "ast_line": 5.5},
        {"name": "Austin Daye", "position": "PF", "ppg": 11.5, "rpg": 4.2, "apg": 1.5, "pts_line": 11.5, "reb_line": 4.0, "ast_line": 1.5},
        {"name": "Stefano Tonut", "position": "SG", "ppg": 10.8, "rpg": 2.5, "apg": 2.5, "pts_line": 10.5, "reb_line": 2.5, "ast_line": 2.5},
        {"name": "Isacco Casarin", "position": "SF", "ppg": 6.5, "rpg": 2.2, "apg": 1.2, "pts_line": 6.5, "reb_line": 2.0, "ast_line": 1.0},
    ]


# ============================================================================
# FIRST HALF PROJECTION
# ============================================================================

def build_first_half_projection(home_metrics: Dict, away_metrics: Dict, ctx: FIBAContext,
                                 q1_result: Dict) -> Dict[str, Any]:
    """
    Build first half projection.
    
    First half in FIBA/EuroLeague = Q1 + Q2
    Typical Q1+Q2 total ~ 38-44 points (lower scoring than NBA)
    """
    from dataclasses import asdict
    # Accept FIBATeamMetrics by converting to dict if needed
    if hasattr(home_metrics, '__dataclass_fields__'):
        home_metrics = asdict(home_metrics)
    if hasattr(away_metrics, '__dataclass_fields__'):
        away_metrics = asdict(away_metrics)
    
    # Get Q1 projections
    q1_home = q1_result.get("projected_q1_home", 19.0)
    q1_away = q1_result.get("projected_q1_away", 17.0)
    
    # Q2 projection models
    # Q2 tends to be slightly higher scoring than Q1 due to rotations settling
    home_q2_base = home_metrics['ortg_per_100'] / 100 * 20  # Approx points per 20 poss
    away_q2_base = away_metrics['ortg_per_100'] / 100 * 20
    
    # Adjust for pace (Venezia higher pace, but Milano controls tempo)
    home_q2_mod = home_q2_base * (1.0 + (home_metrics['pace_per_40'] - 70) * 0.005)
    away_q2_mod = away_q2_base * (1.0 + (away_metrics['pace_per_40'] - 70) * 0.005)
    
    # Defensive adjustment
    home_q2_mod *= (115 / max(away_metrics['drtg_per_100'], 90))
    away_q2_mod *= (115 / max(home_metrics['drtg_per_100'], 90))
    
    # Home advantage for Q2
    home_q2_mod *= 1.03
    away_q2_mod *= 0.97
    
    home_q2 = round(home_q2_mod, 1)
    away_q2 = round(away_q2_mod, 1)
    
    first_half_home = round(q1_home + home_q2, 1)
    first_half_away = round(q1_away + away_q2, 1)
    first_half_total = round(first_half_home + first_half_away, 1)
    first_half_spread = round(first_half_home - first_half_away, 1)
    
    # First half probability using sigmoid
    # Spread of 4+ = strong home lean, 2-4 = moderate
    first_half_score = first_half_spread * 0.65
    first_half_prob = clamp(sigmoid(first_half_score / 3.5))
    
    # Recommendation
    edge = first_half_spread
    conf = confidence_score(abs(edge) * 10, volatility=0.55)
    
    if edge >= 4:
        lean = "Strong Home 1H"
        rec = bet_recommendation(conf)
    elif edge >= 2:
        lean = "Moderate Home 1H"
        rec = bet_recommendation(conf * 0.85)
    elif edge >= 1:
        lean = "Slight Home 1H"
        rec = "PASS"
    elif edge <= -4:
        lean = "Strong Away 1H"
        rec = bet_recommendation(conf)
    elif edge <= -2:
        lean = "Moderate Away 1H"
        rec = bet_recommendation(conf * 0.85)
    elif edge <= -1:
        lean = "Slight Away 1H"
        rec = "PASS"
    else:
        lean = "Pass"
        rec = "PASS"
    
    return {
        "record_type": "first_half",
        "q1_home": q1_home,
        "q1_away": q1_away,
        "q2_home_proj": home_q2,
        "q2_away_proj": away_q2,
        "home_score": first_half_home,
        "away_score": first_half_away,
        "total": first_half_total,
        "spread": first_half_spread,
        "home_win_prob": round(first_half_prob, 4),
        "away_win_prob": round(1 - first_half_prob, 4),
        "edge": round(edge, 2),
        "confidence": round(conf, 1),
        "lean": lean,
        "recommendation": rec,
    }


# ============================================================================
# PLAYER PROP GENERATION (Custom for this matchup)
# ============================================================================

def generate_basketball_player_props(home_team: str, away_team: str,
                                     home_roster: List[Dict], away_roster: List[Dict],
                                     home_ortg: float = 115.0, away_drtg: float = 106.0,
                                     away_ortg: float = 108.0, home_drtg: float = 102.0) -> Dict[str, Any]:
    """Generate basketball player props for the match"""
    
    props = {
        "sport": "basketball",
        "matchup": f"{home_team} vs {away_team}",
        "player_props": [],
        "top_recommendations": []
    }
    
    # Pace factor
    expected_pace = (68.5 + 74.0) / 2  # 71.25 average
    
    for player in home_roster + away_roster:
        team = home_team if player in home_roster else away_team
        is_home = (team == home_team)
        
        # Points prop
        ppg = player.get('ppg', 10.0)
        line = player.get('pts_line', ppg)
        
        # Adjust for matchup
        if is_home:
            # Milano home: strong defense vs Venezia, moderate pace control
            pace_adj = 0.95
            matchup_adj = away_drtg / 115.0  # Venezia allows ~106, PPG ~115
        else:
            # Venezia away: vs elite Milano defense
            pace_adj = 0.92
            matchup_adj = home_drtg / 115.0
        
        proj_pts = round(ppg * pace_adj * matchup_adj, 1)
        pts_edge = proj_pts - line
        pts_conf = min(100, max(0, 50 + pts_edge * 12))
        pts_rec = "Over" if pts_edge > 1.0 else "Under" if pts_edge < -1.0 else "Pass"
        
        props["player_props"].append({
            "player_name": player["name"],
            "team": team,
            "position": player["position"],
            "prop_type": "Points",
            "line": line,
            "projection": proj_pts,
            "edge": round(pts_edge, 2),
            "confidence": round(pts_conf, 1),
            "recommendation": pts_rec,
            "lean": pts_rec if pts_rec != "Pass" else "No Lean",
            "matchup_factor": "Milano elite defense" if not is_home else "Home court",
        })
        
        # Rebounds prop (C, PF, SF)
        if player["position"] in ['C', 'PF', 'SF']:
            rpg = player.get('rpg', 4.0)
            line_rb = player.get('reb_line', rpg)
            proj_rb = round(rpg * 0.95, 1)
            rb_edge = proj_rb - line_rb
            rb_conf = min(100, max(0, 50 + rb_edge * 15))
            rb_rec = "Over" if rb_edge > 0.5 else "Under" if rb_edge < -0.5 else "Pass"
            
            props["player_props"].append({
                "player_name": player["name"],
                "team": team,
                "position": player["position"],
                "prop_type": "Rebounds",
                "line": line_rb,
                "projection": proj_rb,
                "edge": round(rb_edge, 2),
                "confidence": round(rb_conf, 1),
                "recommendation": rb_rec,
                "lean": rb_rec if rb_rec != "Pass" else "No Lean",
            })
        
        # Assists prop (PG, SG)
        if player["position"] in ['PG', 'SG']:
            apg = player.get('apg', 3.0)
            line_ast = player.get('ast_line', apg)
            proj_ast = round(apg * 1.05, 1)  # Guards facilitate more vs 2-3 zone
            ast_edge = proj_ast - line_ast
            ast_conf = min(100, max(0, 50 + ast_edge * 15))
            ast_rec = "Over" if ast_edge > 0.5 else "Under" if ast_edge < -0.5 else "Pass"
            
            props["player_props"].append({
                "player_name": player["name"],
                "team": team,
                "position": player["position"],
                "prop_type": "Assists",
                "line": line_ast,
                "projection": proj_ast,
                "edge": round(ast_edge, 2),
                "confidence": round(ast_conf, 1),
                "recommendation": ast_rec,
                "lean": ast_rec if ast_rec != "Pass" else "No Lean",
            })
    
    # Sort by edge and get top recommendations
    all_props = props["player_props"]
    top_props = sorted(all_props, key=lambda x: abs(x.get("edge", 0)), reverse=True)
    props["top_recommendations"] = top_props[:8]
    
    return props


# ============================================================================
# MAIN ANALYSIS
# ============================================================================

def run_milano_venezia_analysis():
    """Run comprehensive analysis for Olimpia Milano vs Reyer Venezia"""
    
    print("=" * 80)
    print("EUROLEAGUE ANALYSIS: OLIMPIA MILANO vs REYER VENEZIA")
    print("=" * 80)
    print()
    print("MATCHUP NARRATIVE: Pace vs. Execution")
    print("  Milano: Methodical, defensively elite, half-court grinders")
    print("  Venezia: Home adrenaline, high-variance 3-point shooters, pace pushers")
    print()
    print("KEY FACTORS:")
    print("  [Depth Delta] Milano has 10-11 rotation players vs Venezia's 8")
    print("  [Pace Suppression] Milano limits possessions, controls defensive glass")
    print("  [Home Adrenaline] Venezia's loud small arena boosts 1st Half performance")
    print("  [Variance Dependency] Venezia needs 3P% > 33% to stay competitive")
    print("  [Fatigue Red Flag] Venezia's primary guards face heavy usage vs Milano defense")
    print("=" * 80)
    print()
    
    # Get metrics
    milano_data = get_milano_metrics()
    venezia_data = get_venezia_metrics()
    
    home_roster = get_milano_roster()
    away_roster = get_venezia_roster()
    
    # Create team metrics objects (placeholder values with analysis-based overrides)
    home = FIBATeamMetrics(
        ortg_per_100=milano_data['ortg_per_100'],
        drtg_per_100=milano_data['drtg_per_100'],
        baseline_net_per_100=milano_data['baseline_net_per_100'],
        recent_net_per_100=milano_data['recent_net_per_100'],
        pace_per_40=milano_data['pace_per_40'],
        rest_days=milano_data['rest_days'],
        travel_km=milano_data['travel_km'],
        back_to_back=milano_data['back_to_back'],
        three_in_six=milano_data['three_in_six'],
        split_edge=milano_data['split_edge'],
        rotation_depth=milano_data['rotation_depth'],
        injury_status=milano_data['injury_status'],
        coach_stability=milano_data['coach_stability'],
        motivation=milano_data['motivation'],
        three_pt_pct=milano_data['three_pt_pct'],
        orb_pct=milano_data['orb_pct'],
    )
    
    away = FIBATeamMetrics(
        ortg_per_100=venezia_data['ortg_per_100'],
        drtg_per_100=venezia_data['drtg_per_100'],
        baseline_net_per_100=venezia_data['baseline_net_per_100'],
        recent_net_per_100=venezia_data['recent_net_per_100'],
        pace_per_40=venezia_data['pace_per_40'],
        rest_days=venezia_data['rest_days'],
        travel_km=venezia_data['travel_km'],
        back_to_back=venezia_data['back_to_back'],
        three_in_six=venezia_data['three_in_six'],
        split_edge=venezia_data['split_edge'],
        rotation_depth=venezia_data['rotation_depth'],
        injury_status=venezia_data['injury_status'],
        coach_stability=venezia_data['coach_stability'],
        motivation=venezia_data['motivation'],
        three_pt_pct=venezia_data['three_pt_pct'],
        orb_pct=venezia_data['orb_pct'],
    )
    
    # Game context
    ctx = FIBAContext(
        game_id="olimpia_milano_vs_reyer_venezia",
        date="2026-06-18",
        league="EuroLeague",
        home_team="Olimpia Milano",
        away_team="Reyer Venezia",
        market_line=0.0,
        current_line=0.0,
        open_line=0.0,
        notes="Milano favored; Venezia home underdog with high variance profile"
    )
    
    # ========================================================================
    # 1. Q1 PREDICTION
    # ========================================================================
    print("=" * 80)
    print("1. FIRST QUARTER (Q1) PROJECTION")
    print("=" * 80)
    print()
    
    # Q1 metrics with narrative-driven data
    home_q1_metrics = {
        'pts_for': 18.5,
        'pts_against': 16.0,
        'home_edge': 2.5,
        'coach_fast_start': 'green',
        'injury_status': 'green',
        'starting_five_net': 4.5,
    }
    
    away_q1_metrics = {
        'pts_for': 19.5,  # Venezia fast starts
        'pts_against': 18.0,
        'home_edge': 0.0,
        'coach_fast_start': 'yellow',  # More measured start on road
        'injury_status': 'yellow',
        'starting_five_net': 2.0,
    }
    
    q1_result = fiba_build_q1(home, away, home_q1_metrics, away_q1_metrics, ctx)
    
    print(f"   Projected Q1 Score:")
    print(f"     Milano: {q1_result['projected_q1_home']:.1f}")
    print(f"     Venezia: {q1_result['projected_q1_away']:.1f}")
    print(f"   Q1 Total: {q1_result['projected_q1_total']:.1f}")
    print(f"   Q1 Model: {q1_result['q1_model']:+.2f}")
    print(f"   Q1 Lean: {q1_result['lean']}")
    print()
    
    # ========================================================================
    # 2. FIRST HALF (1H) PROJECTION
    # ========================================================================
    print("=" * 80)
    print("2. FIRST HALF (1H) PROJECTION")
    print("=" * 80)
    print()
    
    first_half_result = build_first_half_projection(home, away, ctx, q1_result)
    
    print(f"   First Half Projection:")
    print(f"     Milano 1H: {first_half_result['home_score']:.1f}")
    print(f"     Venezia 1H: {first_half_result['away_score']:.1f}")
    print(f"   1H Total: {first_half_result['total']:.1f}")
    print(f"   1H Spread: Milano {first_half_result['spread']:+.1f}")
    print(f"   1H Milano Win Prob: {first_half_result['home_win_prob']:.1%}")
    print(f"   1H Lean: {first_half_result['lean']}")
    print(f"   1H Confidence: {first_half_result['confidence']:.1f}%")
    print()
    
    # ========================================================================
    # 3. FULL GAME (FG) PROJECTION
    # ========================================================================
    print("=" * 80)
    print("3. FULL GAME (FG) PROJECTION")
    print("=" * 80)
    print()
    
    full_game_result = fiba_build_full_game(home, away, ctx)
    
    print(f"   Projected Score:")
    print(f"     Milano: {full_game_result['projected_home_score']:.1f}")
    print(f"     Venezia: {full_game_result['projected_away_score']:.1f}")
    print(f"   Projected Total: {full_game_result['projected_total']:.1f}")
    print(f"   Win Prob: Milano {full_game_result['probability']:.1%}")
    print(f"   Model Edge: {full_game_result['model_edge']:+.2f}")
    print(f"   Full Game Lean: {full_game_result['lean']}")
    print()
    
    # ========================================================================
    # 4. TOTALS ANALYSIS
    # ========================================================================
    print("=" * 80)
    print("4. TOTALS (OVER/UNDER) ANALYSIS")
    print("=" * 80)
    print()
    
    projected_total = full_game_result['projected_total']
    
    # Typical market line ~148-152 for EuroLeague
    market_total_line = 149.5  # Assumed line
    
    edge_vs_total = projected_total - market_total_line
    total_conf = confidence_score(abs(edge_vs_total) * 8, volatility=0.5)
    total_lean = "OVER" if edge_vs_total > 0 else "UNDER"
    total_rec = bet_recommendation(total_conf)
    
    print(f"   Model Projected Total: {projected_total:.1f}")
    print(f"   Assumed Market Line: {market_total_line}")
    print(f"   Model Edge: {edge_vs_total:+.2f}")
    print(f"   Over Probability: ~{50 + edge_vs_total * 3:.0f}%")
    print(f"   Confidence: {total_conf:.1f}%")
    print(f"   Recommendation: {total_rec} {total_lean}")
    print()
    
    # Additional total lines
    alt_lines = {
        145.5: projected_total - 145.5,
        150.5: projected_total - 150.5,
        155.5: projected_total - 155.5,
    }
    
    print("   Alternate Total Lines:")
    for line, edge in alt_lines.items():
        line_conf = confidence_score(abs(edge) * 8, volatility=0.55)
        line_lean = "OVER" if edge > 0 else "UNDER"
        print(f"     {line}: Edge {edge:+.2f} | Lean {line_lean} | Conf {line_conf:.1f}%")
    print()
    
    # ========================================================================
    # 5. SIDES (HANDICAP/SPREAD) ANALYSIS
    # ========================================================================
    print("=" * 80)
    print("5. SIDES (MONEYLINE/SPREAD) ANALYSIS")
    print("=" * 80)
    print()
    
    milano_win_prob = full_game_result['probability']
    venezia_win_prob = 1 - milano_win_prob
    
    # Implied odds from probability
    milano_implied_odds = milano_win_prob / (1 - milano_win_prob) if milano_win_prob < 1 else 999
    venezia_implied_odds = venezia_win_prob / (1 - venezia_win_prob) if venezia_win_prob < 1 else 999
    
    # Spread: Milano -6.5 typical
    market_spread = -6.5
    spread_edge = (milano_win_prob - 0.5) * 14 - market_spread  # -6.5
    spread_conf = confidence_score(abs(spread_edge) * 10, volatility=0.5)
    
    spread_rec = bet_recommendation(spread_conf)
    spread_lean = "MILANO" if milano_win_prob > 0.55 else "VENEZIA" if milano_win_prob < 0.45 else "PASS"
    
    print(f"   Milano Win Probability: {milano_win_prob:.1%}")
    print(f"   Venezia Win Probability: {venezia_win_prob:.1%}")
    print(f"   Model Edge: Milano {full_game_result['model_edge']:+.2f}")
    print()
    print(f"   Spread: Milano {market_spread}")
    print(f"   Spread Recommendation: {spread_rec} {spread_lean}")
    print(f"   Spread Confidence: {spread_conf:.1f}%")
    print()
    
    print(f"   Moneyline Analysis:")
    print(f"     Milano ML Fair Odds: ~{int(100/milano_win_prob) if milano_win_prob > 0.01 else 999}")
    print(f"     Venezia ML Fair Odds: ~{int(100/venezia_win_prob) if venezia_win_prob > 0.01 else 999}")
    print()
    
    # ========================================================================
    # 6. PLAYER PROPS
    # ========================================================================
    print("=" * 80)
    print("6. PLAYER PROP RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    player_props = generate_basketball_player_props(
        home_team="Olimpia Milano",
        away_team="Reyer Venezia",
        home_roster=home_roster,
        away_roster=away_roster,
        home_ortg=home.ortg_per_100,
        away_drtg=away.drtg_per_100,
        away_ortg=away.ortg_per_100,
        home_drtg=home.drtg_per_100,
    )
    
    print("   === TOP PLAYER PROP RECOMMENDATIONS ===")
    print()
    
    for i, prop in enumerate(player_props["top_recommendations"][:6], 1):
        print(f"   {i}. {prop['player_name']} ({prop['team']}) - {prop['prop_type']}")
        print(f"      Line: {prop['line']} | Proj: {prop['projection']} | Edge: {prop['edge']:+.2f}")
        print(f"      Recommendation: {prop['recommendation']} | Conf: {prop['confidence']:.1f}%")
        print()
    
    print("   === POINTS PROPS ===")
    pts_props = [p for p in player_props["player_props"] if p["prop_type"] == "Points"]
    for prop in sorted(pts_props, key=lambda x: abs(x["edge"]), reverse=True)[:5]:
        print(f"   {prop['player_name']} ({prop['team']}): O/U {prop['line']} -> "
              f"{prop['recommendation']} (Proj: {prop['projection']}, Conf: {prop['confidence']:.0f}%)")
    print()
    
    print("   === REBOUNDS PROPS ===")
    reb_props = [p for p in player_props["player_props"] if p["prop_type"] == "Rebounds"]
    for prop in sorted(reb_props, key=lambda x: abs(x["edge"]), reverse=True)[:5]:
        print(f"   {prop['player_name']} ({prop['team']}): O/U {prop['line']} -> "
              f"{prop['recommendation']} (Proj: {prop['projection']}, Conf: {prop['confidence']:.0f}%)")
    print()
    
    print("   === ASSISTS PROPS ===")
    ast_props = [p for p in player_props["player_props"] if p["prop_type"] == "Assists"]
    for prop in sorted(ast_props, key=lambda x: abs(x["edge"]), reverse=True)[:5]:
        print(f"   {prop['player_name']} ({prop['team']}): O/U {prop['line']} -> "
              f"{prop['recommendation']} (Proj: {prop['projection']}, Conf: {prop['confidence']:.0f}%)")
    print()
    
    # ========================================================================
    # 7. NARRATIVE-SPECIFIC RECOMMENDATIONS
    # ========================================================================
    print("=" * 80)
    print("7. NARRATIVE-SPECIFIC MARKET RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    print("   KEY THESES:")
    print("   " + "-" * 60)
    print()
    print("   [Depth Delta] Milano's 11-man rotation vs Venezia's 8 means:")
    print("     - 3rd/4th quarter attrition advantage for Milano")
    print("     - Consider: MILANO Q4 MONEYLINE or LIVE 4Q SPREAD")
    print()
    print("   [Pace Suppression] Milano controls tempo:")
    print("     - UNDER on total likely holds value")
    print("     - Q1/Q2 slightly lower scoring than Vegas expectations")
    print()
    print("   [Home Adrenaline] Venezia first half boost:")
    print("     - Venezia 1H + spread has value (closer games early)")
    print("     - Q1 often tight before Milano defense locks in Q2/Q3")
    print()
    print("   [Variance Dependency] Venezia needs hot 3PT shooting:")
    print("     - Milano defense gives up low volume of 3PA")
    print("     - VENEZIA TEAM TOTAL UNDERS have edge")
    print()
    print("   [Fatigue Delta] Late-game collapse risk for Venezia:")
    print("     - 3rd quarter = Milano separation window")
    print("     - Consider: MILANO -3.5 2ND HALF SPREAD if available")
    print()
    
    # ========================================================================
    # 8. COMPREHENSIVE RESULTS DICTIONARY
    # ========================================================================
    
    results = {
        "game_info": {
            "home_team": "Olimpia Milano",
            "away_team": "Reyer Venezia",
            "league": "EuroLeague",
            "date": "2026-06-18",
            "venue": "Taliercio, Venezia",
            "matchup_narrative": "Pace vs. Execution - Milano methodical defense vs Venezia high-variance 3-point offense"
        },
        "narrative_summary": {
            "depth_delta": {
                "description": "Milano has 10-11 rotation players vs Venezia's 8",
                "impact": "3rd/4th quarter attrition advantage for Milano",
                "markets": ["Milano Q4 ML", "Milano Live 2H Spread"]
            },
            "pace_suppression": {
                "description": "Milano controls tempo, limits fast break opportunities",
                "impact": "Lower total, especially late in game",
                "markets": ["Game Total UNDER", "1H Total UNDER"]
            },
            "home_adrenaline": {
                "description": "Venezia home crowd creates early game energy",
                "impact": "Tight 1H, Venezia stays competitive early",
                "markets": ["Venezia +1H spread", "Q1 tight"]
            },
            "variance_dependency": {
                "description": "Venezia needs >33% 3PT% to beat Milano defense",
                "impact": "Venezia unders likely if shooting variance regresses",
                "markets": ["Venezia Team Total UNDER", "Milano Team Total OVER"]
            },
            "fatigue_red_flag": {
                "description": "Venezia guards face heavy usage vs Milano's rotating defense",
                "impact": "Late game turnovers, short jumpers",
                "markets": ["Milano 3Q/4Q coverage", "Game TOTAL 2H UNDER"]
            }
        },
        "q1": {
            "projected_home_score": q1_result['projected_q1_home'],
            "projected_away_score": q1_result['projected_q1_away'],
            "projected_total": q1_result['projected_q1_total'],
            "model_score": q1_result['q1_model'],
            "lean": q1_result['lean'],
            "confidence": 55.0,
            "recommendation": "PASS",
        },
        "first_half": {
            "projected_home_score": first_half_result['home_score'],
            "projected_away_score": first_half_result['away_score'],
            "projected_total": first_half_result['total'],
            "spread": first_half_result['spread'],
            "home_win_prob": first_half_result['home_win_prob'],
            "away_win_prob": first_half_result['away_win_prob'],
            "lean": first_half_result['lean'],
            "confidence": first_half_result['confidence'],
            "recommendation": first_half_result['recommendation'],
        },
        "full_game": {
            "projected_home_score": full_game_result['projected_home_score'],
            "projected_away_score": full_game_result['projected_away_score'],
            "projected_total": full_game_result['projected_total'],
            "home_win_prob": full_game_result['probability'],
            "away_win_prob": 1 - full_game_result['probability'],
            "model_edge": full_game_result['model_edge'],
            "historical_gap": full_game_result['historical_gap'],
            "rest_gap": full_game_result['rest_gap'],
            "context_gap": full_game_result['context_gap'],
            "lean": full_game_result['lean'],
            "confidence": 62.0,
        },
        "totals": {
            "projected_total": projected_total,
            "market_line": market_total_line,
            "edge": round(edge_vs_total, 2),
            "confidence": total_conf,
            "lean": total_lean,
            "recommendation": total_rec,
            "alternate_lines": [
                {"line": 145.5, "edge": round(projected_total - 145.5, 2)},
                {"line": 150.5, "edge": round(projected_total - 150.5, 2)},
                {"line": 155.5, "edge": round(projected_total - 155.5, 2)},
            ]
        },
        "sides": {
            "spread_line": market_spread,
            "milano_win_prob": milano_win_prob,
            "venezia_win_prob": venezia_win_prob,
            "edge": round(spread_edge, 2),
            "confidence": spread_conf,
            "lean": spread_lean,
            "recommendation": spread_rec,
        },
        "player_props": player_props,
        "betting_recommendations": {
            "primary_bets": [
                {
                    "market": "Game Total",
                    "recommendation": f"{total_rec} {total_lean} {market_total_line}",
                    "confidence": total_conf,
                    "reasoning": "Milano pace suppression + defensive efficiency -> lower scoring"
                },
                {
                    "market": "Game Spread",
                    "recommendation": f"{spread_rec} Milano -6.5",
                    "confidence": spread_conf,
                    "reasoning": "Depth Delta + defensive edge = 4th quarter separation"
                },
                {
                    "market": "1H Spread",
                    "recommendation": f"{first_half_result['recommendation']} Venezia +2.5 1H",
                    "confidence": first_half_result['confidence'],
                    "reasoning": "Home adrenaline keeps Venezia close early"
                },
            ],
            "player_props_top3": [
                {
                    "player": player_props["top_recommendations"][0]["player_name"],
                    "prop": player_props["top_recommendations"][0]["prop_type"],
                    "recommendation": player_props["top_recommendations"][0]["recommendation"],
                    "confidence": player_props["top_recommendations"][0]["confidence"],
                },
                {
                    "player": player_props["top_recommendations"][1]["player_name"],
                    "prop": player_props["top_recommendations"][1]["prop_type"],
                    "recommendation": player_props["top_recommendations"][1]["recommendation"],
                    "confidence": player_props["top_recommendations"][1]["confidence"],
                },
                {
                    "player": player_props["top_recommendations"][2]["player_name"],
                    "prop": player_props["top_recommendations"][2]["prop_type"],
                    "recommendation": player_props["top_recommendations"][2]["recommendation"],
                    "confidence": player_props["top_recommendations"][2]["confidence"],
                },
            ]
        },
        "timestamp": datetime.now().isoformat()
    }
    
    return results


# ============================================================================
# OUTPUT AND REPORTING
# ============================================================================

def print_final_summary(results: Dict):
    """Print the final betting summary"""
    
    print("=" * 80)
    print("FINAL BETTING RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    print(f"Match: {results['game_info']['home_team']} vs {results['game_info']['away_team']}")
    print(f"League: {results['game_info']['league']}")
    print()
    
    print("PROJECTED SCORE:")
    print(f"  Milano {results['full_game']['projected_home_score']:.1f} - "
          f"{results['full_game']['projected_away_score']:.1f} Venezia")
    print(f"  Total: {results['full_game']['projected_total']:.1f}")
    print()
    
    print("BETTING RECOMMENDATIONS:")
    print("  " + "-" * 60)
    
    for rec in results['betting_recommendations']['primary_bets']:
        print(f"  [BET] {rec['market']}: {rec['recommendation']}")
        print(f"        Confidence: {rec['confidence']:.1f}%")
        print(f"        Reasoning: {rec['reasoning']}")
        print()
    
    print("TOP PLAYER PROP RECOMMENDATIONS:")
    print("  " + "-" * 60)
    for prop in results['betting_recommendations']['player_props_top3']:
        print(f"  [BET] {prop['player']} {prop['prop']}: {prop['recommendation']}")
        print(f"        Confidence: {prop['confidence']:.1f}%")
    
    print()
    print("NARRATIVE EDGE SUMMARY:")
    print("  - Milano's Depth Delta creates 3rd/4Q attrition advantage")
    print("  - Milano pace suppression -> Game Total UNDER value")
    print("  - Venezia Home Adrenaline -> 1H closer than final score")
    print("  - Venezia 3PT variance dependency -> Team Total UNDER value")
    print("  - Fatigue Delta for Venezia guards vs rotating Milano D")
    print()


def save_results(results: Dict):
    """Save results to JSON file"""
    output_dir = Path("output/basketball")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "olimpia_milano_vs_reyer_venezia_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"Detailed results saved to: {output_file}")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("OLIMPIA MILANO vs REYER VENEZIA - COMPREHENSIVE ANALYSIS")
    print("EuroLeague - June 18, 2026")
    print("=" * 80 + "\n")
    
    # Run analysis
    results = run_milano_venezia_analysis()
    
    # Print final summary
    print_final_summary(results)
    
    # Save to file
    save_results(results)
    
    print("\nAnalysis complete.")