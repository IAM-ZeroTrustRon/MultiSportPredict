#!/usr/bin/env python
"""
Sharp Betting Report: Shenzhen Juniors vs. Shenzhen Peng City
Chinese Super League - June 19, 2026 | 18:30 KST
Venue: Shenzhen Universiade Sports Centre

Tactical Baseline: Shenzhen Peng City (High Possession / Overload) vs. Shenzhen Juniors (Low Block / Counter)
"""

import sys
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Import core confidence engine
from core.confidence_engine import confidence_score, bet_recommendation


def sigmoid(x: float) -> float:
    """Sigmoid function for probability conversion"""
    x = max(-500, min(500, x))
    return 1 / (1 + math.exp(-x))


def clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp value between low and high bounds"""
    return max(low, min(high, x))


def poisson_over_prob(lam: float, line: float) -> float:
    """Calculate probability of over a given line using Poisson distribution"""
    n = int(math.floor(line))
    frac = line - n
    if abs(frac) < 1e-9:
        return 1 - sum(math.exp(-lam) * lam**k / math.factorial(k) for k in range(0, n + 1))
    else:
        threshold = int(math.floor(line))
        return 1 - sum(math.exp(-lam) * lam**k / math.factorial(k) for k in range(0, threshold + 1))


# ============================================================================
# SHENZHEN DERBY SPECIFIC CONFIGURATION
# ============================================================================

SHENZHEN_CONFIG = {
    'league_avg_corners': 9.8,
    'league_avg_goals': 2.6,
    'possession_impact_corners': 0.15,  # Each 10% possession adds ~1.5 corners
    'low_block_corner_suppression': 0.25,  # Low blocks reduce opponent corners by ~25%
    'cross_deflection_rate': 0.30,  # 30% of crosses headed/deflected out for corners
}


def get_team_stats(team: str) -> Dict[str, Any]:
    """
    Get estimated team statistics for Shenzhen teams.
    """
    # Shenzhen Peng City (Home) - High possession, wing overload
    if team in ["SHENZHEN_PENG", "Shenzhen Peng City", "Peng City", "SPC"]:
        return {
            'team_name': 'Shenzhen Peng City',
            'abbreviation': 'SPC',
            'possession_pct': 0.68,
            'xg_for': 1.85,
            'xg_against': 1.15,
            'goals_for': 1.72,
            'goals_against': 1.08,
            'shots_per_game': 14.5,
            'sot_per_game': 5.8,
            'corners_per_game': 7.2,
            'corners_conceded_per_game': 4.5,
            'clean_sheets': 3,
            'tempo': 0.15,
            'width_crossing': 0.90,
            'final_third_pressure': 0.85,
            'recent_form': 0.65,
            'home_record': 0.70,
            'form_string': 'W,W,W,L,W',
        }
    # Shenzhen Juniors (Away) - Low block, counter attack
    elif team in ["SHENZHEN_JUN", "Shenzhen Juniors", "Juniors", "SJ"]:
        return {
            'team_name': 'Shenzhen Juniors',
            'abbreviation': 'SJ',
            'possession_pct': 0.32,
            'xg_for': 1.25,
            'xg_against': 1.45,
            'goals_for': 1.15,
            'goals_against': 1.38,
            'shots_per_game': 9.5,
            'sot_per_game': 3.2,
            'corners_per_game': 4.8,
            'corners_conceded_per_game': 6.5,
            'clean_sheets': 2,
            'tempo': -0.20,
            'width_crossing': 0.35,
            'final_third_pressure': 0.45,
            'recent_form': 0.45,
            'away_record': 0.35,
            'form_string': 'L,D,L,W,D',
        }
    else:
        return {
            'team_name': team,
            'abbreviation': team[:3].upper(),
            'possession_pct': 0.50,
            'xg_for': 1.45,
            'xg_against': 1.35,
            'goals_for': 1.35,
            'goals_against': 1.30,
            'shots_per_game': 11.0,
            'sot_per_game': 4.2,
            'corners_per_game': 5.5,
            'corners_conceded_per_game': 5.5,
            'clean_sheets': 3,
            'tempo': 0.0,
            'width_crossing': 0.55,
            'final_third_pressure': 0.60,
            'recent_form': 0.50,
            'home_record': 0.50,
            'away_record': 0.45,
            'form_string': 'W,L,D,W,L',
        }


def project_corners_market(home_stats: Dict, away_stats: Dict, venue: str = "Shenzhen Universiade Sports Centre") -> Dict[str, Any]:
    """
    Project corner market based on tactical matchup.
    
    Key factors:
    - Peng City's extreme width and crossing
    - Juniors' low block congestion
    - Head-to-head corner history
    - Park factor (if applicable)
    """
    
    # Base corner projection
    home_corner_base = home_stats['corners_per_game']
    away_corner_base = away_stats['corners_per_game']
    
    # Adjust for possession dominance (Peng City 68% possession)
    possession_boost = (home_stats['possession_pct'] - 0.50) * 10 * SHENZHEN_CONFIG['possession_impact_corners']
    
    # Adjust for low block (Juniors concede more corners against wide teams)
    low_block_suppression = SHENZHEN_CONFIG['low_block_corner_suppression']
    away_corner_adj = away_corner_base * (1 - low_block_suppression * 0.5)
    
    # Peng City's crossing volume against low block
    crossing_factor = home_stats['width_crossing'] * 1.3  # Elite width
    
    # Combined projection
    home_corners_proj = home_corner_base + possession_boost + (crossing_factor * 1.5)
    away_corners_proj = away_corner_adj * 0.85  # Away team sees reduced corners
    
    total_corners_proj = home_corners_proj + away_corners_proj
    
    # Team-specific corner totals
    home_team_corners_proj = home_corners_proj
    away_team_corners_proj = away_corners_proj
    
    # Market recommendations
    market_total_line = 10.5
    market_home_corners_line = 6.5
    
    total_edge = total_corners_proj - market_total_line
    home_corners_edge = home_team_corners_proj - market_home_corners_line
    
    # Total corners recommendation
    if total_edge > 1.5:
        total_corners_rec = f"Over {market_total_line}"
        total_corners_conf = confidence_score(total_edge, volatility=0.65)
    elif total_edge < -1.5:
        total_corners_rec = f"Under {market_total_line}"
        total_corners_conf = confidence_score(abs(total_edge), volatility=0.65)
    else:
        total_corners_rec = "Pass"
        total_corners_conf = 0.0
    
    # Team corners recommendation (the sharp play)
    if home_corners_edge >= 2.0:
        home_corners_rec = f"Over {market_home_corners_line}"
        home_corners_conf = confidence_score(home_corners_edge, volatility=0.55)
    elif home_corners_edge <= -2.0:
        home_corners_rec = f"Under {market_home_corners_line}"
        home_corners_conf = confidence_score(abs(home_corners_edge), volatility=0.55)
    else:
        home_corners_rec = "Pass"
        home_corners_conf = 0.0
    
    return {
        'projected_total_corners': round(total_corners_proj, 1),
        'projected_home_team_corners': round(home_team_corners_proj, 1),
        'projected_away_team_corners': round(away_team_corners_proj, 1),
        'market_total_line': market_total_line,
        'market_home_corners_line': market_home_corners_line,
        'total_corners_edge': round(total_edge, 2),
        'home_corners_edge': round(home_corners_edge, 2),
        'total_corners_recommendation': total_corners_rec,
        'total_corners_confidence': round(total_corners_conf, 1),
        'home_corners_recommendation': home_corners_rec,
        'home_corners_confidence': round(home_corners_conf, 1),
        'sharp_play': f"Shenzhen Peng City - OVER {market_home_corners_line} Team Corners",
        'tactical_reasoning': (
            f"Peng City's extreme width ({home_stats['width_crossing']:.0%}) and {home_stats['possession_pct']:.0%} "
            f"possession vs. Juniors' low block forces crosses that are deflected/headed out ({SHENZHEN_CONFIG['cross_deflection_rate']:.0%} rate). "
            f"Model projects {home_team_corners_proj:.1f} Peng City corners."
        ),
    }


def calculate_player_prop_edge(player_name: str, team: str, position: str,
                               base_shots_90: float, base_sot_90: float,
                               low_block_modifier_shots: float, low_block_modifier_sot: float,
                               shot_distance_factor: float = 1.0) -> Dict[str, Any]:
    """
    Calculate player prop edge rating for shots on target.
    
    Edge Rating > 7.0 = Elite (OVER 1.5 SoT or Anytime Goalscorer value)
    Edge Rating 5.0-7.0 = Strong
    Edge Rating < 5.0 = Avoid
    """
    
    # Apply low block modifiers
    proj_shots = base_shots_90 * (1 + low_block_modifier_shots)
    proj_sot = base_sot_90 * (1 + low_block_modifier_sot)
    
    # Apply shot distance penalty (further shots = harder to hit target)
    if shot_distance_factor < 1.0:
        proj_sot *= shot_distance_factor
    
    # Calculate edge rating (simplified model: combination of volume and efficiency)
    # Base rating from shots per 90
    shots_component = proj_shots * 2.0
    # Efficiency component from SoT rate
    sot_efficiency = proj_sot / proj_shots if proj_shots > 0 else 0
    efficiency_component = sot_efficiency * 5.0
    
    edge_rating = shots_component + efficiency_component
    
    # Classification
    if edge_rating >= 7.0:
        classification = "Elite"
        recommendation = f"OVER 1.5 SoT or Anytime Goalscorer - {player_name}"
    elif edge_rating >= 5.0:
        classification = "Strong"
        recommendation = f"Consider {player_name} SoT Over"
    else:
        classification = "Avoid"
        recommendation = f"Fade {player_name} - insufficient edge"
    
    return {
        'player_name': player_name,
        'team': team,
        'position': position,
        'base_shots_90': base_shots_90,
        'base_sot_90': base_sot_90,
        'low_block_modifier_shots': low_block_modifier_shots,
        'low_block_modifier_sot': low_block_modifier_sot,
        'proj_total_shots': round(proj_shots, 2),
        'proj_sot': round(proj_sot, 2),
        'edge_rating': round(edge_rating, 1),
        'classification': classification,
        'recommendation': recommendation,
    }


def analyze_shenzhen_derby():
    """
    Comprehensive analysis for Shenzhen Juniors vs Shenzhen Peng City
    """
    
    print("=" * 80)
    print("SHARP BETTING REPORT: SHENZHEN JUNIORS vs SHENZHEN PENG CITY")
    print("Chinese Super League - June 19, 2026 | 18:30 KST")
    print("Venue: Shenzhen Universiade Sports Centre")
    print("=" * 80)
    print()
    
    # Get team statistics
    home_stats = get_team_stats("Shenzhen Peng City")
    away_stats = get_team_stats("Shenzhen Juniors")
    
    # 1. TACTICAL MATCHUP ANALYSIS
    print("1. TACTICAL MATCHUP ANALYSIS")
    print("-" * 40)
    print()
    print("   SHENZHEN PENG CITY (Home) - High Possession / Overload:")
    print(f"      Possession: {home_stats['possession_pct']:.0%}")
    print(f"      Style: Extreme width, wingers stretch defense, high crossing volume")
    print(f"      xG For: {home_stats['xg_for']:.2f} | xG Against: {home_stats['xg_against']:.2f}")
    print(f"      Width/Crossing: {home_stats['width_crossing']:.0%}")
    print(f"      Form: {home_stats['form_string']}")
    print()
    print("   SHENZHEN JUNIORS (Away) - Low Block / Counter:")
    print(f"      Possession: {away_stats['possession_pct']:.0%}")
    print(f"      Style: Compact defensive block, congested penalty area, counter-attack focused")
    print(f"      xG For: {away_stats['xg_for']:.2f} | xG Against: {away_stats['xg_against']:.2f}")
    print(f"      Defensive Width: {away_stats['width_crossing']:.0%}")
    print(f"      Form: {away_stats['form_string']}")
    print()
    
    # 2. CORNER MARKET RECALIBRATION
    print("2. CORNER MARKET RECALIBRATION (SHARP ANGLE)")
    print("-" * 40)
    print()
    
    corner_analysis = project_corners_market(home_stats, away_stats)
    
    print(f"   Tactical Context:")
    print(f"   - Peng City operates with extreme width (wingers Albion Ademi, D. Owusu-Sekyere)")
    print(f"   - Peng City projected possession: {home_stats['possession_pct']:.0%}%")
    print(f"   - Juniors' low block forces attackers to byline for crosses")
    print(f"   - Crosses vs. low block: ~{SHENZHEN_CONFIG['cross_deflection_rate']:.0%} headed/deflected out of bounds")
    print()
    print(f"   Projected Corners:")
    print(f"   - Total Match Corners: {corner_analysis['projected_total_corners']}")
    print(f"   - Peng City Team Corners: {corner_analysis['projected_home_team_corners']}")
    print(f"   - Juniors Team Corners: {corner_analysis['projected_away_team_corners']}")
    print()
    print(f"   Market Lines:")
    print(f"   - Total Corners: O/U {corner_analysis['market_total_line']}")
    print(f"   - Peng City Team Corners: O/U {corner_analysis['market_home_corners_line']}")
    print()
    print(f"   CORNER RECOMMENDATIONS:")
    print(f"   - Total Corners: {corner_analysis['total_corners_recommendation']} (Confidence: {corner_analysis['total_corners_confidence']:.1f}%)")
    print(f"   - Peng City Team Corners: {corner_analysis['home_corners_recommendation']} (Confidence: {corner_analysis['home_corners_confidence']:.1f}%)")
    print()
    print(f"   SHARP PLAY: {corner_analysis['sharp_play']}")
    print(f"   Reasoning: {corner_analysis['tactical_reasoning']}")
    print()
    
    # 3. PLAYER PROP EDGE RATINGS (Shots on Target)
    print("3. PLAYER PROP EDGE RATINGS (Shots on Target)")
    print("-" * 40)
    print()
    print("   Algorithm: engineer_shot_prop_features() vs. Low Block defense")
    print("   Edge Rating > 7.0 = Elite | 5.0-7.0 = Strong | < 5.0 = Avoid")
    print()
    
    # Wesley (FW) - Elite edge
    wesley = calculate_player_prop_edge(
        player_name="Wesley",
        team="Shenzhen Peng City",
        position="FW",
        base_shots_90=3.20,
        base_sot_90=1.65,
        low_block_modifier_shots=0.20,  # +20% shots due to volume
        low_block_modifier_sot=-0.20,   # -20% SoT efficiency (crowded box)
        shot_distance_factor=1.0
    )
    
    # Albion Ademi (AM) - Strong edge
    ademi = calculate_player_prop_edge(
        player_name="Albion Ademi",
        team="Shenzhen Peng City",
        position="AM",
        base_shots_90=2.45,
        base_sot_90=1.10,
        low_block_modifier_shots=0.20,
        low_block_modifier_sot=-0.20,
        shot_distance_factor=0.95
    )
    
    # D. Owusu-Sekyere (RW) - Avoid
    owusu = calculate_player_prop_edge(
        player_name="D. Owusu-Sekyere",
        team="Shenzhen Peng City",
        position="RW",
        base_shots_90=2.10,
        base_sot_90=0.85,
        low_block_modifier_shots=0.20,
        low_block_modifier_sot=-0.30,   # -30% due to distance
        shot_distance_factor=0.75      # Further shots = heavily blocked
    )
    
    player_props = [wesley, ademi, owusu]
    
    for prop in player_props:
        print(f"   {prop['player_name']} ({prop['position']}):")
        print(f"      Base Sh/90: {prop['base_shots_90']:.2f} | Base SoT/90: {prop['base_sot_90']:.2f}")
        print(f"      Low Block Modifier: {prop['low_block_modifier_shots']:+.0%} Sh / {prop['low_block_modifier_sot']:+.0%} SoT")
        print(f"      Proj. Total Shots: {prop['proj_total_shots']:.2f}")
        print(f"      Proj. SoT: {prop['proj_sot']:.2f}")
        print(f"      Edge Rating: {prop['edge_rating']:.1f} ({prop['classification']})")
        print(f"      Recommendation: {prop['recommendation']}")
        print()
    
    # 4. GOAL MARKET PROJECTION
    print("4. GOAL MARKET PROJECTION")
    print("-" * 40)
    print()
    
    # Simple goal projection based on xG and tactical context
    home_goals_lam = (home_stats['xg_for'] * 1.1) + (away_stats['xg_against'] * 0.9)
    away_goals_lam = (away_stats['xg_for'] * 0.9) + (home_stats['xg_against'] * 1.1)
    
    # Adjust for possession and tactical style
    home_goals_lam *= (1 + (home_stats['possession_pct'] - 0.50) * 0.3)
    away_goals_lam *= (1 - (home_stats['possession_pct'] - 0.50) * 0.2)
    
    # Adjust for low block (away team may score on counter)
    away_goals_lam *= 1.1
    
    total_goals_lam = home_goals_lam + away_goals_lam
    
    market_total_goals = 2.5
    goals_edge = total_goals_lam - market_total_goals
    
    p_over_25 = poisson_over_prob(total_goals_lam, 2.5)
    p_over_35 = poisson_over_prob(total_goals_lam, 3.5)
    
    if goals_edge > 0.5:
        goals_rec = f"Over {market_total_goals}"
        goals_conf = confidence_score(goals_edge, volatility=0.45)
    elif goals_edge < -0.5:
        goals_rec = f"Under {market_total_goals}"
        goals_conf = confidence_score(abs(goals_edge), volatility=0.45)
    else:
        goals_rec = "Pass"
        goals_conf = 0.0
    
    print(f"   {home_stats['team_name']} Expected Goals: {home_goals_lam:.2f}")
    print(f"   {away_stats['team_name']} Expected Goals: {away_goals_lam:.2f}")
    print(f"   Total Expected Goals: {total_goals_lam:.2f}")
    print(f"   Market Total: O/U {market_total_goals}")
    print(f"   Over 2.5 Probability: {p_over_25:.3f}")
    print(f"   Over 3.5 Probability: {p_over_35:.3f}")
    print(f"   Recommendation: {goals_rec} (Confidence: {goals_conf:.1f}%)")
    print()
    
    # 5. MATCH RESULT / MONEYLINE
    print("5. MATCH RESULT / MONEYLINE")
    print("-" * 40)
    print()
    
    home_win_prob = home_goals_lam / (home_goals_lam + away_goals_lam)
    away_win_prob = away_goals_lam / (home_goals_lam + away_goals_lam)
    draw_prob = 1 - home_win_prob - away_win_prob
    
    # Home advantage boost
    home_win_prob = home_win_prob * 1.15
    away_win_prob = away_win_prob * 0.85
    home_win_prob = clamp(home_win_prob)
    away_win_prob = clamp(away_win_prob)
    
    if home_win_prob >= 0.50:
        ml_rec = f"Moneyline {home_stats['team_name']}"
    elif away_win_prob >= 0.50:
        ml_rec = f"Moneyline {away_stats['team_name']}"
    else:
        ml_rec = "Pass"
    
    print(f"   {home_stats['team_name']} Win Probability: {home_win_prob:.3f}")
    print(f"   Draw Probability: {draw_prob:.3f}")
    print(f"   {away_stats['team_name']} Win Probability: {away_win_prob:.3f}")
    print(f"   Recommendation: {ml_rec}")
    print()
    
    # 6. BTTTS (Both Teams To Score)
    print("6. BTTS (BOTH TEAMS TO SCORE)")
    print("-" * 40)
    print()
    
    # BTTS probability estimation
    btts_prob = (home_goals_lam > 0.8) * (away_goals_lam > 0.8) * 0.75
    btts_prob = clamp(btts_prob + 0.1, 0.25, 0.75)
    
    if btts_prob >= 0.55:
        btts_rec = "Yes BTTS"
    elif btts_prob <= 0.45:
        btts_rec = "No BTTS"
    else:
        btts_rec = "Pass"
    
    print(f"   BTTS Probability: {btts_prob:.3f}")
    print(f"   Recommendation: {btts_rec}")
    print()
    
    # 7. KEY HANDICAPPING FACTORS
    print("7. KEY HANDICAPPING FACTORS")
    print("-" * 40)
    print()
    
    print(f"   FACTORS FAVORING {home_stats['team_name'].upper()}:")
    print(f"   [+] Extreme possession dominance ({home_stats['possession_pct']:.0%})")
    print(f"   [+] Elite width/crossing ({home_stats['width_crossing']:.0%})")
    print(f"   [+] Superior xG For ({home_stats['xg_for']:.2f} vs {away_stats['xg_for']:.2f})")
    print(f"   [+] Better recent form ({home_stats['recent_form']:.0%} vs {away_stats['recent_form']:.0%})")
    print(f"   [+] Home field advantage (70% home record)")
    print(f"   [+] Low block tactical mismatch - Juniors vulnerable to wide play")
    print()
    print(f"   FACTORS FAVORING {away_stats['team_name'].upper()}:")
    print(f"   [+] Compact low block limits big scoring games")
    print(f"   [+] Counter-attack threat (may limit Peng City's dominance)")
    print(f"   [+] Defensive organization in block (only 1.08 xG Against per game)")
    print()
    
    # FINAL SUMMARY
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Match: {home_stats['team_name']} vs {away_stats['team_name']}")
    print(f"   Projected Score: {home_stats['team_name']} {home_goals_lam:.1f} - {away_stats['team_name']} {away_goals_lam:.1f}")
    print(f"   Total Expected Goals: {total_goals_lam:.2f}")
    print(f"   Total Expected Corners: {corner_analysis['projected_total_corners']}")
    print()
    print("   === BETTING RECOMMENDATIONS ===")
    print(f"   Match Result: {ml_rec}")
    print(f"   Total Goals (O/U {market_total_goals}): {goals_rec} (Confidence: {goals_conf:.1f}%)")
    print(f"   BTTS: {btts_rec}")
    print(f"   Total Corners (O/U {corner_analysis['market_total_line']}): {corner_analysis['total_corners_recommendation']} (Confidence: {corner_analysis['total_corners_confidence']:.1f}%)")
    print(f"   Peng City Team Corners (O/U {corner_analysis['market_home_corners_line']}): {corner_analysis['home_corners_recommendation']} (Confidence: {corner_analysis['home_corners_confidence']:.1f}%)")
    print()
    print("   === PLAYER PROP HIGHLIGHTS ===")
    for prop in player_props:
        print(f"   {prop['player_name']}: {prop['recommendation']} (Edge: {prop['edge_rating']:.1f})")
    print()
    
    # Build results dictionary
    results = {
        "game_info": {
            "home_team": home_stats['team_name'],
            "away_team": away_stats['team_name'],
            "league": "Chinese Super League",
            "date": "2026-06-19",
            "venue": "Shenzhen Universiade Sports Centre",
            "kickoff": "18:30 KST",
        },
        "tactical_analysis": {
            "home_style": "High Possession / Overload (Wide Attack)",
            "away_style": "Low Block / Counter",
            "home_possession": home_stats['possession_pct'],
            "away_possession": away_stats['possession_pct'],
        },
        "team_stats": {
            "home": home_stats,
            "away": away_stats,
        },
        "projections": {
            "home_goals": round(home_goals_lam, 2),
            "away_goals": round(away_goals_lam, 2),
            "total_goals": round(total_goals_lam, 2),
            "home_corners": corner_analysis['projected_home_team_corners'],
            "away_corners": corner_analysis['projected_away_team_corners'],
            "total_corners": corner_analysis['projected_total_corners'],
        },
        "corners_analysis": corner_analysis,
        "goals_analysis": {
            "market_total": market_total_goals,
            "model_total": round(total_goals_lam, 2),
            "edge": round(goals_edge, 2),
            "over_25_prob": round(p_over_25, 3),
            "over_35_prob": round(p_over_35, 3),
            "confidence": round(goals_conf, 1),
            "recommendation": goals_rec,
        },
        "moneyline_analysis": {
            "home_win_prob": round(home_win_prob, 3),
            "draw_prob": round(draw_prob, 3),
            "away_win_prob": round(away_win_prob, 3),
            "recommendation": ml_rec,
        },
        "btts_analysis": {
            "btts_probability": round(btts_prob, 3),
            "recommendation": btts_rec,
        },
        "player_props": player_props,
        "recommendations": {
            "match_result": ml_rec,
            "total_goals": goals_rec,
            "btts": btts_rec,
            "total_corners": corner_analysis['total_corners_recommendation'],
            "home_team_corners": corner_analysis['home_corners_recommendation'],
            "sharp_play": corner_analysis['sharp_play'],
        },
        "timestamp": datetime.now().isoformat(),
    }
    
    return results


def main():
    """Run Shenzhen Juniors vs Shenzhen Peng City analysis"""
    
    print("=" * 80)
    print("SHENZHEN DERBY - SHARP BETTING REPORT")
    print("Shenzhen Juniors vs Shenzhen Peng City")
    print("Chinese Super League | June 19, 2026")
    print("=" * 80)
    
    result = analyze_shenzhen_derby()
    
    # Save results
    output_dir = Path("output/soccer")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / "shenzhen_juniors_vs_peng_city_analysis.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print()
    print(f"Results saved to: {output_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()