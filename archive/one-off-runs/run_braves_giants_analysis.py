#!/usr/bin/env python
"""
COMPREHENSIVE MLB ANALYSIS (RECALIBRATED)
- Atlanta Braves vs San Francisco Giants
MLB - June 16, 2026 at 7:45 PM ET
Truist Park, Atlanta, GA
- Updated with correct venue, pitchers, market data
"""

import sys
import json
import math
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


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, x))


def nrfi_compute(home_k_rate, away_k_rate, home_era, away_era, park_factor=1.0):
    """Compute No Run First Inning probability with park adjustment"""
    base_nrfi = 0.53
    era_adj = ((5.0 - home_era) + (5.0 - away_era)) * 0.015
    k_adj = ((home_k_rate - 0.22) + (away_k_rate - 0.22)) * 0.5
    # Pitcher-friendly parks boost NRFI, hitter-friendly parks reduce NRFI
    park_adj = (1.0 - park_factor) * 0.12
    nrfi_prob = max(0.25, min(0.75, base_nrfi + era_adj + k_adj + park_adj))
    edge = nrfi_prob - 0.50
    conf = confidence_score(edge * 100, volatility=0.60)
    lean = "NRFI" if nrfi_prob > 0.55 else "YRFI"
    rec = bet_recommendation(conf, "mlb_nrfi")
    return {"probability": round(nrfi_prob, 4), "lean": lean, "confidence": round(conf, 1), "recommendation": rec}


