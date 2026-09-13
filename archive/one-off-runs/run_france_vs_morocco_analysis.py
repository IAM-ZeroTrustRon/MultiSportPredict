#!/usr/bin/env python
"""
Deep Dive Analysis — FIFA World Cup 2026
France vs Morocco
Date: July 2026 (Knockout Stage)
Historical Context: France defeated Morocco 2-0 in the 2022 WC Semifinal.
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
    print("FIFA WORLD CUP 2026 — KNOCKOUT STAGE")
    print("France vs Morocco")
    print("=" * 80 + "\n")

    # ========================================================
    # France — Elite tournament side, heavy favourite
    # ========================================================
    # Mbappé (captain/finisher), Griezmann (10, creative), Tchouaméni (DM),
    # Camavinga (energy), Hernandez brothers (fullbacks), Maignan (GK).
    # High press, vertical transitions, world-class individual quality.
    # Historically dominant vs Morocco (3-0 agg including 2022 WC SF 2-0).
    france_data = {
        'xg_for':  2.15,
        'xg_against': 0.90,
        'shots': 15.2,
        'sot': 5.8,
        'goals_for': 2.10,
        'goals_against': 0.85,
        'clean_sheets': 6,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.55,
        'width_crossing': 0.62,
        'final_third_pressure': 0.65,
    }

    # ========================================================
    # Morocco — 2022 WC Semi-finalists, disciplined & dangerous
    # ========================================================
    # En-Nesyri (striker), Ziyech (creator), Hakimi (RB, attacking threat),
    # Saiss/Aguerd (CB partnership), Bono (elite GK).
    # Ultra-compact 4-3-3 / 5-4-1 defensive block, deadly set pieces,
    # lethal counter-attacks via Hakimi & Ziyech.
    morocco_data = {
        'xg_for':  1.20,
        'xg_against': 0.78,
        'shots': 9.8,
        'sot': 3.4,
        'goals_for': 1.15,
        'goals_against': 0.80,
        'clean_sheets': 7,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.18,
        'width_crossing': 0.42,
        'final_third_pressure': 0.35,
    }

    market_data = {'goals_line': 2.5}

    home_team = "France"
    away_team = "Morocco"
    league = "soccer_fifa_world_cup"
    date_str = "2026-07"

    # ------------------------------------------------------------------
    # 1. GOAL STRENGTH
    # ------------------------------------------------------------------
    print("1. GOAL STRENGTH ANALYSIS")
    print("-" * 40)
    home_gs = team_goal_strength(
        france_data['xg_for'], france_data['xg_against'],
        france_data['shots'], france_data['sot'],
        france_data['goals_for'], france_data['goals_against'],
        france_data['tempo'], 1,
        france_data['missing_attacker'], france_data['missing_creator'],
        france_data['missing_cb'], france_data['missing_gk']
    )
    away_gs = team_goal_strength(
        morocco_data['xg_for'], morocco_data['xg_against'],
        morocco_data['shots'], morocco_data['sot'],
        morocco_data['goals_for'], morocco_data['goals_against'],
        morocco_data['tempo'], 0,
        morocco_data['missing_attacker'], morocco_data['missing_creator'],
        morocco_data['missing_cb'], morocco_data['missing_gk']
    )
    print(f"   France Goal Strength:  {home_gs:+.2f}")
    print(f"   Morocco Goal Strength: {away_gs:+.2f}")
    print(f"   Goal Strength Diff:    {home_gs - away_gs:+.2f}")
    print()

    # ------------------------------------------------------------------
    # 2. EXPECTED GOALS
    # ------------------------------------------------------------------
    print("2. EXPECTED GOALS PROJECTION")
    print("-" * 40)
    home_lam = estimate_team_goals(
        france_data['xg_for'], france_data['sot'], france_data['tempo'], 0,  # Neutral venue
        france_data['missing_attacker'], france_data['missing_creator'],
        morocco_data['xg_against'], morocco_data['missing_cb'], morocco_data['missing_gk']
    )
    away_lam = estimate_team_goals(
        morocco_data['xg_for'], morocco_data['sot'], morocco_data['tempo'], 0,
        morocco_data['missing_attacker'], morocco_data['missing_creator'],
        france_data['xg_against'], france_data['missing_cb'], france_data['missing_gk']
    )
    config = get_league_config(league)
    home_lam *= config['goal_variance']
    away_lam *= config['goal_variance']

    # World Cup knockout: heightened tension, lower scoring average
    home_lam *= 0.95
    away_lam *= 0.92  # Morocco extra defensive in knockouts

    total_lam = home_lam + away_lam

    print(f"   France Expected Goals:  {home_lam:.2f}")
    print(f"   Morocco Expected Goals: {away_lam:.2f}")
    print(f"   Total Expected Goals:   {total_lam:.2f}")
    print(f"   Expected Goal Diff:     {home_lam - away_lam:+.2f}")
    print()

    p_over_15 = poisson_over_prob(total_lam, 1.5)
    p_over_25 = poisson_over_prob(total_lam, 2.5)
    p_over_35 = poisson_over_prob(total_lam, 3.5)
    print(f"   Over 1.5 Goals:  {p_over_15:.1%}")
    print(f"   Over 2.5 Goals:  {p_over_25:.1%}")
    print(f"   Over 3.5 Goals:  {p_over_35:.1%}")
    print()

    # ------------------------------------------------------------------
    # 3. BTTS
    # ------------------------------------------------------------------
    print("3. BTTS ANALYSIS")
    print("-" * 40)
    home_btts = team_btts_strength(
        france_data['xg_for'], france_data['xg_against'],
        france_data['goals_for'], france_data['goals_against'],
        france_data['sot'], france_data['tempo'],
        france_data['final_third_pressure'],
        france_data['missing_attacker'], france_data['missing_cb'], france_data['missing_gk'],
        france_data['clean_sheets']
    )
    away_btts = team_btts_strength(
        morocco_data['xg_for'], morocco_data['xg_against'],
        morocco_data['goals_for'], morocco_data['goals_against'],
        morocco_data['sot'], morocco_data['tempo'],
        morocco_data['final_third_pressure'],
        morocco_data['missing_attacker'], morocco_data['missing_cb'], morocco_data['missing_gk'],
        morocco_data['clean_sheets']
    )
    btts_prob = estimate_btts_prob(home_lam, away_lam, home_btts, away_btts)
    defensive_weakness = (france_data['xg_against'] + morocco_data['xg_against'] - 2.5) * 0.05
    btts_prob = max(0, min(1, btts_prob + defensive_weakness))
    tempo_factor = (france_data['tempo'] + morocco_data['tempo']) * 0.03
    btts_prob = max(0, min(1, btts_prob + tempo_factor))

    # World Cup knockout: both teams very defensive, Morocco especially tight
    btts_prob *= 0.85

    btts_conf = confidence_score((btts_prob - 0.50) * 100, volatility=0.48)
    btts_lean = "BTTS YES" if btts_prob > 0.55 else "BTTS NO"
    print(f"   France BTTS Strength:  {home_btts:+.2f}")
    print(f"   Morocco BTTS Strength: {away_btts:+.2f}")
    print(f"   BTTS Probability:      {btts_prob:.1%}")
    print(f"   BTTS Confidence:       {btts_conf:.1f}%")
    print(f"   BTTS Recommendation:   {btts_lean}")
    print()

    # ------------------------------------------------------------------
    # 4. MATCH OUTCOME
    # ------------------------------------------------------------------
    print("4. MATCH OUTCOME PROJECTION")
    print("-" * 40)
    # Neutral venue, knockout — no true home advantage
    home_win_prob = (home_lam / (home_lam + away_lam)) * 0.78 + 0.05
    away_win_prob = (away_lam / (home_lam + away_lam)) * 0.78 + 0.05
    draw_prob = 1 - home_win_prob - away_win_prob

    # Knockout stage raises draw probability (extra time / pens possible)
    if draw_prob < 0.22:
        draw_prob = 0.22
        norm = home_win_prob + away_win_prob
        if norm > 0:
            home_win_prob *= (1 - draw_prob) / norm
            away_win_prob *= (1 - draw_prob) / norm

    print(f"   France Win:  {home_win_prob:.1%}")
    print(f"   Draw:        {draw_prob:.1%}  (may go to ET/Pens)")
    print(f"   Morocco Win: {away_win_prob:.1%}")

    if home_win_prob >= 0.45:
        outcome_lean = "France Win"
    elif away_win_prob >= 0.35:
        outcome_lean = "Morocco Win"
    elif draw_prob >= 0.28:
        outcome_lean = "Draw (ET/Pens likely)"
    else:
        outcome_lean = "Lean France"
    print(f"   Outcome Lean: {outcome_lean}")
    print()

    # ------------------------------------------------------------------
    # 5. PLAYER PROPS & GOALSCORER ANALYSIS
    # ------------------------------------------------------------------
    print("5. PLAYER PROPS & ANYTIME GOALSCORER")
    print("-" * 40)
    france_scorers = [
        {"name": "Kylian Mbappé",       "xg": 0.68, "odds": "-140", "role": "CF / Captain"},
        {"name": "Antoine Griezmann",   "xg": 0.32, "odds": "+190", "role": "SS / 10"},
        {"name": "Ousmane Dembélé",     "xg": 0.28, "odds": "+220", "role": "RW"},
        {"name": "Marcus Thuram",       "xg": 0.25, "odds": "+250", "role": "CF (rotation)"},
    ]
    morocco_scorers = [
        {"name": "Youssef En-Nesyri",   "xg": 0.38, "odds": "+280", "role": "ST"},
        {"name": "Hakim Ziyech",        "xg": 0.22, "odds": "+380", "role": "AM / wide"},
        {"name": "Achraf Hakimi",       "xg": 0.18, "odds": "+420", "role": "RB (set pieces)"},
        {"name": "Azzedine Ounahi",     "xg": 0.12, "odds": "+550", "role": "CM, long shots"},
    ]

    print(f"\n   FRANCE Anytime Goalscorer Props:")
    print(f"   {'Player':<22} {'xG':>6} {'Odds':>8} {'Prob':>7} {'Role'}")
    print(f"   {'-'*65}")
    for p in france_scorers:
        prob = 1 - (2.718 ** -p['xg'])  # P(at least 1 goal) via Poisson
        rec = "STRONG" if prob >= 0.45 else ("VALUE" if prob >= 0.30 else "PASS")
        print(f"   {p['name']:<22} {p['xg']:>6.2f} {p['odds']:>8} {prob:>6.1%}  {p['role']}")

    print(f"\n   MOROCCO Anytime Goalscorer Props:")
    print(f"   {'Player':<22} {'xG':>6} {'Odds':>8} {'Prob':>7} {'Role'}")
    print(f"   {'-'*65}")
    for p in morocco_scorers:
        prob = 1 - (2.718 ** -p['xg'])
        rec = "VALUE" if prob >= 0.22 else "PASS"
        print(f"   {p['name']:<22} {p['xg']:>6.2f} {p['odds']:>8} {prob:>6.1%}  {p['role']}")

    print()

    # ------------------------------------------------------------------
    # 6. TACTICAL BREAKDOWN
    # ------------------------------------------------------------------
    print("6. TACTICAL BREAKDOWN")
    print("-" * 40)
    print("   France Formation: 4-3-3 / 4-2-3-1")
    print("   Style: High press, vertical transitions, individual brilliance.")
    print("   Strengths: Mbappé pace/dribbling in behind, Griezmann link-up,")
    print("              superior squad depth, elite GK (Maignan).")
    print("   Vulnerabilities: Can be caught on counter if press breaks,")
    print("                    needs to be patient vs deep block.")
    print()
    print("   Morocco Formation: 4-3-3 / 5-4-1 (defensive shape)")
    print("   Style: Ultra-compact low block, disciplined defensive rows,")
    print("          deadly counter-attacks via Hakimi overlaps & Ziyech creativity.")
    print("   Strengths: Bono (GK) exceptional, back-5 very hard to break,")
    print("              lethal on set pieces (scoring & conceding few).")
    print("   Vulnerabilities: Limited possession game (38-42% vs elite),")
    print("                    need set-piece magic or Hakimi burst to break France.")
    print()
    print("   KEY MATCHUP: Mbappé (speed) vs Hakimi (overlapping, same club PSG).")
    print("   Historical: France won 2022 WC SF 2-0 — Morocco never scored vs France.")
    print("   Narrative: Morocco seeking historic revenge; France seeking WC retention.")
    print()

    # ------------------------------------------------------------------
    # 7. CORNER & SET PIECE ANALYSIS
    # ------------------------------------------------------------------
    print("7. CORNERS & SET PIECE ANALYSIS")
    print("-" * 40)
    # France avg ~6 corners for, Morocco avg ~4 corners for
    expected_corners_total = 10.5
    p_corners_over_95 = 0.58
    p_corners_over_105 = 0.44
    print(f"   France Avg Corners For:   ~6.0 per game")
    print(f"   Morocco Avg Corners For:  ~4.5 per game")
    print(f"   Total Corners Expected:   {expected_corners_total}")
    print(f"   Over 9.5 Corners:         {p_corners_over_95:.1%}")
    print(f"   Over 10.5 Corners:        {p_corners_over_105:.1%}")
    print()

    # ------------------------------------------------------------------
    # 8. FINAL SUMMARY
    # ------------------------------------------------------------------
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Match:        France vs Morocco")
    print(f"   Competition:  FIFA World Cup 2026 — Knockout Stage")
    print(f"   Date:         July 2026")
    print()
    print(f"   Projected Score: France {home_lam:.1f} - {away_lam:.1f} Morocco")
    print(f"   Total Expected Goals: {total_lam:.2f}")
    print()

    goals_edge = total_lam - market_data['goals_line']
    goals_conf = confidence_score(goals_edge * 10, volatility=0.55)

    print("   === BETTING RECOMMENDATIONS ===")
    print(f"   Match Outcome:       {outcome_lean}")
    print(f"   Goals O/U 2.5:       {'OVER' if p_over_25 > 0.50 else 'UNDER'} (Conf: {goals_conf:.1f}%)")
    print(f"   BTTS:                {btts_lean} (Conf: {btts_conf:.1f}%)")
    print(f"   Anytime Scorer:      Kylian Mbappé (STRONG), En-Nesyri (VALUE)")
    print(f"   Corners O/U 9.5:     OVER (58.0%)")
    print()
    print("   === SHARP VALUE NOTES ===")
    print("   • Morocco to qualify (Draw + ET/Pens): Solid upset value (~+290+)")
    print("   • Mbappé anytime scorer: best single-bet value at French prices")
    print("   • Under 2.5 goals: Morocco's defensive record makes this a live option")
    print("   • France to win both halves: value if press dominates early")
    print()

    results = {
        "game_info": {
            "home_team": "France",
            "away_team": "Morocco",
            "competition": "FIFA World Cup 2026",
            "stage": "Knockout Stage",
            "date": date_str,
        },
        "projections": {
            "france_expected_goals": round(home_lam, 2),
            "morocco_expected_goals": round(away_lam, 2),
            "total_expected_goals": round(total_lam, 2),
            "france_win_prob": round(home_win_prob, 3),
            "draw_prob": round(draw_prob, 3),
            "morocco_win_prob": round(away_win_prob, 3),
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
        "corners_analysis": {
            "total_expected": expected_corners_total,
            "over_95_prob": p_corners_over_95,
            "over_105_prob": p_corners_over_105,
            "recommendation": "OVER 9.5",
        },
        "goal_strength": {
            "france": round(home_gs, 2),
            "morocco": round(away_gs, 2),
        },
        "player_props": {
            "france_scorers": [
                {**p, "prob": round(1 - (2.718 ** -p['xg']), 3)}
                for p in france_scorers
            ],
            "morocco_scorers": [
                {**p, "prob": round(1 - (2.718 ** -p['xg']), 3)}
                for p in morocco_scorers
            ],
        },
        "recommendations": {
            "match_outcome": outcome_lean,
            "goals": "OVER" if p_over_25 > 0.50 else "UNDER",
            "btts": btts_lean,
            "anytime_scorer_value": "Kylian Mbappé",
            "corners": "OVER 9.5",
        },
        "analysis_notes": (
            "France enter as heavy favourites with the world's best player (Mbappé) "
            "and a multi-layered attacking threat. Morocco are the most defensively "
            "disciplined team in the tournament — their compact block frustrated "
            "every opponent in 2022 until France themselves put them to bed 2-0. "
            "The Atlas Lions will sit deep and look to Hakimi and Ziyech on the "
            "counter or set pieces. France must be patient, avoid overcommitting, "
            "and use Mbappé's pace in behind a high Morocco line. Expect a tactical, "
            "low-scoring first half with France likely edging a 1-0 or 2-0 result. "
            "Morocco upset potential is real if France miss key chances early."
        ),
        "timestamp": datetime.now().isoformat(),
    }
    return results


def main():
    print("=" * 80)
    print("FIFA WORLD CUP 2026 — France vs Morocco")
    print("=" * 80)
    result = run_analysis()
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "france_vs_morocco_world_cup_analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")
    print()


if __name__ == "__main__":
    main()
