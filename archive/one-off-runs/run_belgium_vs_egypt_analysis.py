#!/usr/bin/env python
"""
Deep Dive Analysis — FIFA World Cup 2026
Belgium vs Egypt
Date: June 2026
"""

import sys
import json
from datetime import datetime
from pathlib import Path

from models.soccer_predictor import (
    get_league_config,
    poisson_over_prob,
    poisson_at_least_one,
    estimate_team_goals,
    estimate_btts_prob,
    team_goal_strength,
    team_btts_strength,
)
from core.confidence_engine import confidence_score, bet_recommendation


def run_analysis():
    print("\n" + "=" * 80)
    print("FIFA WORLD CUP 2026 — GROUP STAGE")
    print("Belgium vs Egypt")
    print("=" * 80 + "\n")

    # ========================================================
    # Belgium (Favorite, historically strong)
    # ========================================================
    # Golden generation aging (De Bruyne, Lukaku, Vertonghen later stages)
    # Still technically elite, strong midfield, creative attack
    # Defense has been vulnerable in transition
    belgium_data = {
        'xg_for': 1.90,
        'xg_against': 1.10,
        'shots': 13.5,
        'sot': 4.8,
        'goals_for': 1.85,
        'goals_against': 1.05,
        'clean_sheets': 5,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.35,
        'width_crossing': 0.58,
        'final_third_pressure': 0.55,
    }

    # ========================================================
    # Egypt (Underdog, Mohamed Salah-led)
    # ========================================================
    # Strong defensive structure, counter-attacking
    # Salah is the x-factor — world-class talent
    # Compact defense, dangerous on set pieces
    egypt_data = {
        'xg_for': 1.20,
        'xg_against': 1.10,
        'shots': 10.0,
        'sot': 3.5,
        'goals_for': 1.15,
        'goals_against': 1.05,
        'clean_sheets': 5,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.15,
        'width_crossing': 0.45,
        'final_third_pressure': 0.40,
    }

    market_data = {'goals_line': 2.5}

    home_team = "Belgium"
    away_team = "Egypt"
    league = "soccer_fifa_world_cup"
    date_str = "2026-06"

    # 1. GOAL STRENGTH
    print("1. GOAL STRENGTH ANALYSIS")
    print("-" * 40)
    home_gs = team_goal_strength(
        belgium_data['xg_for'], belgium_data['xg_against'], belgium_data['shots'], belgium_data['sot'],
        belgium_data['goals_for'], belgium_data['goals_against'], belgium_data['tempo'], 1,
        belgium_data['missing_attacker'], belgium_data['missing_creator'],
        belgium_data['missing_cb'], belgium_data['missing_gk']
    )
    away_gs = team_goal_strength(
        egypt_data['xg_for'], egypt_data['xg_against'], egypt_data['shots'], egypt_data['sot'],
        egypt_data['goals_for'], egypt_data['goals_against'], egypt_data['tempo'], 0,
        egypt_data['missing_attacker'], egypt_data['missing_creator'],
        egypt_data['missing_cb'], egypt_data['missing_gk']
    )
    print(f"   Belgium Goal Strength: {home_gs:+.2f}")
    print(f"   Egypt Goal Strength: {away_gs:+.2f}")
    print(f"   Goal Strength Diff: {home_gs - away_gs:+.2f}")
    print()

    # 2. EXPECTED GOALS
    print("2. EXPECTED GOALS PROJECTION")
    print("-" * 40)
    home_lam = estimate_team_goals(
        belgium_data['xg_for'], belgium_data['sot'], belgium_data['tempo'], 0,  # Neutral venue
        belgium_data['missing_attacker'], belgium_data['missing_creator'],
        egypt_data['xg_against'], egypt_data['missing_cb'], egypt_data['missing_gk']
    )
    away_lam = estimate_team_goals(
        egypt_data['xg_for'], egypt_data['sot'], egypt_data['tempo'], 0,
        egypt_data['missing_attacker'], egypt_data['missing_creator'],
        belgium_data['xg_against'], belgium_data['missing_cb'], belgium_data['missing_gk']
    )
    config = get_league_config(league)
    home_lam *= config['goal_variance']
    away_lam *= config['goal_variance']
    # World Cup: lower home advantage (neutral venue)
    # Still apply a small "familiarity" bonus, not full home advantage

    total_lam = home_lam + away_lam

    print(f"   Belgium Expected Goals: {home_lam:.2f}")
    print(f"   Egypt Expected Goals: {away_lam:.2f}")
    print(f"   Total Expected Goals: {total_lam:.2f}")
    print(f"   Expected Goal Diff: {home_lam - away_lam:+.2f}")
    print()

    p_over_15 = poisson_over_prob(total_lam, 1.5)
    p_over_25 = poisson_over_prob(total_lam, 2.5)
    p_over_35 = poisson_over_prob(total_lam, 3.5)
    print(f"   Over 1.5 Goals: {p_over_15:.1%}")
    print(f"   Over 2.5 Goals: {p_over_25:.1%}")
    print(f"   Over 3.5 Goals: {p_over_35:.1%}")
    print()

    # 3. BTTS
    print("3. BTTS ANALYSIS")
    print("-" * 40)
    home_btts = team_btts_strength(
        belgium_data['xg_for'], belgium_data['xg_against'], belgium_data['goals_for'], belgium_data['goals_against'],
        belgium_data['sot'], belgium_data['tempo'], belgium_data['final_third_pressure'],
        belgium_data['missing_attacker'], belgium_data['missing_cb'], belgium_data['missing_gk'],
        belgium_data['clean_sheets']
    )
    away_btts = team_btts_strength(
        egypt_data['xg_for'], egypt_data['xg_against'], egypt_data['goals_for'], egypt_data['goals_against'],
        egypt_data['sot'], egypt_data['tempo'], egypt_data['final_third_pressure'],
        egypt_data['missing_attacker'], egypt_data['missing_cb'], egypt_data['missing_gk'],
        egypt_data['clean_sheets']
    )
    btts_prob = estimate_btts_prob(home_lam, away_lam, home_btts, away_btts)
    defensive_weakness = (belgium_data['xg_against'] + egypt_data['xg_against'] - 2.5) * 0.05
    btts_prob = max(0, min(1, btts_prob + defensive_weakness))
    tempo_factor = (belgium_data['tempo'] + egypt_data['tempo']) * 0.03
    btts_prob = max(0, min(1, btts_prob + tempo_factor))
    
    # World Cup adjustment: lower scoring, more defensive
    btts_prob *= 0.90  # 10% reduction for World Cup defensive focus
    
    btts_conf = confidence_score((btts_prob - 0.50) * 100, volatility=0.48)
    btts_lean = "BTTS YES" if btts_prob > 0.55 else "BTTS NO"
    print(f"   Belgium BTTS Strength: {home_btts:+.2f}")
    print(f"   Egypt BTTS Strength: {away_btts:+.2f}")
    print(f"   BTTS Probability: {btts_prob:.1%}")
    print(f"   BTTS Confidence: {btts_conf:.1f}%")
    print(f"   BTTS Recommendation: {btts_lean}")
    print()

    # 4. MATCH OUTCOME
    print("4. MATCH OUTCOME PROJECTION")
    print("-" * 40)
    # World Cup: lower home adv, neutral venue
    home_win_prob = (home_lam / (home_lam + away_lam)) * 0.75 + 0.05
    away_win_prob = (away_lam / (home_lam + away_lam)) * 0.75 + 0.05
    draw_prob = 1 - home_win_prob - away_win_prob
    
    # World Cup: higher draw rate
    if draw_prob < 0.20:
        draw_prob = 0.20
        norm = home_win_prob + away_win_prob
        if norm > 0:
            home_win_prob *= (1 - draw_prob) / norm
            away_win_prob *= (1 - draw_prob) / norm

    print(f"   Belgium Win: {home_win_prob:.1%}")
    print(f"   Draw:         {draw_prob:.1%}")
    print(f"   Egypt Win: {away_win_prob:.1%}")

    if home_win_prob >= 0.45:
        outcome_lean = f"Belgium Win"
    elif away_win_prob >= 0.45:
        outcome_lean = f"Egypt Win"
    elif draw_prob >= 0.30:
        outcome_lean = "Draw"
    else:
        outcome_lean = "Pass"
    print(f"   Outcome Lean: {outcome_lean}")
    print()

    # 5. KEY PLAYERS & MATCHUP
    print("5. KEY PLAYERS & MATCHUP ANALYSIS")
    print("-" * 40)
    print(f"   Belgium Key Players: De Bruyne (midfield creator), Lukaku (finisher),")
    print(f"      Courtois (GK). Aging golden generation but still elite.")
    print(f"   Egypt Key Players: Mohamed Salah (world-class winger/finisher),")
    print(f"      defensive structure solid, set piece threat.")
    print(f"   Matchup: Belgium's technical midfield vs Egypt's compact defense.")
    print(f"   Salah's counter-attacking threat keeps Belgium honest.")
    print(f"   Belgium must break down a disciplined low block.")
    print(f"   World Cup context: Group stage — both teams need result.")
    print()

    # 6. FINAL SUMMARY
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Match: Belgium vs Egypt")
    print(f"   Competition: FIFA World Cup 2026 — Group Stage")
    print()
    print(f"   Projected Score: Belgium {home_lam:.1f} - {away_lam:.1f} Egypt")
    print(f"   Total Expected Goals: {total_lam:.2f}")
    print()
    goals_edge = total_lam - market_data['goals_line']
    goals_conf = confidence_score(goals_edge * 10, volatility=0.55)
    print("   === BETTING RECOMMENDATIONS ===")
    print(f"   Match Outcome:      {outcome_lean}")
    print(f"   Goals (O/U 2.5):     {'OVER' if p_over_25 > 0.50 else 'UNDER'} (Conf: {goals_conf:.1f}%)")
    print(f"   BTTS:               {btts_lean} (Conf: {btts_conf:.1f}%)")
    print()

    results = {
        "game_info": {
            "home_team": "Belgium",
            "away_team": "Egypt",
            "competition": "FIFA World Cup 2026",
            "stage": "Group Stage",
        },
        "projections": {
            "home_expected_goals": round(home_lam, 2),
            "away_expected_goals": round(away_lam, 2),
            "total_expected_goals": round(total_lam, 2),
            "belgium_win_prob": round(home_win_prob, 3),
            "draw_prob": round(draw_prob, 3),
            "egypt_win_prob": round(away_win_prob, 3),
        },
        "goals_analysis": {
            "over_15_prob": round(p_over_15, 3),
            "over_25_prob": round(p_over_25, 3),
            "over_35_prob": round(p_over_35, 3),
            "recommendation": "OVER" if p_over_25 > 0.50 else "UNDER",
        },
        "btts_analysis": {
            "btts_probability": round(btts_prob, 3),
            "confidence": round(btts_conf, 1),
            "recommendation": btts_lean,
        },
        "goal_strength": {
            "belgium": round(home_gs, 2),
            "egypt": round(away_gs, 2),
        },
        "recommendations": {
            "match_outcome": outcome_lean,
            "goals": "OVER" if p_over_25 > 0.50 else "UNDER",
            "btts": btts_lean,
        },
        "analysis_notes": (
            "Belgium enters as favorites with superior attacking talent "
            "(De Bruyne, Lukaku) and technical midfield control. Egypt "
            "relies on a compact defensive structure and Mohamed Salah's "
            "world-class counter-attacking ability. Belgium must break "
            "down a disciplined low block — historically a challenge for "
            "possession-dominant teams. World Cup group stage context "
            "adds tension; both teams will be cautious early."
        ),
        "timestamp": datetime.now().isoformat(),
    }
    return results


def main():
    print("=" * 80)
    print("FIFA WORLD CUP 2026 — Belgium vs Egypt")
    print("=" * 80)
    result = run_analysis()
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "belgium_vs_egypt_world_cup_analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")
    print()


if __name__ == "__main__":
    main()