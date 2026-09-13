#!/usr/bin/env python
"""
FIBA Basketball Interactive Runner
===================================
Enter ANY FIBA match and get 1Q, 1H, and Full Game recommendations
pushed to Discord with rich organized formatting.

Usage:
  python fiba_interactive_runner.py                          [Interactive mode]
  python fiba_interactive_runner.py --preset <name>          [Preset match]
  python fiba_interactive_runner.py --match "csv,values..."  [Quick entry]
"""

import sys
import json
import os
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from dotenv import load_dotenv
load_dotenv()

from MultiSportModel import (
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
    sigmoid,
    clamp,
)

# ============================================================================
# FIRST HALF PROJECTION (1H)
# ============================================================================

def project_basketball_h1(home: Dict, away: Dict) -> Dict:
    """Project first HALF outcomes for FIBA basketball games."""
    avg_h1_possessions = 38
    home_h1_efficiency = home["ortg"] * 0.96
    away_h1_efficiency = away["ortg"] * 0.96
    home_h1_points = (home_h1_efficiency / 100) * avg_h1_possessions * (100 / away["drtg"])
    away_h1_points = (away_h1_efficiency / 100) * avg_h1_possessions * (100 / home["drtg"])
    avg_pace = (home["pace"] + away["pace"]) / 2
    pace_factor = avg_pace / 70
    home_h1_points *= pace_factor
    away_h1_points *= pace_factor
    home_h1_points *= 1.04
    home_ctx = context_score(home["rotation_depth"], home["injury_status"],
                             home["coach_stability"], home["motivation"])
    away_ctx = context_score(away["rotation_depth"], away["injury_status"],
                             away["coach_stability"], away["motivation"])
    ctx_adjustment = (home_ctx - away_ctx) * 0.4
    home_h1_points += ctx_adjustment * 0.6
    away_h1_points -= ctx_adjustment * 0.6
    h1_spread = home_h1_points - away_h1_points
    h1_total = home_h1_points + away_h1_points
    h1_score = h1_spread * 0.6
    h1_prob_home = clamp(sigmoid(h1_score / 4.0))
    return {
        "home_h1_points": round(home_h1_points, 1),
        "away_h1_points": round(away_h1_points, 1),
        "h1_spread": round(h1_spread, 1),
        "h1_total": round(h1_total, 1),
        "h1_prob_home_win": round(h1_prob_home, 3),
    }


# ============================================================================
# BET DECISION ENGINE
# ============================================================================

def make_bet_decision(
    projected_value: float, market_line: float,
    threshold_bet: float = 1.5, threshold_lean: float = 0.5,
    prob_home: float = 0.5, direction: str = "spread",
) -> Dict[str, Any]:
    """Make a clear bet decision based on projected vs market values."""
    if direction == "spread":
        edge = abs(projected_value - market_line)
        if edge >= threshold_bet and prob_home >= 0.55:
            decision = "BET"
        elif edge >= threshold_lean:
            decision = "LEAN"
        else:
            decision = "PASS"
    else:
        edge = abs(projected_value - market_line)
        if edge >= threshold_bet:
            decision = "BET"
        elif edge >= threshold_lean:
            decision = "LEAN"
        else:
            decision = "PASS"
    return {"decision": decision, "edge": round(edge, 2),
            "projected": round(projected_value, 1), "market": market_line}


# ============================================================================
# FIBA ANALYSIS ENGINE
# ============================================================================

