#!/usr/bin/env python
"""
Comprehensive Analysis for KBO Match - June 9, 2026
- NC Dinos (Away) vs Kiwoom Heroes (Home)

Focus: Total Runs, Run Line, Moneyline, and Player Props
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


# KBO Team Aliases
KBO_TEAM_ALIASES = {
    "NC Dinos": "NC",
    "NC": "NC",
    "Dinos": "NC",
    "Kiwoom Heroes": "KIW",
    "Kiwoom": "KIW",
    "Heroes": "KIW",
}


def normalize_team_name(team: str) -> str:
    """Normalize KBO team name to standard abbreviation"""
    team = str(team).strip()
    return KBO_TEAM_ALIASES.get(team, team.upper())


# ============================================================================
# KBO-SPECIFIC CONFIGURATION
# ============================================================================

# KBO League averages and characteristics
KBO_CONFIG = {
    'avg_runs_per_game': 9.8,  # KBO is higher scoring than MLB
    'avg_hits_per_game': 10.5,
    'avg_home_runs_per_game': 1.8,
    'park_factors': {
        'Changwon NC Park': 1.03,
        'Gocheok Sky Dome': 0.98,  # Slightly pitcher-friendly (dome)
    },
    'home_advantage': 0.35,  # Runs added for home team
}


def get_team_stats(team: str) -> Dict[str, Any]:
    """
    Get estimated team statistics for KBO teams.
    In production, this would pull from a real database.
    """
    # Kiwoom Heroes (Home) - Strong team, good pitching, playing at dome
    if team in ["KIW", "Kiwoom Heroes", "Kiwoom", "Heroes"]:
        return {
            'team_name': 'Kiwoom Heroes',
            'abbreviation': 'KIW',
            'runs_per_game': 5.6,
            'runs_allowed_per_game': 4.5,
            'batting_avg': 0.278,
            'on_base_pct': 0.348,
            'slugging_pct': 0.438,
            'ops': 0.786,
            'home_runs_per_game': 1.15,
            'strikeouts_per_game': 7.6,
            'walks_per_game': 3.7,
            'hits_per_game': 9.9,
            'era': 4.15,
            'whip': 1.30,
            'quality_start_pct': 0.46,
            'bullpen_era': 3.85,
            'recent_form': 0.62,  # Win % in last 10
            'home_record': 0.68,  # Home win %
            'vs_opponent_record': 0.55,  # Season series record
        }
    # NC Dinos (Away) - Decent team, average pitching, struggling on road
    elif team in ["NC", "NC Dinos", "Dinos"]:
        return {
            'team_name': 'NC Dinos',
            'abbreviation': 'NC',
            'runs_per_game': 5.0,
            'runs_allowed_per_game': 5.2,
            'batting_avg': 0.270,
            'on_base_pct': 0.335,
            'slugging_pct': 0.415,
            'ops': 0.750,
            'home_runs_per_game': 1.0,
            'strikeouts_per_game': 8.0,
            'walks_per_game': 3.4,
            'hits_per_game': 9.4,
            'era': 4.85,
            'whip': 1.42,
            'quality_start_pct': 0.36,
            'bullpen_era': 4.55,
            'recent_form': 0.48,  # Win % in last 10
            'away_record': 0.42,  # Away win %
            'vs_opponent_record': 0.45,  # Season series record
        }
    else:
        # Default stats
        return {
            'team_name': team,
            'abbreviation': team[:3].upper(),
            'runs_per_game': 4.8,
            'runs_allowed_per_game': 4.8,
            'batting_avg': 0.265,
            'on_base_pct': 0.330,
            'slugging_pct': 0.410,
            'ops': 0.740,
            'home_runs_per_game': 1.0,
            'strikeouts_per_game': 8.0,
            'walks_per_game': 3.5,
            'hits_per_game': 9.5,
            'era': 4.80,
            'whip': 1.42,
            'quality_start_pct': 0.35,
            'bullpen_era': 4.60,
            'recent_form': 0.50,
            'home_record': 0.50,
            'away_record': 0.45,
            'vs_opponent_record': 0.50,
        }


def project_team_runs(home_stats: Dict, away_stats: Dict) -> tuple:
    """
    Project runs for both teams using a comprehensive model.
    
    Returns:
        Tuple of (home_runs_proj, away_runs_proj, total_proj)
    """
    # Home team projected runs
    # Based on: own offense vs opponent pitching + home advantage
    home_offense_strength = home_stats['runs_per_game'] / KBO_CONFIG['avg_runs_per_game'] * 2
    away_pitching_weakness = away_stats['era'] / 4.50  # League avg ERA ~4.50
    
    home_lam = (home_offense_strength * 0.4 + away_pitching_weakness * 0.4 + 1.0) * 2.2
    home_lam += KBO_CONFIG['home_advantage']
    
    # Adjust for recent form
    home_lam *= (0.9 + home_stats['recent_form'] * 0.2)
    
    # Away team projected runs
    away_offense_strength = away_stats['runs_per_game'] / KBO_CONFIG['avg_runs_per_game'] * 2
    home_pitching_weakness = home_stats['era'] / 4.50
    
    away_lam = (away_offense_strength * 0.4 + home_pitching_weakness * 0.4 + 1.0) * 2.0
    # Away disadvantage
    away_lam *= 0.92
    
    # Adjust for recent form
    away_lam *= (0.9 + away_stats['recent_form'] * 0.2)
    
    total_lam = home_lam + away_lam
    
    return home_lam, away_lam, total_lam


def calculate_win_probability(home_lam: float, away_lam: float) -> Dict[str, float]:
    """Calculate win/draw/loss probabilities"""
    # Simple model based on expected runs
    total = home_lam + away_lam
    if total == 0:
        return {'home': 0.5, 'away': 0.5}
    
    home_win_prob = home_lam / total
    # Apply home field advantage
    home_win_prob = home_win_prob * 0.85 + 0.12
    away_win_prob = 1 - home_win_prob
    
    return {
        'home': clamp(home_win_prob),
        'away': clamp(away_win_prob),
    }


def project_run_line(home_lam: float, away_lam: float, line: float = -1.5) -> Dict[str, Any]:
    """Project run line (spread) outcome"""
    spread = home_lam - away_lam
    edge = spread - line
    
    # Calculate probability using normal distribution approximation
    std_dev = 3.5  # Typical baseball game std dev
    z_score = edge / std_dev
    prob = sigmoid(z_score * 1.5)
    
    return {
        'model_spread': round(spread, 2),
        'market_line': line,
        'edge': round(edge, 2),
        'probability': round(prob, 3),
    }


def project_player_props(home_stats: Dict, away_stats: Dict) -> Dict[str, Any]:
    """Generate player prop projections"""
    
    # Top hitter props (simulated for star players)
    home_top_hitter = {
        'player_name': 'Kiwoom Star Hitter',
        'team': 'KIW',
        'avg': home_stats['batting_avg'],
        'slg': home_stats['slugging_pct'],
        'hr_rate': home_stats['home_runs_per_game'] / 9,
    }
    
    away_top_hitter = {
        'player_name': 'NC Star Hitter',
        'team': 'NC',
        'avg': away_stats['batting_avg'],
        'slg': away_stats['slugging_pct'],
        'hr_rate': away_stats['home_runs_per_game'] / 9,
    }
    
    # Total Bases projections
    home_tb_proj = home_top_hitter['slg'] * 4.0  # 4 plate appearances
    away_tb_proj = away_top_hitter['slg'] * 3.8
    
    # Hits projections
    home_hits_proj = home_top_hitter['avg'] * 4.0
    away_hits_proj = away_top_hitter['avg'] * 3.8
    
    return {
        'home_top_hitter': {
            'total_bases': {
                'projection': round(home_tb_proj, 2),
                'line': 1.5,
                'edge': round(home_tb_proj - 1.5, 2),
                'lean': 'Over' if home_tb_proj > 1.5 else 'Under',
            },
            'hits': {
                'projection': round(home_hits_proj, 2),
                'line': 0.5,
                'edge': round(home_hits_proj - 0.5, 2),
                'lean': 'Over' if home_hits_proj > 0.5 else 'Under',
            },
        },
        'away_top_hitter': {
            'total_bases': {
                'projection': round(away_tb_proj, 2),
                'line': 1.5,
                'edge': round(away_tb_proj - 1.5, 2),
                'lean': 'Over' if away_tb_proj > 1.5 else 'Under',
            },
            'hits': {
                'projection': round(away_hits_proj, 2),
                'line': 0.5,
                'edge': round(away_hits_proj - 0.5, 2),
                'lean': 'Over' if away_hits_proj > 0.5 else 'Under',
            },
        },
    }


def analyze_kbo_match(
    home_team: str,
    away_team: str,
    market_total: float = 9.5,
    market_spread: float = -1.5,
    venue: str = "Gocheok Sky Dome",
    date: str = "2026-06-09",
) -> Dict[str, Any]:
    """
    Comprehensive analysis for a KBO match.
    """
    home_team_normalized = normalize_team_name(home_team)
    away_team_normalized = normalize_team_name(away_team)
    
    print("=" * 80)
    print(f"KBO MATCH ANALYSIS: {home_team} vs {away_team}")
    print(f"Korean Baseball Organization - {date}")
    print(f"Venue: {venue}")
    print("=" * 80)
    print()
    
    # Get team statistics
    home_stats = get_team_stats(home_team_normalized)
    away_stats = get_team_stats(away_team_normalized)
    
    # 1. TEAM STATISTICS OVERVIEW
    print("1. TEAM STATISTICS OVERVIEW")
    print("-" * 40)
    print(f"   {home_stats['team_name']}:")
    print(f"      Runs/Game: {home_stats['runs_per_game']:.1f} | Runs Allowed: {home_stats['runs_allowed_per_game']:.1f}")
    print(f"      Batting Avg: {home_stats['batting_avg']:.3f} | OPS: {home_stats['ops']:.3f}")
    print(f"      ERA: {home_stats['era']:.2f} | WHIP: {home_stats['whip']:.2f}")
    print(f"      Recent Form: {home_stats['recent_form']:.0%} | Home Record: {home_stats['home_record']:.0%}")
    print()
    print(f"   {away_stats['team_name']}:")
    print(f"      Runs/Game: {away_stats['runs_per_game']:.1f} | Runs Allowed: {away_stats['runs_allowed_per_game']:.1f}")
    print(f"      Batting Avg: {away_stats['batting_avg']:.3f} | OPS: {away_stats['ops']:.3f}")
    print(f"      ERA: {away_stats['era']:.2f} | WHIP: {away_stats['whip']:.2f}")
    print(f"      Recent Form: {away_stats['recent_form']:.0%} | Away Record: {away_stats['away_record']:.0%}")
    print()
    
    # 2. RUN PROJECTION
    print("2. RUN PROJECTION")
    print("-" * 40)
    
    home_lam, away_lam, total_lam = project_team_runs(home_stats, away_stats)
    
    print(f"   {home_stats['team_name']} Expected Runs: {home_lam:.2f}")
    print(f"   {away_stats['team_name']} Expected Runs: {away_lam:.2f}")
    print(f"   Total Expected Runs: {total_lam:.2f}")
    print()
    
    # Over/Under probabilities
    p_over_75 = poisson_over_prob(total_lam, 7.5)
    p_over_85 = poisson_over_prob(total_lam, 8.5)
    p_over_95 = poisson_over_prob(total_lam, 9.5)
    p_over_105 = poisson_over_prob(total_lam, 10.5)
    
    print(f"   Over 7.5 Runs Probability: {p_over_75:.3f}")
    print(f"   Over 8.5 Runs Probability: {p_over_85:.3f}")
    print(f"   Over 9.5 Runs Probability: {p_over_95:.3f}")
    print(f"   Over 10.5 Runs Probability: {p_over_105:.3f}")
    print()
    
    # 3. WIN PROBABILITY
    print("3. WIN PROBABILITY")
    print("-" * 40)
    
    win_probs = calculate_win_probability(home_lam, away_lam)
    
    print(f"   {home_stats['team_name']} Win Probability: {win_probs['home']:.3f}")
    print(f"   {away_stats['team_name']} Win Probability: {win_probs['away']:.3f}")
    print()
    
    # 4. RUN LINE ANALYSIS
    print("4. RUN LINE ANALYSIS")
    print("-" * 40)
    
    run_line_proj = project_run_line(home_lam, away_lam, market_spread)
    
    print(f"   Model Spread: {run_line_proj['model_spread']:+.2f}")
    print(f"   Market Line: {run_line_proj['market_line']}")
    print(f"   Edge: {run_line_proj['edge']:+.2f}")
    print(f"   Cover Probability: {run_line_proj['probability']:.3f}")
    
    # Confidence and recommendation
    rl_confidence = confidence_score(run_line_proj['edge'], volatility=0.40)
    rl_recommendation = bet_recommendation(rl_confidence)
    print(f"   Confidence: {rl_confidence:.1f}%")
    print(f"   Recommendation: {rl_recommendation}")
    print()
    
    # 5. TOTALS ANALYSIS
    print("5. TOTALS ANALYSIS")
    print("-" * 40)
    
    totals_edge = total_lam - market_total
    
    if market_total <= 7.5:
        totals_prob = p_over_75
    elif market_total <= 8.5:
        totals_prob = p_over_85
    elif market_total <= 9.5:
        totals_prob = p_over_95
    else:
        totals_prob = p_over_105
    
    print(f"   Market Total: {market_total}")
    print(f"   Model Total: {total_lam:.2f}")
    print(f"   Edge: {totals_edge:+.2f}")
    print(f"   Over Probability: {totals_prob:.3f}")
    
    # Confidence and recommendation
    t_confidence = confidence_score(totals_edge, volatility=0.38)
    if totals_prob >= 0.57:
        t_recommendation = f"Over {market_total}"
    elif totals_prob <= 0.43:
        t_recommendation = f"Under {market_total}"
    else:
        t_recommendation = "Pass"
    
    print(f"   Confidence: {t_confidence:.1f}%")
    print(f"   Recommendation: {t_recommendation}")
    print()
    
    # 6. MONEYLINE ANALYSIS
    print("6. MONEYLINE ANALYSIS")
    print("-" * 40)
    
    home_ml_prob = win_probs['home']
    away_ml_prob = win_probs['away']
    
    print(f"   {home_stats['team_name']} ML Probability: {home_ml_prob:.3f}")
    print(f"   {away_stats['team_name']} ML Probability: {away_ml_prob:.3f}")
    
    if home_ml_prob >= 0.57:
        ml_recommendation = f"Moneyline {home_stats['team_name']}"
    elif away_ml_prob >= 0.57:
        ml_recommendation = f"Moneyline {away_stats['team_name']}"
    else:
        ml_recommendation = "Pass"
    
    print(f"   Recommendation: {ml_recommendation}")
    print()
    
    # 7. PLAYER PROPS
    print("7. PLAYER PROPS PROJECTIONS")
    print("-" * 40)
    
    props = project_player_props(home_stats, away_stats)
    
    print(f"   {home_stats['team_name']} Top Hitter:")
    print(f"      Total Bases: {props['home_top_hitter']['total_bases']['projection']:.2f} (Line: {props['home_top_hitter']['total_bases']['line']})")
    print(f"      Hits: {props['home_top_hitter']['hits']['projection']:.2f} (Line: {props['home_top_hitter']['hits']['line']})")
    print()
    print(f"   {away_stats['team_name']} Top Hitter:")
    print(f"      Total Bases: {props['away_top_hitter']['total_bases']['projection']:.2f} (Line: {props['away_top_hitter']['total_bases']['line']})")
    print(f"      Hits: {props['away_top_hitter']['hits']['projection']:.2f} (Line: {props['away_top_hitter']['hits']['line']})")
    print()
    
    # 8. KEY HANDICAPPING FACTORS
    print("8. KEY HANDICAPPING FACTORS")
    print("-" * 40)
    print()
    
    print(f"   FACTORS FAVORING {home_stats['team_name'].upper()}:")
    if home_stats['runs_per_game'] > away_stats['runs_per_game']:
        print(f"   [+] Better offense ({home_stats['runs_per_game']:.1f} vs {away_stats['runs_per_game']:.1f} R/G)")
    if home_stats['era'] < away_stats['era']:
        print(f"   [+] Better pitching (ERA {home_stats['era']:.2f} vs {away_stats['era']:.2f})")
    if home_stats['ops'] > away_stats['ops']:
        print(f"   [+] Higher OPS ({home_stats['ops']:.3f} vs {away_stats['ops']:.3f})")
    if home_stats['recent_form'] > away_stats['recent_form']:
        print(f"   [+] Better recent form ({home_stats['recent_form']:.0%} vs {away_stats['recent_form']:.0%})")
    print(f"   [+] Home field advantage")
    print()
    
    print(f"   FACTORS FAVORING {away_stats['team_name'].upper()}:")
    if away_stats['runs_per_game'] > home_stats['runs_per_game']:
        print(f"   [+] Better offense ({away_stats['runs_per_game']:.1f} vs {home_stats['runs_per_game']:.1f} R/G)")
    if away_stats['era'] < home_stats['era']:
        print(f"   [+] Better pitching (ERA {away_stats['era']:.2f} vs {home_stats['era']:.2f})")
    if away_stats['ops'] > home_stats['ops']:
        print(f"   [+] Higher OPS ({away_stats['ops']:.3f} vs {home_stats['ops']:.3f})")
    if away_stats['recent_form'] > home_stats['recent_form']:
        print(f"   [+] Better recent form ({away_stats['recent_form']:.0%} vs {home_stats['recent_form']:.0%})")
    print()
    
    # FINAL SUMMARY
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Match: {home_stats['team_name']} vs {away_stats['team_name']}")
    print(f"   Projected Score: {home_stats['team_name']} {home_lam:.1f} - {away_stats['team_name']} {away_lam:.1f}")
    print(f"   Total Expected Runs: {total_lam:.2f}")
    print()
    print("   === BETTING RECOMMENDATIONS ===")
    print(f"   Run Line ({market_spread:+.1f}): {rl_recommendation} (Confidence: {rl_confidence:.1f}%)")
    print(f"   Total (O/U {market_total}): {t_recommendation} (Confidence: {t_confidence:.1f}%)")
    print(f"   Moneyline: {ml_recommendation}")
    print()
    
    # Build results dictionary
    results = {
        "game_info": {
            "home_team": home_stats['team_name'],
            "away_team": away_stats['team_name'],
            "league": "KBO",
            "date": date,
            "venue": venue,
        },
        "team_stats": {
            "home": home_stats,
            "away": away_stats,
        },
        "projections": {
            "home_runs": round(home_lam, 2),
            "away_runs": round(away_lam, 2),
            "total_runs": round(total_lam, 2),
            "home_win_prob": round(win_probs['home'], 3),
            "away_win_prob": round(win_probs['away'], 3),
        },
        "totals_analysis": {
            "over_75_prob": round(p_over_75, 3),
            "over_85_prob": round(p_over_85, 3),
            "over_95_prob": round(p_over_95, 3),
            "over_105_prob": round(p_over_105, 3),
            "market_total": market_total,
            "model_total": round(total_lam, 2),
            "edge": round(totals_edge, 2),
            "over_probability": round(totals_prob, 3),
            "confidence": round(t_confidence, 1),
            "recommendation": t_recommendation,
        },
        "run_line_analysis": {
            "model_spread": run_line_proj['model_spread'],
            "market_line": run_line_proj['market_line'],
            "edge": run_line_proj['edge'],
            "cover_probability": run_line_proj['probability'],
            "confidence": round(rl_confidence, 1),
            "recommendation": rl_recommendation,
        },
        "moneyline_analysis": {
            "home_win_prob": round(home_ml_prob, 3),
            "away_win_prob": round(away_ml_prob, 3),
            "recommendation": ml_recommendation,
        },
        "player_props": props,
        "recommendations": {
            "run_line": rl_recommendation,
            "total": t_recommendation,
            "moneyline": ml_recommendation,
        },
        "timestamp": datetime.now().isoformat(),
    }
    
    return results


def main():
    """Run KBO match analysis for Kiwoom Heroes vs NC Dinos"""
    
    print("=" * 80)
    print("KBO MATCH COMPREHENSIVE ANALYSIS")
    print("June 9, 2026")
    print("=" * 80)
    
    # Run analysis - Kiwoom Heroes is HOME team but UNDERDOG (+1.5)
    # NC Dinos is the favorite on the road
    result = analyze_kbo_match(
        home_team="Kiwoom Heroes",
        away_team="NC Dinos",
        market_total=9.5,
        market_spread=1.5,  # Kiwoom is +1.5 underdog at home
        venue="Gocheok Sky Dome",
    )
    
    # Save results
    output_dir = Path("output/baseball/kbo")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / "nc_dinos_vs_kiwoom_heroes_analysis.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"Results saved to: {output_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()