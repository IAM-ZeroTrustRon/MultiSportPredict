#!/usr/bin/env python
"""
Comprehensive Analysis for MLB Game
- Atlanta Braves vs Pittsburgh Pirates
MLB - June 7, 2026 at 1:00 PM ET
Includes: Full Game, Player Props Analysis
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Import MLB module functions
from mlb.mlb_module import (
    project_k_prop,
    project_hr_prop,
    project_total_bases,
    project_hits,
    project_walks,
    project_rbis,
    WeatherContext,
)
from core.confidence_engine import confidence_score, bet_recommendation, get_volatility


def analyze_mlb_match(
    home_team, away_team, home_data, away_data, market_data, venue,
    date="2026-06-07", league="MLB"
):
    """Analyze a single MLB match and return results"""

    print("=" * 80)
    print(f"COMPREHENSIVE MATCH ANALYSIS: {home_team} vs {away_team}")
    print(f"{league} - {date}")
    print(f"Venue: {venue}")
    print("=" * 80)
    print()

    # 1. TEAM OFFENSIVE/DEFENSIVE ANALYSIS
    print("1. TEAM OFFENSIVE/DEFENSIVE ANALYSIS")
    print("-" * 40)

    home_net = home_data['runs_per_game'] - home_data['runs_allowed_per_game']
    away_net = away_data['runs_per_game'] - away_data['runs_allowed_per_game']

    print(f"   {home_team}:")
    print(f"      Runs/Game: {home_data['runs_per_game']:.2f} | Runs Allowed/Game: {home_data['runs_allowed_per_game']:.2f} | Net: {home_net:+.2f}")
    print(f"      Team ERA: {home_data['team_era']:.2f} | Team OPS: {home_data['team_ops']:.3f}")
    print()
    print(f"   {away_team}:")
    print(f"      Runs/Game: {away_data['runs_per_game']:.2f} | Runs Allowed/Game: {away_data['runs_allowed_per_game']:.2f} | Net: {away_net:+.2f}")
    print(f"      Team ERA: {away_data['team_era']:.2f} | Team OPS: {away_data['team_ops']:.3f}")
    print()

    # 2. PITCHING MATCHUP ANALYSIS
    print("2. PITCHING MATCHUP ANALYSIS")
    print("-" * 40)

    home_pitcher = home_data.get('starting_pitcher', {})
    away_pitcher = away_data.get('starting_pitcher', {})

    print(f"   {home_team} Starter: {home_pitcher.get('name', 'TBD')}")
    print(f"      ERA: {home_pitcher.get('era', 0.00):.2f} | K/9: {home_pitcher.get('k_per_9', 0.0):.1f} | WHIP: {home_pitcher.get('whip', 0.00):.2f}")
    print(f"      K Rate: {home_pitcher.get('k_rate', 0.0):.1%}")
    print()
    print(f"   {away_team} Starter: {away_pitcher.get('name', 'TBD')}")
    print(f"      ERA: {away_pitcher.get('era', 0.00):.2f} | K/9: {away_pitcher.get('k_per_9', 0.0):.1f} | WHIP: {away_pitcher.get('whip', 0.00):.2f}")
    print(f"      K Rate: {away_pitcher.get('k_rate', 0.0):.1%}")
    print()

    # 3. LINEUP ANALYSIS
    print("3. LINEUP ANALYSIS")
    print("-" * 40)

    print(f"   {home_team} Active Roster:")
    print(f"      Infielders: {', '.join(home_data.get('infielders', []))}")
    print(f"      Outfielders: {', '.join(home_data.get('outfielders', []))}")
    print(f"      Catchers/DH: {', '.join(home_data.get('catchers_dh', []))}")
    print()
    print(f"   {away_team} Active Roster:")
    print(f"      Infielders: {', '.join(away_data.get('infielders', []))}")
    print(f"      Outfielders: {', '.join(away_data.get('outfielders', []))}")
    print(f"      Catchers/DH: {', '.join(away_data.get('catchers_dh', []))}")
    print()

    # 4. PROJECTED TOTAL RUNS CALCULATION
    print("4. PROJECTED TOTAL RUNS")
    print("-" * 40)

    # Calculate projected runs based on team offense vs pitcher defense
    home_pitcher_era = home_pitcher.get('era', 4.00)
    away_pitcher_era = away_pitcher.get('era', 4.00)

    # Base projection from team scoring and pitcher ERA
    home_proj_runs = (home_data['runs_per_game'] + away_pitcher_era) / 2
    away_proj_runs = (away_data['runs_per_game'] + home_pitcher_era) / 2

    # Adjust for park factor and weather
    park_factor = home_data.get('park_factor', 1.0)
    weather_adj = home_data.get('weather_adjustment', 1.0)

    home_proj_runs *= park_factor * weather_adj
    away_proj_runs *= park_factor * weather_adj

    projected_total = home_proj_runs + away_proj_runs

    print(f"   {home_team} Projected Runs: {home_proj_runs:.2f}")
    print(f"   {away_team} Projected Runs: {away_proj_runs:.2f}")
    print(f"   Projected Total: {projected_total:.2f}")
    print(f"   Market Total: {market_data['total']}")
    print()

    # 5. MONEYLINE ANALYSIS
    print("5. MONEYLINE ANALYSIS")
    print("-" * 40)

    # Calculate implied probabilities from moneyline
    home_ml = market_data['moneyline_home']
    away_ml = market_data['moneyline_away']

    if home_ml < 0:
        home_implied = abs(home_ml) / (abs(home_ml) + 100)
    else:
        home_implied = 100 / (home_ml + 100)

    if away_ml < 0:
        away_implied = abs(away_ml) / (abs(away_ml) + 100)
    else:
        away_implied = 100 / (away_ml + 100)

    # Calculate model win probability based on projected runs
    run_diff = home_proj_runs - away_proj_runs
    # Simple logistic model for win probability
    model_home_prob = 1 / (1 + 2.71828 ** (-0.3 * run_diff))

    print(f"   {home_team} Moneyline: {home_ml:+d}")
    print(f"      Implied Probability: {home_implied:.1%}")
    print(f"      Model Probability: {model_home_prob:.1%}")
    print(f"      Edge: {(model_home_prob - home_implied):+.1%}")
    print()
    print(f"   {away_team} Moneyline: {away_ml:+d}")
    print(f"      Implied Probability: {away_implied:.1%}")
    print(f"      Model Probability: {(1 - model_home_prob):.1%}")
    print(f"      Edge: {((1 - model_home_prob) - away_implied):+.1%}")
    print()

    # 6. RUN LINE ANALYSIS
    print("6. RUN LINE ANALYSIS")
    print("-" * 40)

    run_line = market_data['run_line']
    home_rl_odds = market_data['run_line_home_odds']
    away_rl_odds = market_data['run_line_away_odds']

    print(f"   Run Line: {home_team} {run_line} ({home_rl_odds:+d}) | {away_team} {abs(run_line)} ({away_rl_odds:+d})")
    print(f"   Projected Margin: {run_diff:+.2f}")

    # Simple run line probability estimation
    if run_diff > abs(run_line):
        home_rl_prob = 0.65  # Favor covering
    elif run_diff > 0:
        home_rl_prob = 0.45  # Might not cover
    else:
        home_rl_prob = 0.35  # Unlikely to cover

    print(f"   Model {home_team} Cover Probability: {home_rl_prob:.1%}")
    print()

    # 7. CONFIDENCE SCORING
    print("7. CONFIDENCE SCORING")
    print("-" * 40)

    total_volatility = get_volatility("mlb_totals")
    total_edge = projected_total - market_data['total']
    total_confidence = confidence_score(total_edge, total_volatility)
    total_recommendation = bet_recommendation(total_confidence, "mlb_totals")

    side_volatility = get_volatility("mlb_sides")
    side_edge = run_diff
    side_confidence = confidence_score(abs(side_edge), side_volatility)
    side_recommendation = bet_recommendation(side_confidence, "mlb_sides")

    print(f"   Total Bet ({'Over' if projected_total > market_data['total'] else 'Under'} {market_data['total']}):")
    print(f"      Edge: {total_edge:+.2f}")
    print(f"      Confidence: {total_confidence:.1f}%")
    print(f"      Recommendation: {total_recommendation}")
    print()
    print(f"   Side Bet ({home_team} Moneyline):")
    print(f"      Edge: {side_edge:+.2f} runs")
    print(f"      Confidence: {side_confidence:.1f}%")
    print(f"      Recommendation: {side_recommendation}")
    print()

    # 8. K PROPS FOR PITCHERS
    print("8. PITCHER STRIKEOUT PROPS")
    print("-" * 40)

    # Project K props for both pitchers
    home_k_prop = project_k_prop(
        pitcher_stats={
            "k_rate": home_pitcher.get('k_rate', 0.22),
            "handedness": home_pitcher.get('handedness', 'R'),
            "innings_proj": home_pitcher.get('innings_proj', 5.5),
            "prop_line": 5.5
        },
        opponent_stats={
            "k_rate_vs_R": away_data.get('k_rate_vs_rhp', 0.22),
            "k_rate_vs_L": away_data.get('k_rate_vs_lhp', 0.22),
            "k_rate": away_data.get('team_k_rate', 0.22)
        },
        umpire_stats=None,
        park_factor=park_factor
    )

    away_k_prop = project_k_prop(
        pitcher_stats={
            "k_rate": away_pitcher.get('k_rate', 0.22),
            "handedness": away_pitcher.get('handedness', 'R'),
            "innings_proj": away_pitcher.get('innings_proj', 5.5),
            "prop_line": 5.5
        },
        opponent_stats={
            "k_rate_vs_R": home_data.get('k_rate_vs_rhp', 0.22),
            "k_rate_vs_L": home_data.get('k_rate_vs_lhp', 0.22),
            "k_rate": home_data.get('team_k_rate', 0.22)
        },
        umpire_stats=None,
        park_factor=park_factor
    )

    print(f"   {home_pitcher.get('name', 'Home Pitcher')}: {home_k_prop['projection']:.1f} Ks (Line: {home_k_prop['line']}) -> {home_k_prop['lean']}")
    print(f"   {away_pitcher.get('name', 'Away Pitcher')}: {away_k_prop['projection']:.1f} Ks (Line: {away_k_prop['line']}) -> {away_k_prop['lean']}")
    print()

    # 9. HR PROPS FOR KEY HITTERS
    print("9. HOME RUN PROPS - KEY HITTERS")
    print("-" * 40)

    weather = {
        "temperature": home_data.get('temperature', 75),
        "wind_speed": home_data.get('wind_speed', 8),
        "wind_direction_factor": home_data.get('wind_direction', 0.5)
    }

    # Project HR props for key hitters from each team
    key_hitters = [
        # Braves key hitters
        {"name": "Ronald Acuña Jr.", "team": "ATL", "hr_rate": 0.06, "barrel_rate": 0.12, "hard_hit_rate": 0.45},
        {"name": "Matt Olson", "team": "ATL", "hr_rate": 0.07, "barrel_rate": 0.14, "hard_hit_rate": 0.48},
        {"name": "Austin Riley", "team": "ATL", "hr_rate": 0.05, "barrel_rate": 0.11, "hard_hit_rate": 0.42},
        {"name": "Marcell Ozuna", "team": "ATL", "hr_rate": 0.05, "barrel_rate": 0.10, "hard_hit_rate": 0.40},
        # Pirates key hitters
        {"name": "Bryan Reynolds", "team": "PIT", "hr_rate": 0.04, "barrel_rate": 0.09, "hard_hit_rate": 0.38},
        {"name": "Oneil Cruz", "team": "PIT", "hr_rate": 0.05, "barrel_rate": 0.11, "hard_hit_rate": 0.44},
        {"name": "Ryan O'Hearn", "team": "PIT", "hr_rate": 0.04, "barrel_rate": 0.08, "hard_hit_rate": 0.36},
    ]

    hr_props = []
    for hitter in key_hitters:
        pitcher = away_pitcher if hitter['team'] == 'ATL' else home_pitcher
        hr_proj = project_hr_prop(
            hitter_stats={
                "hr_rate": hitter['hr_rate'],
                "barrel_rate": hitter['barrel_rate'],
                "hard_hit_rate": hitter['hard_hit_rate'],
            },
            pitcher_stats={
                "handedness": pitcher.get('handedness', 'R'),
                "hr_per_9": pitcher.get('hr_per_9', 1.0),
            },
            park_factor=park_factor,
            weather=weather
        )
        hr_props.append({
            "player_name": hitter['name'],
            "team": hitter['team'],
            "hr_probability": hr_proj['hr_probability'],
            "lean": hr_proj['lean']
        })
        print(f"   {hitter['name']} ({hitter['team']}): {hr_proj['hr_probability']:.1%} HR probability -> {hr_proj['lean']}")

    print()

    # 10. PLAYER PROPS - TOTAL BASES & HITS
    print("10. PLAYER PROPS - TOTAL BASES & HITS")
    print("-" * 40)

    player_props = []

    # Key players for props
    prop_players = [
        {"name": "Ronald Acuña Jr.", "team": "ATL", "avg": 0.285, "slg": 0.480, "pa_proj": 4.5},
        {"name": "Matt Olson", "team": "ATL", "avg": 0.265, "slg": 0.510, "pa_proj": 4.2},
        {"name": "Austin Riley", "team": "ATL", "avg": 0.270, "slg": 0.460, "pa_proj": 4.3},
        {"name": "Marcell Ozuna", "team": "ATL", "avg": 0.275, "slg": 0.470, "pa_proj": 4.0},
        {"name": "Bryan Reynolds", "team": "PIT", "avg": 0.275, "slg": 0.440, "pa_proj": 4.3},
        {"name": "Oneil Cruz", "team": "PIT", "avg": 0.255, "slg": 0.450, "pa_proj": 4.0},
        {"name": "Ryan O'Hearn", "team": "PIT", "avg": 0.260, "slg": 0.420, "pa_proj": 3.8},
    ]

    for player in prop_players:
        # Total Bases prop
        tb_prop = project_total_bases({
            "player_name": player['name'],
            "team": player['team'],
            "slg": player['slg'],
            "avg": player['avg'],
            "pa_proj": player['pa_proj'],
            "prop_line": 1.5
        })

        # Hits prop
        hits_prop = project_hits({
            "player_name": player['name'],
            "team": player['team'],
            "avg": player['avg'],
            "pa_proj": player['pa_proj'],
            "prop_line": 0.5
        })

        player_props.extend([tb_prop, hits_prop])

        print(f"   {player['name']} ({player['team']}):")
        print(f"      Total Bases: {tb_prop['projection']:.1f} (Line: {tb_prop['line']}) -> {tb_prop['lean']}")
        print(f"      Hits: {hits_prop['projection']:.1f} (Line: {hits_prop['line']}) -> {hits_prop['lean']}")

    print()

    # 11. FINAL PROJECTION & RECOMMENDATION
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()

    # Determine confidence level
    if abs(model_home_prob - home_implied) > 0.10:
        confidence = "HIGH"
    elif abs(model_home_prob - home_implied) > 0.05:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Moneyline recommendation
    if model_home_prob > home_implied + 0.05:
        ml_recommendation = f"LEAN {home_team} ML ({home_ml:+d})"
    elif (1 - model_home_prob) > away_implied + 0.05:
        ml_recommendation = f"LEAN {away_team} ML ({away_ml:+d})"
    else:
        ml_recommendation = "NO STRONG MONEYLINE LEAN"

    # Total recommendation
    if projected_total > market_data['total'] + 0.5:
        total_rec = f"LEAN OVER {market_data['total']}"
    elif projected_total < market_data['total'] - 0.5:
        total_rec = f"LEAN UNDER {market_data['total']}"
    else:
        total_rec = "NO STRONG TOTAL LEAN"

    print(f"   PROJECTED SCORE: {home_team} {home_proj_runs:.1f} - {away_team} {away_proj_runs:.1f}")
    print(f"   PROJECTED TOTAL: {projected_total:.2f} (Market: {market_data['total']})")
    print(f"   PROJECTED MARGIN: {run_diff:+.2f}")
    print()
    print(f"   WIN PROBABILITIES:")
    print(f"      {home_team}: {model_home_prob:.1%}")
    print(f"      {away_team}: {(1 - model_home_prob):.1%}")
    print()
    print(f"   BETTING RECOMMENDATIONS:")
    print(f"      Moneyline: {ml_recommendation}")
    print(f"      Total: {total_rec}")
    print(f"      Run Line: {'LEAN' if abs(run_diff) > 1.5 else 'NO LEAN'} {'Home' if run_diff > 0 else 'Away'} -1.5")
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
            "venue": venue,
            "game_time": "1:00 PM ET"
        },
        "team_metrics": {
            "home": {
                "runs_per_game": home_data['runs_per_game'],
                "runs_allowed_per_game": home_data['runs_allowed_per_game'],
                "team_era": home_data['team_era'],
                "team_ops": home_data['team_ops'],
                "starting_pitcher": home_pitcher
            },
            "away": {
                "runs_per_game": away_data['runs_per_game'],
                "runs_allowed_per_game": away_data['runs_allowed_per_game'],
                "team_era": away_data['team_era'],
                "team_ops": away_data['team_ops'],
                "starting_pitcher": away_pitcher
            }
        },
        "market_data": {
            "moneyline_home": home_ml,
            "moneyline_away": away_ml,
            "run_line": run_line,
            "run_line_home_odds": home_rl_odds,
            "run_line_away_odds": away_rl_odds,
            "total": market_data['total'],
        },
        "projections": {
            "home_runs": round(home_proj_runs, 2),
            "away_runs": round(away_proj_runs, 2),
            "total_runs": round(projected_total, 2),
            "run_differential": round(run_diff, 2),
            "home_win_probability": round(model_home_prob, 3),
            "away_win_probability": round(1 - model_home_prob, 3),
        },
        "recommendations": {
            "moneyline": ml_recommendation,
            "total": total_rec,
            "run_line": f"{'LEAN' if abs(run_diff) > 1.5 else 'NO LEAN'} {'Home' if run_diff > 0 else 'Away'} -1.5",
            "confidence": confidence,
        },
        "confidence_scores": {
            "total": {
                "score": total_confidence,
                "recommendation": total_recommendation,
                "volatility": total_volatility,
                "edge": round(total_edge, 2)
            },
            "side": {
                "score": side_confidence,
                "recommendation": side_recommendation,
                "volatility": side_volatility,
                "edge": round(side_edge, 2)
            }
        },
        "pitcher_props": {
            "home": home_k_prop,
            "away": away_k_prop,
        },
        "hr_props": hr_props,
        "player_props": player_props,
        "timestamp": datetime.now().isoformat()
    }

    return results


def run_braves_pirates_analysis():
    """Run comprehensive analysis for Braves vs Pirates"""

    print("=" * 80)
    print("COMPREHENSIVE ANALYSIS: ATLANTA BRAVES vs PITTSBURGH PIRATES")
    print("MLB - June 7, 2026 at 1:00 PM ET")
    print("=" * 80)
    print()

    # Pittsburgh Pirates (Home) - Based on provided roster
    home_data = {
        'runs_per_game': 4.35,           # Pirates season average
        'runs_allowed_per_game': 4.82,    # Pirates season average
        'team_era': 4.45,                 # Pirates team ERA
        'team_ops': 0.710,                # Pirates team OPS
        'team_k_rate': 0.23,              # Pirates strikeout rate
        'k_rate_vs_rhp': 0.24,            # vs Right-handed pitchers
        'k_rate_vs_lhp': 0.22,            # vs Left-handed pitchers
        'park_factor': 0.98,              # PNC Park slightly pitcher-friendly
        'temperature': 75,                # Game time temperature
        'wind_speed': 8,                  # Wind speed mph
        'wind_direction': 0.3,            # Wind factor (0-1)

        # Active Roster
        'infielders': ['Nick Gonzales (3B/2B)', 'Spencer Horwitz (1B)', 'Jared Triolo (SS)', 'Tyler Callihan (3B)', 'Ryan O\'Hearn (1B/RF)'],
        'outfielders': ['Bryan Reynolds (LF)', 'Oneil Cruz (CF)', 'Brandon Lowe (DH)'],
        'catchers_dh': ['Endy Rodríguez', 'Henry Davis'],

        # Starting Pitcher (estimated - would need actual starter info)
        'starting_pitcher': {
            'name': 'Paul Skenes',  # Assuming ace starter
            'era': 2.85,
            'k_per_9': 11.2,
            'whip': 1.05,
            'k_rate': 0.32,
            'handedness': 'R',
            'innings_proj': 6.0,
            'hr_per_9': 0.7,
        }
    }

    # Atlanta Braves (Away) - Based on provided roster
    away_data = {
        'runs_per_game': 5.12,           # Braves season average
        'runs_allowed_per_game': 4.25,    # Braves season average
        'team_era': 3.95,                 # Braves team ERA
        'team_ops': 0.765,                # Braves team OPS
        'team_k_rate': 0.21,              # Braves strikeout rate
        'k_rate_vs_rhp': 0.20,            # vs Right-handed pitchers
        'k_rate_vs_lhp': 0.22,            # vs Left-handed pitchers

        # Active Roster
        'infielders': ['Matt Olson (1B)', 'Ozzie Albies (2B)', 'Austin Riley (3B)', 'Mauricio Dubón (SS)', 'Ha-Seong Kim (SS)'],
        'outfielders': ['Ronald Acuña Jr. (RF)', 'Michael Harris II (CF)', 'Mike Yastrzemski (LF)', 'Jhostynxon Garcia (RF)'],
        'catchers_dh': ['Marcell Ozuna (DH)', 'Dominic Smith (DH)', 'Sandy León (C)', 'Austin Wynns (C)'],

        # Starting Pitcher (estimated - would need actual starter info)
        'starting_pitcher': {
            'name': 'Spencer Strider',  # Assuming ace starter
            'era': 3.15,
            'k_per_9': 12.5,
            'whip': 1.10,
            'k_rate': 0.34,
            'handedness': 'R',
            'innings_proj': 6.0,
            'hr_per_9': 0.9,
        }
    }

    # Market data from user
    market_data = {
        'moneyline_home': +124,           # Pirates
        'moneyline_away': -146,           # Braves
        'run_line': -1.5,                 # Braves -1.5
        'run_line_home_odds': -158,       # Pirates +1.5 (-158)
        'run_line_away_odds': +131,       # Braves -1.5 (+131)
        'total': 8.5,                     # Over/Under
    }

    # Run analysis
    result = analyze_mlb_match(
        home_team="Pittsburgh Pirates",
        away_team="Atlanta Braves",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="PNC Park, Pittsburgh",
        date="2026-06-07",
        league="MLB"
    )

    # Save results
    output_path = Path("output/braves_vs_pirates_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\nDetailed results saved to: {output_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    run_braves_pirates_analysis()