def analyze_mlb_match(
    home_team, away_team, home_data, away_data, market_data, venue,
    date="2026-06-16", league="MLB"
):
    """Analyze a single MLB match and return results"""

    print("=" * 80)
    print(f"COMPREHENSIVE MATCH ANALYSIS: {home_team} vs {away_team}")
    print(f"{league} - {date}")
    print(f"Venue: {venue}")
    print("=" * 80)
    print()

    park_factor = home_data.get('park_factor', 1.0)

    # 1. TEAM OFFENSIVE/DEFENSIVE ANALYSIS
    print("1. TEAM OFFENSIVE/DEFENSIVE ANALYSIS")
    print("-" * 40)

    home_net = home_data['runs_per_game'] - home_data['runs_allowed_per_game']
    away_net = away_data['runs_per_game'] - away_data['runs_allowed_per_game']

    print(f"   {home_team}:")
    print(f"      Runs/Game: {home_data['runs_per_game']:.2f} | Runs Allowed/Game: {home_data['runs_allowed_per_game']:.2f} | Net: {home_net:+.2f}")
    print(f"      Team ERA: {home_data['team_era']:.2f} | Team OPS: {home_data['team_ops']:.3f} | WHIP: {home_data.get('team_whip', 1.28):.2f}")
    print(f"      O/U Trends: Over 28/45 home games (62%) | F5 Under 32/50 (64%)")
    print()
    print(f"   {away_team}:")
    print(f"      Runs/Game: {away_data['runs_per_game']:.2f} | Runs Allowed/Game: {away_data['runs_allowed_per_game']:.2f} | Net: {away_net:+.2f}")
    print(f"      Team ERA: {away_data['team_era']:.2f} | Team OPS: {away_data['team_ops']:.3f} | WHIP: {away_data.get('team_whip', 1.28):.2f}")
    print(f"      O/U Trends: Over 10/15 away games (67%) | F5 Under 7/8 (88%)")
    print()

    # 2. PITCHING MATCHUP ANALYSIS
    print("2. PITCHING MATCHUP ANALYSIS")
    print("-" * 40)

    home_pitcher = home_data.get('starting_pitcher', {})
    away_pitcher = away_data.get('starting_pitcher', {})

    print(f"   {home_team} Starter: {home_pitcher.get('name', 'TBD')} ({home_pitcher.get('handedness', 'R')})")
    print(f"      ERA: {home_pitcher.get('era', 0.00):.2f} | K/9: {home_pitcher.get('k_per_9', 0.0):.1f} | WHIP: {home_pitcher.get('whip', 0.00):.2f}")
    print(f"      K Rate: {home_pitcher.get('k_rate', 0.0):.1%} | HR/9: {home_pitcher.get('hr_per_9', 1.0):.2f} | IP Proj: {home_pitcher.get('innings_proj', 5.5):.1f}")
    print(f"      BAA: {home_pitcher.get('baa', 0.250):.3f} | Barrel%: {home_pitcher.get('barrel_pct', 8.0):.1f}%")
    print()
    print(f"   {away_team} Starter: {away_pitcher.get('name', 'TBD')} ({away_pitcher.get('handedness', 'R')})")
    print(f"      ERA: {away_pitcher.get('era', 0.00):.2f} | K/9: {away_pitcher.get('k_per_9', 0.0):.1f} | WHIP: {away_pitcher.get('whip', 0.00):.2f}")
    print(f"      K Rate: {away_pitcher.get('k_rate', 0.0):.1%} | HR/9: {away_pitcher.get('hr_per_9', 1.0):.2f} | IP Proj: {away_pitcher.get('innings_proj', 5.5):.1f}")
    print(f"      BAA: {away_pitcher.get('baa', 0.250):.3f} | Barrel%: {away_pitcher.get('barrel_pct', 8.0):.1f}%")

    # Bullpen comparison
    print()
    print(f"   BULLPEN (Last 14 Days):")
    print(f"      {home_team} BP ERA: {home_data.get('bullpen_era_14d', 4.00):.2f} | FIP: {home_data.get('bullpen_fip_14d', 4.00):.2f}")
    print(f"      {away_team} BP ERA: {away_data.get('bullpen_era_14d', 5.00):.2f} | FIP: {away_data.get('bullpen_fip_14d', 5.00):.2f}")
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
    print(f"      INJURY NOTE: Harrison Bader (CF) OUT - CF defense downgrade")
    print()

    # 4. PROJECTED TOTAL RUNS CALCULATION (RECALIBRATED)
    print("4. PROJECTED TOTAL RUNS (RECALIBRATED)")
    print("-" * 40)
    print("   FACTORS INCORPORATED:")
    print("   - Houser: pitch-to-contact (.289 BAA, 6.4 K/9) = low K, high contact")
    print("   - Houser avg 4.90 IP/start = early bullpen (Giants BP: 6.26 ERA)")
    print("   - Truist Park: hitter-friendly (1.05 park factor)")
    print("   - Bader OUT: CF defense downgrade = more XBH for Braves")
    print("   - Public money pushing Over juice -105 to -115")
    print()

    home_pitcher_era = home_pitcher.get('era', 4.00)
    away_pitcher_era = away_pitcher.get('era', 4.00)

    # Base projection from team scoring and pitcher ERA
    home_proj_runs = (home_data['runs_per_game'] + away_pitcher_era) / 2
    away_proj_runs = (away_data['runs_per_game'] + home_pitcher_era) / 2

    # RECALIBRATION: Houser is a contact pitcher, boost opponent scoring
    houser_contact_adj = 0.35  # Houser's .289 BAA and contact style = extra runs
    away_proj_runs += houser_contact_adj

    # RECALIBRATION: Giants bullpen is a liability (6.26 ERA last 14 days)
    giants_bullpen_adj = 0.40  # Early hook + terrible pen = late runs
    away_proj_runs += giants_bullpen_adj

    # RECALIBRATION: Bader CF injury = outfield defense downgrade
    bader_defense_adj = 0.25  # Elite CF -> replacement = extra hits/XBH
    away_proj_runs += bader_defense_adj

    # Home net run differential adjustment
    home_net_adj = (home_data['runs_per_game'] - home_data['runs_allowed_per_game']) * 0.08
    away_net_adj = (away_data['runs_per_game'] - away_data['runs_allowed_per_game']) * 0.08
    home_proj_runs += home_net_adj
    away_proj_runs += away_net_adj

    # Adjust for park factor and weather
    weather_adj = home_data.get('weather_adjustment', 1.0)

    home_proj_runs *= park_factor * weather_adj
    away_proj_runs *= park_factor * weather_adj

    projected_total = home_proj_runs + away_proj_runs
    run_diff = home_proj_runs - away_proj_runs

    print(f"   {home_team} Projected Runs: {home_proj_runs:.2f}")
    print(f"   {away_team} Projected Runs: {away_proj_runs:.2f}")
    print(f"   Projected Total: {projected_total:.2f}")
    print(f"   Market Total: {market_data['total']}")
    print(f"   Total Edge: {projected_total - market_data['total']:+.2f} runs")
    print(f"   Park Factor: {park_factor:.2f} | Weather Adj: {weather_adj:.2f}")
    print(f"   Recalibration Factors: Houser_Contact(+{houser_contact_adj}) | BP_Fatigue(+{giants_bullpen_adj}) | Bader_Injury(+{bader_defense_adj})")
    print()

    # 5. MONEYLINE ANALYSIS
    print("5. MONEYLINE ANALYSIS")
    print("-" * 40)

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

    model_home_prob = clamp(sigmoid(run_diff / 2.5 + 0.12))

    print(f"   {home_team} Moneyline: {home_ml:+d}")
    print(f"      Implied Probability: {home_implied:.1%}")
    print(f"      Model Probability: {model_home_prob:.1%}")
    print(f"      Edge: {(model_home_prob - home_implied):+.1%}")
    print(f"      Fair Moneyline: {int(-100 * model_home_prob / (1 - model_home_prob)) if model_home_prob > 0.50 else int(100 * (1 - model_home_prob) / model_home_prob)}")
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

    if run_diff > 1.5:
        home_rl_prob = 0.50
    elif run_diff > 0.5:
        home_rl_prob = 0.42
    elif run_diff > -0.5:
        home_rl_prob = 0.35
    elif run_diff > -1.5:
        home_rl_prob = 0.28
    else:
        home_rl_prob = 0.22

    print(f"   Model {home_team} Cover -{abs(run_line)} Probability: {home_rl_prob:.1%}")
    print()

    # 7. NRFI ANALYSIS
    print("7. NRFI (NO RUN FIRST INNING) ANALYSIS")
    print("-" * 40)

    nrfi = nrfi_compute(
        home_data.get('k_rate', 0.22),
        away_data.get('k_rate', 0.22),
        home_data.get('team_era', 4.00),
        away_data.get('team_era', 4.00),
        park_factor
    )
    print(f"   NRFI Probability: {nrfi['probability']:.1%}")
    print(f"   Lean: {nrfi['lean']} | Conf: {nrfi['confidence']:.1f}% | Rec: {nrfi['recommendation']}")
    print(f"   Historical Edge: Braves F5 Under 32/50 (64%) | Giants F5 Under 7/8 (88%)")
    print()

    # 8. CONFIDENCE SCORING
    print("8. CONFIDENCE SCORING")
    print("-" * 40)

    total_volatility = get_volatility("mlb_totals")
    total_edge = projected_total - market_data['total']
    total_confidence = confidence_score(total_edge * 8, total_volatility)
    total_recommendation = bet_recommendation(total_confidence, "mlb_totals")

    side_volatility = get_volatility("mlb_sides")
    side_edge = (model_home_prob - home_implied) * 100
    side_confidence = confidence_score(abs(side_edge), side_volatility)
    side_recommendation = bet_recommendation(side_confidence, "mlb_sides")

    print(f"   Total Bet ({'OVER' if projected_total > market_data['total'] else 'UNDER'} {market_data['total']}):")
    print(f"      Edge: {total_edge:+.2f} runs")
    print(f"      Confidence: {total_confidence:.1f}%")
    print(f"      Recommendation: {total_recommendation}")
    print()
    print(f"   Side Bet ({home_team if model_home_prob > 0.50 else away_team} ML):")
    print(f"      Edge: {side_edge:+.1f}%")
    print(f"      Confidence: {side_confidence:.1f}%")
    print(f"      Recommendation: {side_recommendation}")
    print()

    # 9. K PROPS FOR PITCHERS
    print("9. PITCHER STRIKEOUT PROPS")
    print("-" * 40)

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
            "k_rate": away_pitcher.get('k_rate', 0.15),
            "handedness": away_pitcher.get('handedness', 'R'),
            "innings_proj": away_pitcher.get('innings_proj', 4.9),
            "prop_line": 3.5
        },
        opponent_stats={
            "k_rate_vs_R": home_data.get('k_rate_vs_rhp', 0.22),
            "k_rate_vs_L": home_data.get('k_rate_vs_lhp', 0.22),
            "k_rate": home_data.get('team_k_rate', 0.21)
        },
        umpire_stats=None,
        park_factor=park_factor
    )

    print(f"   {home_pitcher.get('name', 'Home Pitcher')}: {home_k_prop['projection']:.1f} Ks (Line: {home_k_prop['line']}) -> {home_k_prop['lean']}")
    print(f"   {away_pitcher.get('name', 'Away Pitcher')} (Houser): {away_k_prop['projection']:.1f} Ks (Line: {away_k_prop['line']}) -> {away_k_prop['lean']}")
    print(f"      NOTE: Houser has 6.4 K/9 (career-low whiff rate) — Under looks strong")
    print()

    # 10. HR PROPS FOR KEY HITTERS
    print("10. HOME RUN PROPS - KEY HITTERS")
    print("-" * 40)

    weather = {
        "temperature": home_data.get('temperature', 82),
        "wind_speed": home_data.get('wind_speed', 7),
        "wind_direction_factor": home_data.get('wind_direction', 0.65)
    }

    key_hitters = [
        # Braves key hitters (Home)
        {"name": "Ronald Acuña Jr.", "team": "ATL", "hr_rate": 0.06, "barrel_rate": 0.12, "hard_hit_rate": 0.45},
        {"name": "Matt Olson", "team": "ATL", "hr_rate": 0.07, "barrel_rate": 0.14, "hard_hit_rate": 0.48},
        {"name": "Austin Riley", "team": "ATL", "hr_rate": 0.05, "barrel_rate": 0.11, "hard_hit_rate": 0.42},
        {"name": "Marcell Ozuna", "team": "ATL", "hr_rate": 0.05, "barrel_rate": 0.10, "hard_hit_rate": 0.40},
        {"name": "Michael Harris II", "team": "ATL", "hr_rate": 0.04, "barrel_rate": 0.09, "hard_hit_rate": 0.38},
        {"name": "Ozzie Albies", "team": "ATL", "hr_rate": 0.04, "barrel_rate": 0.09, "hard_hit_rate": 0.39},
        # Giants key hitters (Away)
        {"name": "Matt Chapman", "team": "SF", "hr_rate": 0.05, "barrel_rate": 0.11, "hard_hit_rate": 0.44},
        {"name": "LaMonte Wade Jr.", "team": "SF", "hr_rate": 0.03, "barrel_rate": 0.08, "hard_hit_rate": 0.35},
        {"name": "Mike Yastrzemski", "team": "SF", "hr_rate": 0.04, "barrel_rate": 0.09, "hard_hit_rate": 0.37},
        {"name": "Jorge Soler", "team": "SF", "hr_rate": 0.06, "barrel_rate": 0.13, "hard_hit_rate": 0.44},
        {"name": "Heliot Ramos", "team": "SF", "hr_rate": 0.04, "barrel_rate": 0.09, "hard_hit_rate": 0.39},
    ]

    hr_props = []
    for hitter in key_hitters:
        pitcher = home_pitcher if hitter['team'] == 'ATL' else away_pitcher
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

    # 11. PLAYER PROPS - TOTAL BASES & HITS
    print("11. PLAYER PROPS - TOTAL BASES & HITS")
    print("-" * 40)

    player_props = []

    prop_players = [
        # Braves (at home facing Houser contact pitcher)
        {"name": "Ronald Acuña Jr.", "team": "ATL", "avg": 0.295, "slg": 0.500, "pa_proj": 4.7},
        {"name": "Matt Olson", "team": "ATL", "avg": 0.275, "slg": 0.525, "pa_proj": 4.5},
        {"name": "Austin Riley", "team": "ATL", "avg": 0.280, "slg": 0.480, "pa_proj": 4.5},
        {"name": "Marcell Ozuna", "team": "ATL", "avg": 0.280, "slg": 0.490, "pa_proj": 4.3},
        {"name": "Michael Harris II", "team": "ATL", "avg": 0.285, "slg": 0.450, "pa_proj": 4.3},
        {"name": "Ozzie Albies", "team": "ATL", "avg": 0.285, "slg": 0.465, "pa_proj": 4.4},
        # Giants (on road, facing elite pitcher)
        {"name": "Matt Chapman", "team": "SF", "avg": 0.250, "slg": 0.455, "pa_proj": 4.0},
        {"name": "Jorge Soler", "team": "SF", "avg": 0.248, "slg": 0.460, "pa_proj": 3.8},
        {"name": "LaMonte Wade Jr.", "team": "SF", "avg": 0.260, "slg": 0.395, "pa_proj": 3.8},
        {"name": "Heliot Ramos", "team": "SF", "avg": 0.255, "slg": 0.415, "pa_proj": 3.5},
        {"name": "Mike Yastrzemski", "team": "SF", "avg": 0.250, "slg": 0.410, "pa_proj": 3.5},
    ]

    for player in prop_players:
        tb_prop = project_total_bases({
            "player_name": player['name'],
            "team": player['team'],
            "slg": player['slg'],
            "avg": player['avg'],
            "pa_proj": player['pa_proj'],
            "prop_line": 1.5
        })

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

    # 12. HISTORICAL TRENDS & MARKET ANALYSIS
    print("12. HISTORICAL TRENDS & MARKET ANALYSIS")
    print("-" * 40)
    print(f"   CONSENSUS TOTAL: {market_data['total']} (juice shifted -105 to -115 on Over)")
    print(f"   Key Trends Supporting OVER:")
    print(f"      - Giants Over 10/15 away games (67%, +5.55 units)")
    print(f"      - Braves Team Total Over 31/50 games (62%)")
    print(f"      - Houser pitch-to-contact (.289 BAA) vs elite Braves lineup")
    print(f"      - Giants bullpen 6.26 ERA/5.62 FIP last 14 days")
    print(f"      - Harrison Bader (CF) OUT = outfield downgrade")
    print(f"   Key Trends Supporting UNDER:")
    print(f"      - Braves Home Total Under 28/45 (62%, +11.55 units)")
    print(f"      - Braves F5 Under 32/50 (64%)")
    print(f"      - Giants F5 Under 7/8 (88%)")
    print()

    # 13. FINAL PROJECTION & RECOMMENDATION
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY (RECALIBRATED)")
    print("=" * 80)
    print()

    if abs(model_home_prob - home_implied) > 0.10 and abs(total_edge) > 0.5:
        confidence = "HIGH"
    elif abs(model_home_prob - home_implied) > 0.05 or abs(total_edge) > 0.5:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    if model_home_prob > home_implied + 0.05:
        ml_recommendation = f"LEAN {home_team} ML ({home_ml:+d})"
    elif (1 - model_home_prob) > away_implied + 0.05:
        ml_recommendation = f"LEAN {away_team} ML ({away_ml:+d})"
    else:
        ml_recommendation = "NO STRONG MONEYLINE LEAN"

    if projected_total > market_data['total'] + 0.5:
        total_rec = f"LEAN OVER {market_data['total']}"
    elif projected_total < market_data['total'] - 0.5:
        total_rec = f"LEAN UNDER {market_data['total']}"
    else:
        total_rec = "NO STRONG TOTAL LEAN"

    print(f"   PROJECTED SCORE: {home_team} {home_proj_runs:.1f} - {away_team} {away_proj_runs:.1f}")
    print(f"   PROJECTED TOTAL: {projected_total:.2f} (Market: {market_data['total']})")
    print(f"   PROJECTED MARGIN: {run_diff:+.2f} ({home_team})")
    print(f"   PARK: {'Pitcher-friendly' if park_factor < 1.0 else 'Hitter-friendly' if park_factor > 1.0 else 'Neutral'} ({park_factor:.2f})")
    print()
    print(f"   WIN PROBABILITIES:")
    print(f"      {home_team}: {model_home_prob:.1%}")
    print(f"      {away_team}: {(1 - model_home_prob):.1%}")
    print()
    print(f"   BETTING RECOMMENDATIONS:")
    print(f"      Moneyline: {ml_recommendation}")
    print(f"      Total: {total_rec}")
    print(f"      Run Line: {'LEAN' if abs(run_diff) > 1.5 else 'NO LEAN'} {'Home' if run_diff > 0 else 'Away'} -1.5")
    print(f"      NRFI: {nrfi['lean']} (Conf: {nrfi['confidence']:.1f}%)")
    print(f"      F5 Team Totals: Lean Braves F5 Over / Giants F5 Under (Trend-based)")
    print()
    print(f"   CONFIDENCE LEVEL: {confidence}")
    print()

    results = {
        "game_info": {
            "home_team": home_team,
            "away_team": away_team,
            "league": league,
            "date": date,
            "venue": venue,
            "game_time": "7:45 PM ET"
        },
        "team_metrics": {
            "home": {
                "runs_per_game": home_data['runs_per_game'],
                "runs_allowed_per_game": home_data['runs_allowed_per_game'],
                "team_era": home_data['team_era'],
                "team_whip": home_data.get('team_whip', 1.28),
                "team_ops": home_data['team_ops'],
                "k_rate": home_data.get('k_rate', 0.22),
                "park_factor": park_factor,
                "starting_pitcher": home_pitcher
            },
            "away": {
                "runs_per_game": away_data['runs_per_game'],
                "runs_allowed_per_game": away_data['runs_allowed_per_game'],
                "team_era": away_data['team_era'],
                "team_whip": away_data.get('team_whip', 1.28),
                "team_ops": away_data['team_ops'],
                "k_rate": away_data.get('k_rate', 0.22),
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
            "total_juice_shift": "-105 to -115 (Over)"
        },
        "projections": {
            "home_runs": round(home_proj_runs, 2),
            "away_runs": round(away_proj_runs, 2),
            "total_runs": round(projected_total, 2),
            "run_differential": round(run_diff, 2),
            "home_win_probability": round(model_home_prob, 3),
            "away_win_probability": round(1 - model_home_prob, 3),
        },
        "recalibration_factors": {
            "houser_contact_pitcher_adj": houser_contact_adj,
            "giants_bp_fatigue_adj": giants_bullpen_adj,
            "bader_outfield_injury_adj": bader_defense_adj,
            "total_adjustment": round(houser_contact_adj + giants_bullpen_adj + bader_defense_adj, 2)
        },
        "recommendations": {
            "moneyline": ml_recommendation,
            "total": total_rec,
            "run_line": f"{'LEAN' if abs(run_diff) > 1.5 else 'NO LEAN'} {'Home' if run_diff > 0 else 'Away'} -1.5",
            "nrfi": {'lean': nrfi['lean'], 'probability': nrfi['probability'], 'confidence': nrfi['confidence']},
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
        "nrfi_analysis": nrfi,
        "pitcher_props": {
            "home": home_k_prop,
            "away": away_k_prop,
        },
        "hr_props": hr_props,
        "player_props": player_props,
        "timestamp": datetime.now().isoformat()
    }

    return results


def run_braves_giants_analysis():
    """Run comprehensive analysis for Atlanta Braves vs San Francisco Giants (RECALIBRATED)"""

    print("=" * 80)
    print("COMPREHENSIVE ANALYSIS: ATLANTA BRAVES vs SAN FRANCISCO GIANTS")
    print("MLB - June 16, 2026 at 7:45 PM ET")
    print("Truist Park, Atlanta, GA")
    print("=" * 80)
    print()

    # ========================================================
    # Atlanta Braves (HOME) - CORRECTED
    # ========================================================
    # 2026 Season: NL East contender, elite offense
    # Park: Truist Park (hitter-friendly)
    # O/U Trends: Home Under 28/45, F5 Under 32/50
    home_data = {
        'runs_per_game': 5.12,           # Braves season average
        'runs_allowed_per_game': 4.25,    # Braves season average
        'team_era': 3.95,                 # Braves team ERA
        'team_whip': 1.22,                # Braves team WHIP
        'team_ops': 0.765,                # Braves team OPS (elite)
        'team_k_rate': 0.21,              # Braves lineup K rate
        'k_rate': 0.240,                  # Braves pitching K%
        'k_rate_vs_rhp': 0.20,            # vs Right-handed pitchers
        'k_rate_vs_lhp': 0.22,            # vs Left-handed pitchers
        'park_factor': 1.05,              # Truist Park hitter-friendly
        'temperature': 82,                # Atlanta evening temp (F) - June
        'wind_speed': 7,                  # Wind speed mph
        'wind_direction': 0.65,           # Wind factor (0-1) - blowing out
        'weather_adjustment': 1.02,       # Slight boost from warm conditions

        # Active Roster (2026 projection)
        'infielders': ['Matt Olson (1B)', 'Ozzie Albies (2B)', 'Austin Riley (3B)', 'Mauricio Dubón (SS)', 'Ha-Seong Kim (SS)'],
        'outfielders': ['Ronald Acuña Jr. (RF)', 'Michael Harris II (CF)', 'Mike Yastrzemski (LF)', 'Jhostynxon Garcia (RF)'],
        'catchers_dh': ['Marcell Ozuna (DH)', 'Dominic Smith (DH)', 'Sandy León (C)', 'Austin Wynns (C)'],

        # Bullpen (healthy)
        'bullpen_era_14d': 3.65,
        'bullpen_fip_14d': 3.80,

        # Starting Pitcher (Braves TBD - using season ace projection)
        'starting_pitcher': {
            'name': 'Max Fried / Braves SP',
            'era': 3.40,
            'k_per_9': 8.5,
            'whip': 1.18,
            'k_rate': 0.24,
            'handedness': 'L',
            'innings_proj': 6.0,
            'hr_per_9': 0.8,
            'baa': 0.235,
            'barrel_pct': 7.0,
        }
    }

    # ========================================================
    # San Francisco Giants (AWAY) - CORRECTED
    # ========================================================
    # 2026 Season: Competitive NL West team
    # Key: Adrian Houser starting (contact pitcher, .289 BAA, 6.4 K/9)
    # Bullpen: 6.26 ERA / 5.62 FIP last 14 days (major liability)
    # Injury: Harrison Bader (CF) OUT
    # O/U Trends: Away Over 10/15, F5 Under 7/8
    away_data = {
        'runs_per_game': 4.45,           # Giants season average
        'runs_allowed_per_game': 4.10,    # Giants season average
        'team_era': 3.85,                 # Giants team ERA
        'team_whip': 1.24,                # Giants team WHIP
        'team_ops': 0.735,                # Giants team OPS
        'team_k_rate': 0.225,             # Giants lineup K rate
        'k_rate': 0.195,                  # Giants pitching K% (lower with Houser)
        'k_rate_vs_rhp': 0.22,            # vs Right-handed pitchers
        'k_rate_vs_lhp': 0.20,            # vs Left-handed pitchers

        # Active Roster (2026 projection)
        'infielders': ['Matt Chapman (3B)', 'LaMonte Wade Jr. (1B)', 'Tyler Fitzgerald (SS)', 'Wilmer Flores (1B/2B)', 'Brett Wisely (2B)'],
        'outfielders': ['Heliot Ramos (CF/LF)', 'Mike Yastrzemski (RF)', 'Jorge Soler (LF/DH)', 'Luis Matos (CF)'],
        'catchers_dh': ['Patrick Bailey (C)', 'Tommy La Stella (DH)', 'Blake Sabol (C)'],

        # Bullpen (major liability)
        'bullpen_era_14d': 6.26,
        'bullpen_fip_14d': 5.62,

        # Starting Pitcher (Adrian Houser - pitch-to-contact)
        'starting_pitcher': {
            'name': 'Adrian Houser',
            'era': 4.85,
            'k_per_9': 6.4,
            'whip': 1.45,
            'k_rate': 0.15,
            'handedness': 'R',
            'innings_proj': 4.9,
            'hr_per_9': 1.1,
            'baa': 0.289,
            'barrel_pct': 9.5,
        }
    }

    # Market data (corrected for Braves home game with total 9)
    # Braves -145 favorite at home, Giants +125 underdog
    # Total: 9 (juice moved -105 to -115 favoring Over)
    market_data = {
        'moneyline_home': -145,           # Braves (home favorite)
        'moneyline_away': +125,           # Giants (road underdog)
        'run_line': -1.5,                 # Braves -1.5
        'run_line_home_odds': +135,       # Braves -1.5 (+135)
        'run_line_away_odds': -160,       # Giants +1.5 (-160)
        'total': 9.0,                     # Over/Under (juice shifted to Over -115)
    }

    # Run analysis
    result = analyze_mlb_match(
        home_team="Atlanta Braves",
        away_team="San Francisco Giants",
        home_data=home_data,
        away_data=away_data,
        market_data=market_data,
        venue="Truist Park, Atlanta, GA",
        date="2026-06-16",
        league="MLB"
    )

    # Save results
    output_path = Path("output/braves_vs_giants_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\nDetailed results saved to: {output_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    run_braves_giants_analysis()