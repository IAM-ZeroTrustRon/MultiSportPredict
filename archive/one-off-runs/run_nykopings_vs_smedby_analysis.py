#!/usr/bin/env python
"""
Deep Dive Analysis — Swedish Division 2 Sodra Svealand
Nykopings BIS vs Smedby AIS
Date: June 15, 2026
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
    team_corner_strength,
    estimate_corner_total,
)
from core.confidence_engine import confidence_score, bet_recommendation


def run_analysis():
    """Run analysis for Nykopings BIS vs Smedby AIS"""

    print("\n" + "=" * 80)
    print("SWEDISH DIVISION 2 SODRA SVEALAND")
    print("Nykopings BIS vs Smedby AIS")
    print("=" * 80 + "\n")

    # Semi-professional tier in Sweden
    # Nykopings BIS (Home) - 4-3-3 expected, midfield control, wide wingers
    # Veteran Enis Ahmetovic dictates pace, vulnerable to counter-attacks
    home_data = {
        'xg_for': 1.50,
        'xg_against': 1.40,
        'shots': 11.0,
        'sot': 4.0,
        'goals_for': 1.45,
        'goals_against': 1.35,
        'clean_sheets': 3,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.25,
        'width_crossing': 0.55,
        'final_third_pressure': 0.50,
    }

    # Smedby AIS (Away) - 4-4-2 or 4-3-3, aggressive direct attacking
    # Joel Unger presses high, wants up-and-down track meet
    away_data = {
        'xg_for': 1.55,
        'xg_against': 1.50,
        'shots': 11.5,
        'sot': 4.2,
        'goals_for': 1.50,
        'goals_against': 1.45,
        'clean_sheets': 2,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.40,  # High tempo, direct attacking style
        'width_crossing': 0.45,
        'final_third_pressure': 0.58,  # High pressing game
    }

    market_data = {
        'goals_line': 2.5,
        'corners_line': 9.5,
        'weather_penalty': 0,
        'referee_flow': 0,
        'must_win_home': 0,
        'must_win_away': 0,
    }

    home_team = "Nykopings BIS"
    away_team = "Smedby AIS"
    league = "Sweden_Division_2"
    date_str = "2026-06-15"

    # ========================================================
    # 1. GOAL STRENGTH
    # ========================================================
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

    # ========================================================
    # 2. EXPECTED GOALS
    # ========================================================
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

    # ========================================================
    # 3. BTTS
    # ========================================================
    print("3. BTTS (BOTH TEAMS TO SCORE) ANALYSIS")
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

    # ========================================================
    # 4. MATCH OUTCOME
    # ========================================================
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

    if home_win_prob >= 0.45:
        outcome_lean = f"Home Win ({home_team})"
    elif away_win_prob >= 0.45:
        outcome_lean = f"Away Win ({away_team})"
    elif draw_prob >= 0.30:
        outcome_lean = "Draw"
    else:
        outcome_lean = "Pass"
    print(f"   Outcome Lean: {outcome_lean}")
    print()

    # ========================================================
    # 5. TACTICAL & SITUATIONAL ANALYSIS
    # ========================================================
    print("5. TACTICAL & SITUATIONAL ANALYSIS")
    print("-" * 40)
    print(f"   Nykopings BIS (4-3-3): Midfield control, wide wingers")
    print(f"      Enis Ahmetovic dictates tempo from deep")
    print(f"      Vulnerable to counter-attacks (noted vs Fittja)")
    print()
    print(f"   Smedby AIS (4-4-2/4-3-3): Direct, aggressive attacking")
    print(f"      Joel Unger high press to force backline turnovers")
    print(f"      Wants up-and-down track meet (tempo: 0.40)")
    print()
    print(f"   Tactical Battle: Smedby's press vs Nykoping's midfield control")
    print(f"   Smedby tempo ({away_data['tempo']:.2f}) much higher than Nykoping ({home_data['tempo']:.2f})")
    print(f"   This favors an open game with transition chances")
    print(f"   Tempo factor adds ~{tempo_factor*100:.1f}% to BTTS probability")
    print()

    # ========================================================
    # 6. FINAL SUMMARY
    # ========================================================
    goals_edge = total_lam - market_data['goals_line']
    goals_conf = confidence_score(goals_edge * 10, volatility=0.55)

    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Match: {home_team} vs {away_team}")
    print(f"   League: Swedish Division 2 Sodra Svealand")
    print(f"   Venue: Nykoping")
    print()
    print(f"   Projected Score: {home_team} {home_lam:.1f} - {away_lam:.1f} {away_team}")
    print(f"   Total Expected Goals: {total_lam:.2f}")
    print()
    print("   === BETTING RECOMMENDATIONS ===")
    print(f"   Match Outcome:      {outcome_lean}")
    print(f"   Goals (O/U 2.5):     {'OVER' if p_over_25 > 0.50 else 'UNDER'} (Conf: {goals_conf:.1f}%)")
    print(f"   BTTS:               {btts_lean} (Conf: {btts_conf:.1f}%)")
    print()

    results = {
        "game_info": {
            "home_team": home_team,
            "away_team": away_team,
            "league": "Swedish Division 2 Sodra Svealand",
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
        "tactical_notes": (
            "Nykopings BIS (4-3-3) aims to control midfield through Enis Ahmetovic "
            "with wide wingers stretching Smedby's fullbacks. However, they are "
            "vulnerable to counter-attacks. Smedby AIS (4-4-2/4-3-3) plays "
            "aggressive direct football with Joel Unger pressing high to force "
            "backline turnovers. Smedby's high tempo (0.40) favors an open, "
            "transition-based match."
        ),
        "timestamp": datetime.now().isoformat(),
    }

    return results


def main():
    print("=" * 80)
    print("SWEDISH DIVISION 2 SODRA SVEALAND")
    print("Nykopings BIS vs Smedby AIS")
    print("=" * 80)

    result = run_analysis()

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "nykopings_bis_vs_smedby_ais_analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()
    print(f"Nykopings BIS vs Smedby AIS:")
    print(f"  Projected Score: {result['projections']['home_expected_goals']:.1f} - {result['projections']['away_expected_goals']:.1f}")
    print(f"  Total Expected Goals: {result['projections']['total_expected_goals']:.2f}")
    print(f"  Match Outcome: {result['recommendations']['match_outcome']}")
    print(f"  Goals (O/U 2.5): {result['recommendations']['goals']}")
    print(f"  BTTS: {result['recommendations']['btts']}")
    print()
    print(f"Results saved to: {output_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()