#!/usr/bin/env python
"""
Deep Dive Analysis — Ykkosliiga (Finland)
SJK Akatemia vs FC Haka
Date: June 2026
"""

import sys
import json
from datetime import datetime
from pathlib import Path

from models.soccer_predictor import (
    get_league_config,
    poisson_over_prob,
    estimate_team_goals,
    estimate_btts_prob,
    team_goal_strength,
    team_btts_strength,
)
from core.confidence_engine import confidence_score, bet_recommendation


def run_analysis():
    print("\n" + "=" * 80)
    print("FINNISH YKKOSLIIGA")
    print("SJK Akatemia vs FC Haka")
    print("=" * 80 + "\n")

    # SJK Akatemia (Home) — reserve side of SJK Seinajoki
    # Young squad, inconsistent, plays in Seinajoki
    home_data = {
        'xg_for': 1.30,
        'xg_against': 1.55,
        'shots': 10.5,
        'sot': 3.8,
        'goals_for': 1.25,
        'goals_against': 1.50,
        'clean_sheets': 2,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.20,
        'width_crossing': 0.50,
        'final_third_pressure': 0.45,
    }

    # FC Haka (Away) — established Veikkausliiga/Ykkosliiga club from Valkeakoski
    # More experienced, should dominate possession
    away_data = {
        'xg_for': 1.65,
        'xg_against': 1.20,
        'shots': 12.0,
        'sot': 4.5,
        'goals_for': 1.60,
        'goals_against': 1.15,
        'clean_sheets': 5,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.30,
        'width_crossing': 0.52,
        'final_third_pressure': 0.52,
    }

    market_data = {'goals_line': 2.5}

    home_team = "SJK Akatemia"
    away_team = "FC Haka"
    league = "Finland_Ykkosliiga"
    date_str = "2026-06"

    # 1. GOAL STRENGTH
    print("1. GOAL STRENGTH ANALYSIS")
    print("-" * 40)
    home_gs = team_goal_strength(
        home_data['xg_for'], home_data['xg_against'], home_data['shots'], home_data['sot'],
        home_data['goals_for'], home_data['goals_against'], home_data['tempo'], 1,
        home_data['missing_attacker'], home_data['missing_creator'],
        home_data['missing_cb'], home_data['missing_gk']
    )
    away_gs = team_goal_strength(
        away_data['xg_for'], away_data['xg_against'], away_data['shots'], away_data['sot'],
        away_data['goals_for'], away_data['goals_against'], away_data['tempo'], 0,
        away_data['missing_attacker'], away_data['missing_creator'],
        away_data['missing_cb'], away_data['missing_gk']
    )
    print(f"   {home_team} Goal Strength: {home_gs:+.2f}")
    print(f"   {away_team} Goal Strength: {away_gs:+.2f}")
    print(f"   Goal Strength Diff: {home_gs - away_gs:+.2f}")
    print()

    # 2. EXPECTED GOALS
    print("2. EXPECTED GOALS PROJECTION")
    print("-" * 40)
    home_lam = estimate_team_goals(
        home_data['xg_for'], home_data['sot'], home_data['tempo'], 1,
        home_data['missing_attacker'], home_data['missing_creator'],
        away_data['xg_against'], away_data['missing_cb'], away_data['missing_gk']
    )
    away_lam = estimate_team_goals(
        away_data['xg_for'], away_data['sot'], away_data['tempo'], 0,
        away_data['missing_attacker'], away_data['missing_creator'],
        home_data['xg_against'], home_data['missing_cb'], home_data['missing_gk']
    )
    config = get_league_config(league)
    home_lam *= config['goal_variance']
    away_lam *= config['goal_variance']
    home_lam *= (1 + config['home_advantage'] * 0.1)
    total_lam = home_lam + away_lam

    print(f"   {home_team} Expected Goals: {home_lam:.2f}")
    print(f"   {away_team} Expected Goals: {away_lam:.2f}")
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
        home_data['xg_for'], home_data['xg_against'], home_data['goals_for'], home_data['goals_against'],
        home_data['sot'], home_data['tempo'], home_data['final_third_pressure'],
        home_data['missing_attacker'], home_data['missing_cb'], home_data['missing_gk'],
        home_data['clean_sheets']
    )
    away_btts = team_btts_strength(
        away_data['xg_for'], away_data['xg_against'], away_data['goals_for'], away_data['goals_against'],
        away_data['sot'], away_data['tempo'], away_data['final_third_pressure'],
        away_data['missing_attacker'], away_data['missing_cb'], away_data['missing_gk'],
        away_data['clean_sheets']
    )
    btts_prob = estimate_btts_prob(home_lam, away_lam, home_btts, away_btts)
    defensive_weakness = (home_data['xg_against'] + away_data['xg_against'] - 2.5) * 0.05
    btts_prob = max(0, min(1, btts_prob + defensive_weakness))
    tempo_factor = (home_data['tempo'] + away_data['tempo']) * 0.03
    btts_prob = max(0, min(1, btts_prob + tempo_factor))
    btts_conf = confidence_score((btts_prob - 0.50) * 100, volatility=0.48)
    btts_lean = "BTTS YES" if btts_prob > 0.55 else "BTTS NO"
    print(f"   BTTS Probability: {btts_prob:.1%}")
    print(f"   BTTS Confidence: {btts_conf:.1f}%")
    print(f"   BTTS Recommendation: {btts_lean}")
    print()

    # 4. MATCH OUTCOME
    print("4. MATCH OUTCOME PROJECTION")
    print("-" * 40)
    home_win_prob = (home_lam / (home_lam + away_lam)) * 0.85 + 0.10
    away_win_prob = (away_lam / (home_lam + away_lam)) * 0.85 + 0.05
    draw_prob = 1 - home_win_prob - away_win_prob
    if draw_prob < 0.15:
        draw_prob = 0.15
        norm = home_win_prob + away_win_prob
        if norm > 0:
            home_win_prob *= (1 - draw_prob) / norm
            away_win_prob *= (1 - draw_prob) / norm
    print(f"   {home_team} Win: {home_win_prob:.1%}")
    print(f"   Draw:         {draw_prob:.1%}")
    print(f"   {away_team} Win: {away_win_prob:.1%}")
    if away_win_prob >= 0.45:
        outcome_lean = f"Away Win ({away_team})"
    elif home_win_prob >= 0.45:
        outcome_lean = f"Home Win ({home_team})"
    elif draw_prob >= 0.30:
        outcome_lean = "Draw"
    else:
        outcome_lean = "Pass"
    print(f"   Outcome Lean: {outcome_lean}")
    print()

    # 5. FINAL SUMMARY
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Match: {home_team} vs {away_team}")
    print(f"   League: Finnish Ykkosliiga")
    print(f"   Projected Score: {home_team} {home_lam:.1f} - {away_lam:.1f} {away_team}")
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
            "home_team": home_team,
            "away_team": away_team,
            "league": "Finnish Ykkosliiga",
            "date": date_str,
        },
        "projections": {
            "home_expected_goals": round(home_lam, 2),
            "away_expected_goals": round(away_lam, 2),
            "total_expected_goals": round(total_lam, 2),
            "home_win_prob": round(home_win_prob, 3),
            "draw_prob": round(draw_prob, 3),
            "away_win_prob": round(away_win_prob, 3),
        },
        "goals_analysis": {
            "over_15_prob": round(p_over_15, 3),
            "over_25_prob": round(p_over_25, 3),
            "over_35_prob": round(p_over_35, 3),
        },
        "btts_analysis": {
            "btts_probability": round(btts_prob, 3),
            "confidence": round(btts_conf, 1),
            "recommendation": btts_lean,
        },
        "goal_strength": {
            "home": round(home_gs, 2),
            "away": round(away_gs, 2),
        },
        "recommendations": {
            "match_outcome": outcome_lean,
            "goals": "OVER" if p_over_25 > 0.50 else "UNDER",
            "btts": btts_lean,
        },
        "timestamp": datetime.now().isoformat(),
    }
    return results


def main():
    print("=" * 80)
    print("FINNISH YKKOSLIIGA — SJK Akatemia vs FC Haka")
    print("=" * 80)
    result = run_analysis()
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "sjk_akatemia_vs_fc_haka_analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")
    print()


if __name__ == "__main__":
    main()