def analyze_fiba_game(
    home_team: str, away_team: str,
    home_data: Dict, away_data: Dict, market_data: Dict,
    venue: str = "FIBA Arena", date: str = "2026-07-02",
    league: str = "FIBA Americas",
) -> Dict[str, Any]:
    """Complete FIBA analysis: Q1, 1H, FG + bet recommendations."""
    results = {}

    # FULL GAME
    ctx = GameContext(
        game_id=f"{home_team.replace(' ', '_')}_vs_{away_team.replace(' ', '_')}",
        date=date, league=league, record_type="full_game",
        home_team=home_team, away_team=away_team,
        market_line=market_data['spread'],
        current_line=market_data['current_line'],
        open_line=market_data['open_line'],
    )
    home_tm = TeamMetrics(
        ortg=home_data['ortg'], drtg=home_data['drtg'],
        baseline_net=home_data['baseline_net'], recent_net=home_data['recent_net'],
        pace=home_data['pace'], rest_days=home_data['rest_days'],
        travel_km=home_data['travel_km'], back_to_back=home_data['back_to_back'],
        three_in_six=home_data['three_in_six'], split_edge=home_data['split_edge'],
        rotation_depth=home_data['rotation_depth'], injury_status=home_data['injury_status'],
        coach_stability=home_data['coach_stability'], motivation=home_data['motivation'],
        open_line=market_data['open_line'], current_line=market_data['current_line'],
    )
    away_tm = TeamMetrics(
        ortg=away_data['ortg'], drtg=away_data['drtg'],
        baseline_net=away_data['baseline_net'], recent_net=away_data['recent_net'],
        pace=away_data['pace'], rest_days=away_data['rest_days'],
        travel_km=away_data['travel_km'], back_to_back=away_data['back_to_back'],
        three_in_six=away_data['three_in_six'], split_edge=away_data['split_edge'],
        rotation_depth=away_data['rotation_depth'], injury_status=away_data['injury_status'],
        coach_stability=away_data['coach_stability'], motivation=away_data['motivation'],
        open_line=-market_data['open_line'], current_line=-market_data['current_line'],
    )
    fg_result = eu_build_full_game(home_tm, away_tm, ctx)
    fg_prob = fg_result['probability']
    fg_proj_home = fg_result['projected_home_score']
    fg_proj_away = fg_result['projected_away_score']
    fg_proj_total = fg_result['projected_total']
    fg_spread = fg_proj_home - fg_proj_away

    results['fg'] = {
        'projected_home': fg_proj_home, 'projected_away': fg_proj_away,
        'projected_total': fg_proj_total, 'projected_spread': fg_spread,
        'home_win_prob': fg_prob, 'away_win_prob': 1 - fg_prob,
        'model_edge': fg_result['model_edge'], 'lean': fg_result['lean'],
    }

    # FIRST QUARTER
    q1_proj = project_basketball_q1(home_data, away_data)
    results['q1'] = {
        'projected_home': q1_proj['home_q1_points'],
        'projected_away': q1_proj['away_q1_points'],
        'projected_total': q1_proj['q1_total'],
        'projected_spread': q1_proj['q1_spread'],
        'home_win_prob': q1_proj['q1_prob_home_win'],
        'away_win_prob': 1 - q1_proj['q1_prob_home_win'],
    }

    # FIRST HALF
    h1_proj = project_basketball_h1(home_data, away_data)
    results['h1'] = {
        'projected_home': h1_proj['home_h1_points'],
        'projected_away': h1_proj['away_h1_points'],
        'projected_total': h1_proj['h1_total'],
        'projected_spread': h1_proj['h1_spread'],
        'home_win_prob': h1_proj['h1_prob_home_win'],
        'away_win_prob': 1 - h1_proj['h1_prob_home_win'],
    }

    # BET DECISIONS
    q1_line = market_data['spread'] * 0.25
    q1_total_line = market_data['total'] * 0.26
    h1_line = market_data['spread'] * 0.5
    h1_total_line = market_data['total'] * 0.50

    results['bets'] = {
        'fg_spread': make_bet_decision(fg_spread, market_data['spread'], 3.0, 1.5, fg_prob, "spread"),
        'fg_total': make_bet_decision(fg_proj_total, market_data['total'], 6.0, 3.0, 0.5, "total"),
        'h1_spread': make_bet_decision(h1_proj['h1_spread'], h1_line, 2.0, 1.0, h1_proj['h1_prob_home_win'], "spread"),
        'h1_total': make_bet_decision(h1_proj['h1_total'], h1_total_line, 4.0, 2.0, 0.5, "total"),
        'q1_spread': make_bet_decision(q1_proj['q1_spread'], q1_line, 1.5, 0.8, q1_proj['q1_prob_home_win'], "spread"),
        'q1_total': make_bet_decision(q1_proj['q1_total'], q1_total_line, 3.0, 1.5, 0.5, "total"),
    }

    results['meta'] = {
        'home_team': home_team, 'away_team': away_team,
        'league': league, 'date': date, 'venue': venue,
        'market_data': market_data,
    }
    return results


# ============================================================================
# DISCORD PUSH
# ============================================================================

def push_fiba_to_discord(home_team: str, away_team: str, results: Dict) -> bool:
    """Push FIBA analysis to Discord with rich embed formatting."""
    try:
        import requests
    except ImportError:
        print("  [X] requests library not installed.")
        return False

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or webhook_url == "None":
        print("  [X] DISCORD_WEBHOOK_URL not set in .env")
        return False

    fg = results['fg']; q1 = results['q1']; h1 = results['h1']
    bets = results['bets']; md = results['meta']['market_data']

    has_bet = any(b['decision'] == 'BET' for b in bets.values())
    has_lean = any(b['decision'] == 'LEAN' for b in bets.values())
    color = 3066993 if has_bet else (16776960 if has_lean else 15158332)

    fields = []

    # FG projection
    fields.append({
        "name": "FULL GAME PROJECTION",
        "value": (
            f"**Projected Score:** {home_team} {fg['projected_home']:.1f} - "
            f"{away_team} {fg['projected_away']:.1f}\n"
            f"**Total:** {fg['projected_total']:.1f} | **Spread:** {fg['projected_spread']:+.1f}\n"
            f"**Win Prob:** {home_team} {fg['home_win_prob']:.1%}"
        ),
        "inline": False
    })

    # 1H projection
    fields.append({
        "name": "FIRST HALF (1H) PROJECTION",
        "value": (
            f"**Projected Score:** {home_team} {h1['projected_home']:.1f} - "
            f"{away_team} {h1['projected_away']:.1f}\n"
            f"**Total:** {h1['projected_total']:.1f} | **Spread:** {h1['projected_spread']:+.1f}\n"
            f"**Win Prob:** {home_team} {h1['home_win_prob']:.1%}"
        ),
        "inline": False
    })

    # Q1 projection
    fields.append({
        "name": "FIRST QUARTER (1Q) PROJECTION",
        "value": (
            f"**Projected Score:** {home_team} {q1['projected_home']:.1f} - "
            f"{away_team} {q1['projected_away']:.1f}\n"
            f"**Total:** {q1['projected_total']:.1f} | **Spread:** {q1['projected_spread']:+.1f}\n"
            f"**Win Prob:** {home_team} {q1['home_win_prob']:.1%}"
        ),
        "inline": False
    })

    # Bet recommendations
    bet_lines = []
    for key, bet in bets.items():
        label = key.upper().replace('_', ' ')
        emoji = ":green_circle:" if bet['decision'] == 'BET' else (":yellow_circle:" if bet['decision'] == 'LEAN' else ":red_circle:")
        bet_lines.append(
            f"{emoji} **{label}** — {bet['decision']}\n"
            f"   Model: {bet['projected']:+.1f} | Market: {bet['market']:+.1f} | Edge: {bet['edge']:+.2f}"
        )

    fields.append({
        "name": "BET RECOMMENDATIONS",
        "value": "\n".join(bet_lines),
        "inline": False
    })

    # Market data
    fields.append({
        "name": "MARKET DATA",
        "value": (
            f"**Spread:** {md['spread']} ({home_team if md['spread'] < 0 else away_team} favored)\n"
            f"**Total:** {md['total']}\n"
            f"**Line Movement:** {md['open_line']} -> {md['current_line']}"
        ),
        "inline": False
    })

    embed = {
        "title": f"{home_team.upper()} vs {away_team.upper()}",
        "description": f"**FIBA Basketball** — {results['meta']['date']}\n{results['meta']['venue']}\n{results['meta']['league']}",
        "color": color,
        "fields": fields,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "footer": {"text": "MultiSportPredict • FIBA • 1Q • 1H • FG"}
    }

    try:
        resp = requests.post(webhook_url, json={"embeds": [embed]},
                             headers={"Content-Type": "application/json"}, timeout=15)
        if resp.status_code in (200, 204):
            print("\n  [OK] FIBA analysis pushed to Discord!")
            return True
        else:
            print(f"\n  [X] Discord push failed: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"\n  [X] Discord request error: {e}")
        return False


# ============================================================================
# CONSOLE OUTPUT
# ============================================================================

def print_results(home_team: str, away_team: str, results: Dict):
    """Print formatted results with ASCII-only output."""
    fg = results['fg']; q1 = results['q1']
    h1 = results['h1']; bets = results['bets']
    md = results['meta']['market_data']

    sep = "=" * 72
    print(f"\n{sep}")
    print(f"  {home_team.upper()} vs {away_team.upper()}")
    print(f"  {results['meta']['date']} | {results['meta']['venue']}")
    print(f"{sep}")

    # FG
    print(f"\n===== FULL GAME (FG) =====")
    print(f"  Score:  {home_team} {fg['projected_home']:.1f} - {away_team} {fg['projected_away']:.1f}")
    print(f"  Total:  {fg['projected_total']:.1f} | Spread: {fg['projected_spread']:+.1f}")
    print(f"  Win Pr: {home_team} {fg['home_win_prob']:.1%}")
    print(f"  Edge:   {fg['model_edge']:+.2f} | Lean: {fg['lean']}")

    # 1H
    print(f"\n===== FIRST HALF (1H) =====")
    print(f"  Score:  {home_team} {h1['projected_home']:.1f} - {away_team} {h1['projected_away']:.1f}")
    print(f"  Total:  {h1['projected_total']:.1f} | Spread: {h1['projected_spread']:+.1f}")
    print(f"  Win Pr: {home_team} {h1['home_win_prob']:.1%}")

    # Q1
    print(f"\n===== FIRST QUARTER (1Q) =====")
    print(f"  Score:  {home_team} {q1['projected_home']:.1f} - {away_team} {q1['projected_away']:.1f}")
    print(f"  Total:  {q1['projected_total']:.1f} | Spread: {q1['projected_spread']:+.1f}")
    print(f"  Win Pr: {home_team} {q1['home_win_prob']:.1%}")

    # Bets
    print(f"\n===== BET RECOMMENDATIONS =====")
    for key, bet in bets.items():
        sym = "[+]" if bet['decision'] == 'BET' else ("[/]" if bet['decision'] == 'LEAN' else "[ ]")
        print(f"  {sym} {key.upper():15s} | {bet['decision']:4s} | "
              f"Model: {bet['projected']:+.1f} | Market: {bet['market']:+.1f} | "
              f"Edge: {bet['edge']:+.2f}")

    print(f"\n===== MARKET =====")
    print(f"  Spread: {md['spread']} | Total: {md['total']}")
    print(f"  Line:   {md['open_line']} -> {md['current_line']}")
    print(f"{sep}\n")


# ============================================================================
# PRESET MATCHES
# ============================================================================

PRESET_MATCHES = {
    "uruguay_argentina": {
        "home_team": "Uruguay", "away_team": "Argentina",
        "league": "FIBA Americas", "date": "2026-07-02",
        "venue": "Estadio Antel, Montevideo, Uruguay",
        "home_data": {
            'ortg': 104.5, 'drtg': 108.0, 'baseline_net': -3.5, 'recent_net': -2.0,
            'pace': 72.5, 'rest_days': 3, 'travel_km': 0,
            'back_to_back': False, 'three_in_six': False,
            'split_edge': 3.5, 'rotation_depth': 9,
            'injury_status': 'green', 'coach_stability': 'green', 'motivation': 'green',
        },
        "away_data": {
            'ortg': 112.0, 'drtg': 104.5, 'baseline_net': 7.5, 'recent_net': 6.0,
            'pace': 74.0, 'rest_days': 2, 'travel_km': 200,
            'back_to_back': False, 'three_in_six': False,
            'split_edge': -2.0, 'rotation_depth': 10,
            'injury_status': 'green', 'coach_stability': 'green', 'motivation': 'green',
        },
        "market_data": {'spread': -6.5, 'open_line': -5.5, 'current_line': -6.5, 'total': 155.0},
    },
    "panama_cuba": {
        "home_team": "Panama", "away_team": "Cuba",
        "league": "FIBA Americas", "date": "2026-07-02",
        "venue": "Arena Roberto Duran, Panama City, Panama",
        "home_data": {
            'ortg': 101.0, 'drtg': 106.5, 'baseline_net': -5.5, 'recent_net': -4.0,
            'pace': 71.0, 'rest_days': 3, 'travel_km': 0,
            'back_to_back': False, 'three_in_six': False,
            'split_edge': 3.0, 'rotation_depth': 8,
            'injury_status': 'yellow', 'coach_stability': 'yellow', 'motivation': 'green',
        },
        "away_data": {
            'ortg': 102.5, 'drtg': 105.0, 'baseline_net': -2.5, 'recent_net': -3.0,
            'pace': 70.5, 'rest_days': 2, 'travel_km': 1800,
            'back_to_back': False, 'three_in_six': False,
            'split_edge': -1.5, 'rotation_depth': 8,
            'injury_status': 'green', 'coach_stability': 'yellow', 'motivation': 'yellow',
        },
        "market_data": {'spread': -2.5, 'open_line': -1.5, 'current_line': -2.5, 'total': 148.0},
    },
}


# ============================================================================
# MAIN
# ============================================================================

def main():
    sep = "=" * 72
    print(f"\n{sep}")
    print("  FIBA BASKETBALL INTERACTIVE RUNNER")
    print("  1Q | 1H | FG -- Analysis + Discord Push")
    print(f"{sep}")

    args = sys.argv[1:]
    match_config = None

    if "--preset" in args:
        pi = args.index("--preset") + 1
        name = args[pi] if pi < len(args) else "uruguay_argentina"
        if name in PRESET_MATCHES:
            match_config = PRESET_MATCHES[name]
            print(f"\n  Preset: {name} ({match_config['home_team']} vs {match_config['away_team']})")
        else:
            print(f"\n  [X] Preset '{name}' not found. Available: {list(PRESET_MATCHES.keys())}")
            return
    elif "--match" in args:
        mi = args.index("--match") + 1
        if mi < len(args):
            # Parse quick CSV: team names + full data
            parts = args[mi].split(",")
            if len(parts) >= 32:
                idx = 0
                home_team = parts[idx].strip(); idx += 1
                away_team = parts[idx].strip(); idx += 1
                home_data = {
                    'ortg': float(parts[idx]), 'drtg': float(parts[idx+1]),
                    'baseline_net': float(parts[idx+2]), 'recent_net': float(parts[idx+3]),
                    'pace': float(parts[idx+4]), 'rest_days': int(parts[idx+5]),
                    'travel_km': float(parts[idx+6]),
                    'back_to_back': parts[idx+7].strip().lower() in ('true','yes','y'),
                    'three_in_six': parts[idx+8].strip().lower() in ('true','yes','y'),
                    'split_edge': float(parts[idx+9]), 'rotation_depth': int(parts[idx+10]),
                    'injury_status': parts[idx+11].strip(),
                    'coach_stability': parts[idx+12].strip(),
                    'motivation': parts[idx+13].strip(),
                }; idx += 14
                away_data = {
                    'ortg': float(parts[idx]), 'drtg': float(parts[idx+1]),
                    'baseline_net': float(parts[idx+2]), 'recent_net': float(parts[idx+3]),
                    'pace': float(parts[idx+4]), 'rest_days': int(parts[idx+5]),
                    'travel_km': float(parts[idx+6]),
                    'back_to_back': parts[idx+7].strip().lower() in ('true','yes','y'),
                    'three_in_six': parts[idx+8].strip().lower() in ('true','yes','y'),
                    'split_edge': float(parts[idx+9]), 'rotation_depth': int(parts[idx+10]),
                    'injury_status': parts[idx+11].strip(),
                    'coach_stability': parts[idx+12].strip(),
                    'motivation': parts[idx+13].strip(),
                }; idx += 14
                md = {
                    'spread': float(parts[idx]), 'open_line': float(parts[idx+1]),
                    'current_line': float(parts[idx+2]), 'total': float(parts[idx+3]),
                }; idx += 4
                venue = parts[idx].strip() if idx < len(parts) else f"{home_team}'s Arena"; idx += 1
                league = parts[idx].strip() if idx < len(parts) else "FIBA Americas"; idx += 1
                date = parts[idx].strip() if idx < len(parts) else "2026-07-02"
                match_config = {
                    'home_team': home_team, 'away_team': away_team,
                    'league': league, 'date': date, 'venue': venue,
                    'home_data': home_data, 'away_data': away_data,
                    'market_data': md,
                }
                print(f"\n  Quick entry: {home_team} vs {away_team}")
            else:
                print(f"  [X] Need ~33 comma values, got {len(parts)}")
                return
        else:
            print("  [X] --match requires CSV values")
            return
    elif "--help" in args or "-h" in args:
        print("""
Usage:
  python fiba_interactive_runner.py                    Interactive mode
  python fiba_interactive_runner.py --preset <name>    Preset match
  python fiba_interactive_runner.py --match "csv..."   Quick CSV entry

Presets: uruguay_argentina, panama_cuba
        """)
        return
    else:
        # Interactive mode
        print("\n  [Interactive Mode]")
        home_team = input("  Home Team: ").strip()
        away_team = input("  Away Team: ").strip()
        if not home_team or not away_team:
            print("  [X] Both team names required.")
            return
        league = input(f"  League [FIBA Americas]: ").strip() or "FIBA Americas"
        date = input(f"  Date [2026-07-02]: ").strip() or "2026-07-02"
        venue = input(f"  Venue [{home_team}'s Arena]: ").strip() or f"{home_team}'s Arena"

        def td(label, is_home):
            print(f"\n  -- {label} --")
            d = {}
            d['ortg'] = float(input(f"    ORTG [105.0]: ") or 105.0)
            d['drtg'] = float(input(f"    DRTG [105.0]: ") or 105.0)
            d['baseline_net'] = float(input(f"    Baseline Net [0.0]: ") or 0.0)
            d['recent_net'] = float(input(f"    Recent Net [0.0]: ") or 0.0)
            d['pace'] = float(input(f"    Pace [72.0]: ") or 72.0)
            d['rest_days'] = int(input(f"    Rest Days [2]: ") or 2)
            d['travel_km'] = float(input(f"    Travel km [0]: ") or 0)
            d['back_to_back'] = input(f"    Back-to-Back? [n]: ").lower() in ('y','yes')
            d['three_in_six'] = input(f"    3-in-6? [n]: ").lower() in ('y','yes')
            d['split_edge'] = float(input(f"    H/A Split Edge [{3 if is_home else -2}]: ") or (3 if is_home else -2))
            d['rotation_depth'] = int(input(f"    Rotation Depth [9]: ") or 9)
            d['injury_status'] = input(f"    Injury Status [green]: ").strip() or "green"
            d['coach_stability'] = input(f"    Coach Stability [green]: ").strip() or "green"
            d['motivation'] = input(f"    Motivation [green]: ").strip() or "green"
            return d

        home_data = td(home_team, True)
        away_data = td(away_team, False)

        print(f"\n  -- Market Data --")
        market_data = {
            'spread': float(input(f"    Spread (- = home fav) [-6.5]: ") or -6.5),
            'open_line': float(input(f"    Open Line [-5.5]: ") or -5.5),
            'current_line': float(input(f"    Current Line [-6.5]: ") or -6.5),
            'total': float(input(f"    Total [155.0]: ") or 155.0),
        }
        match_config = {
            'home_team': home_team, 'away_team': away_team,
            'league': league, 'date': date, 'venue': venue,
            'home_data': home_data, 'away_data': away_data,
            'market_data': market_data,
        }

    if not match_config:
        print("  [X] No match config.")
        return

    ht = match_config['home_team']
    at = match_config['away_team']
    hd = match_config['home_data']
    ad = match_config['away_data']
    md = match_config['market_data']
    venue = match_config.get('venue', f"{ht}'s Arena")
    date = match_config.get('date', "2026-07-02")
    league = match_config.get('league', "FIBA Americas")

    print(f"\n  Analyzing: {ht} vs {at}")
    print(f"  League: {league} | Date: {date}")
    print(f"  Market: Spread {md['spread']}, Total {md['total']}")

    results = analyze_fiba_game(ht, at, hd, ad, md, venue, date, league)
    print_results(ht, at, results)

    # Save to file
    out_dir = Path("output/fiba")
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{ht.replace(' ', '_')}_vs_{at.replace(' ', '_')}.json"
    out_path = out_dir / fname
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"  [i] Results saved to: {out_path}")

    # Push to Discord
    print(f"\n--- DISCORD ---")
    push_choice = input(f"  Push results to Discord? (Y/n): ").strip().lower()
    if push_choice != 'n':
        push_fiba_to_discord(ht, at, results)

    print(f"\n{sep}")
    print("  Analysis Complete!")
    print(f"{sep}\n")


if __name__ == "__main__":
    main()