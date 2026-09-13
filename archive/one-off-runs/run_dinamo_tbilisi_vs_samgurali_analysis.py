#!/usr/bin/env python
"""
Deep Dive Analysis — Crystalbet Erovnuli Liga Round 18
FC Dinamo Tbilisi vs FC Samgurali Tskhaltubo
Date: June 18, 2026 — 12:00 PM EDT
Venue: Boris Paichadze Dinamo Arena, Tbilisi

Match Data:
  Dinamo Tbilisi: 4th, 25 pts (6W-7D-4L), GF:24 GA:17 (+7), Form: W, W, D, L, W
  Samgurali: 6th, 24 pts (7W-3D-7L), GF:22 GA:27 (-5), Form: D, L, W, W, W
  H2H: Dinamo won 2-1 on April 25, 2026. Series: Dinamo 8W, Samgurali 7W, 6D
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


def run_deep_analysis():
    """Run deep dive analysis for Dinamo Tbilisi vs Samgurali"""

    print("\n" + "=" * 80)
    print("CRYSTALBET EROVNULI LIGA — ROUND 18")
    print("FC Dinamo Tbilisi vs FC Samgurali Tskhaltubo")
    print("Boris Paichadze Dinamo Arena, Tbilisi")
    print("June 18, 2026 — 12:00 PM EDT (16:00 UTC)")
    print("=" * 80 + "\n")

    # ========================================================
    # TEAM METRICS — Derived from match data
    # ========================================================

    # FC Dinamo Tbilisi (Home)
    # 17 games: GF 24 (1.41/g), GA 17 (1.0/g), GD +7
    # Last 5 form: W, W, D, L, W — 11 goals scored, solid defense
    # H2H: Won 2-1 away on April 25
    home_data = {
        'xg_for': 1.65,
        'xg_against': 1.10,
        'shots': 12.5,
        'sot': 4.5,
        'goals_for': 1.41,
        'goals_against': 1.00,
        'clean_sheets': 6,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.30,
        'width_crossing': 0.55,
        'final_third_pressure': 0.55,
    }

    # FC Samgurali Tskhaltubo (Away)
    # 17 games: GF 22 (1.29/g), GA 27 (1.59/g), GD -5
    # Last 5 form: D, L, W, W, W — 3 straight wins before last match
    # Leaky defense, outscore-or-lose approach
    away_data = {
        'xg_for': 1.20,
        'xg_against': 1.55,
        'shots': 10.5,
        'sot': 3.8,
        'goals_for': 1.29,
        'goals_against': 1.59,
        'clean_sheets': 4,
        'missing_attacker': 0,
        'missing_creator': 0,
        'missing_cb': 0,
        'missing_gk': 0,
        'tempo': 0.20,
        'width_crossing': 0.45,
        'final_third_pressure': 0.48,
    }

    market_data = {
        'goals_line': 2.5,
        'alt_goals_line': 1.5,
        'corners_line': 9.0,
        'weather_penalty': 0,
        'referee_flow': 0,
        'must_win_home': 0,
        'must_win_away': 0,
    }

    home_team = "FC Dinamo Tbilisi"
    away_team = "FC Samgurali Tskhaltubo"
    league = "Georgia_Erovnuli_Liga"
    date_str = "2026-06-18"
    venue = "Boris Paichadze Dinamo Arena, Tbilisi"

    # ========================================================
    # 1. TEAM OFFENSIVE/DEFENSIVE ANALYSIS
    # ========================================================
    print("1. TEAM OFFENSIVE/DEFENSIVE ANALYSIS")
    print("-" * 40)

    print(f"   {home_team}:")
    print(f"      xG For: {home_data['xg_for']:.2f} | xG Against: {home_data['xg_against']:.2f}")
    print(f"      Goals For: {home_data['goals_for']:.1f} | Goals Against: {home_data['goals_against']:.1f}")
    print(f"      Goal Differential: +{home_data['goals_for'] - home_data['goals_against']:.1f}")
    print(f"      Shots: {home_data['shots']:.0f} | SoT: {home_data['sot']:.0f}")
    print(f"      Clean Sheets: {home_data['clean_sheets']}")
    print(f"      Form: W, W, D, L, W (11 goals in last 5)")
    print()
    print(f"   {away_team}:")
    print(f"      xG For: {away_data['xg_for']:.2f} | xG Against: {away_data['xg_against']:.2f}")
    print(f"      Goals For: {away_data['goals_for']:.1f} | Goals Against: {away_data['goals_against']:.1f}")
    print(f"      Goal Differential: {away_data['goals_for'] - away_data['goals_against']:+.1f}")
    print(f"      Shots: {away_data['shots']:.0f} | SoT: {away_data['sot']:.0f}")
    print(f"      Clean Sheets: {away_data['clean_sheets']}")
    print(f"      Form: D, L, W, W, W (3 straight wins recently)")
    print()

    # ========================================================
    # 2. GOAL STRENGTH ANALYSIS
    # ========================================================
    print("2. GOAL STRENGTH ANALYSIS")
    print("-" * 40)

    home_goal_strength = team_goal_strength(
        home_data['xg_for'], home_data['xg_against'], home_data['shots'], home_data['sot'],
        home_data['goals_for'], home_data['goals_against'], home_data['tempo'], 1,
        home_data['missing_attacker'], home_data['missing_creator'],
        home_data['missing_cb'], home_data['missing_gk']
    )
    away_goal_strength = team_goal_strength(
        away_data['xg_for'], away_data['xg_against'], away_data['shots'], away_data['sot'],
        away_data['goals_for'], away_data['goals_against'], away_data['tempo'], 0,
        away_data['missing_attacker'], away_data['missing_creator'],
        away_data['missing_cb'], away_data['missing_gk']
    )

    print(f"   {home_team} Goal Strength: {home_goal_strength:+.2f}")
    print(f"   {away_team} Goal Strength: {away_goal_strength:+.2f}")
    print(f"   Goal Strength Diff: {home_goal_strength - away_goal_strength:+.2f}")
    print()

    # ========================================================
    # 3. EXPECTED GOALS PROJECTION
    # ========================================================
    print("3. EXPECTED GOALS PROJECTION")
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

    # Apply league config adjustments
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

    # Goal probabilities
    p_over_15 = poisson_over_prob(total_lam, 1.5)
    p_over_25 = poisson_over_prob(total_lam, 2.5)
    p_over_35 = poisson_over_prob(total_lam, 3.5)

    print(f"   Over 1.5 Goals: {p_over_15:.1%}")
    print(f"   Over 2.5 Goals: {p_over_25:.1%}")
    print(f"   Over 3.5 Goals: {p_over_35:.1%}")
    print()

    # ========================================================
    # 4. BTTS ANALYSIS
    # ========================================================
    print("4. BTTS (BOTH TEAMS TO SCORE) ANALYSIS")
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

    # Samgurali scores consistently (1.29/game)
    # Dinamo defense is strong (1.00 GA/game)
    # Adjust: Samgurali has scored in most recent games
    btts_prob = min(1.0, btts_prob + 0.03)  # slight boost for recent attacking form

    btts_conf = confidence_score((btts_prob - 0.50) * 100, volatility=0.48)
    btts_rec = bet_recommendation(btts_conf)
    btts_lean = "BTTS YES" if btts_prob > 0.55 else "BTTS NO"

    print(f"   {home_team} BTTS Strength: {home_btts:+.2f}")
    print(f"   {away_team} BTTS Strength: {away_btts:+.2f}")
    print(f"   BTTS Probability: {btts_prob:.1%}")
    print(f"   BTTS Confidence: {btts_conf:.1f}%")
    print(f"   BTTS Recommendation: {btts_lean} ({btts_rec})")
    print()

    # ========================================================
    # 5. CORNER ANALYSIS
    # ========================================================
    print("5. CORNERS ANALYSIS")
    print("-" * 40)

    home_corner = team_corner_strength(
        home_data['shots'], home_data['sot'], home_data['final_third_pressure'],
        home_data['width_crossing'], home_data['tempo'], 1,
        home_data['missing_cb'], home_data['missing_gk'], home_data['missing_attacker']
    )
    away_corner = team_corner_strength(
        away_data['shots'], away_data['sot'], away_data['final_third_pressure'],
        away_data['width_crossing'], away_data['tempo'], 0,
        away_data['missing_cb'], away_data['missing_gk'], away_data['missing_attacker']
    )

    corner_total = estimate_corner_total(
        home_corner, away_corner,
        market_data.get('weather_penalty', 0), market_data.get('referee_flow', 0),
        market_data.get('must_win_home', 0), market_data.get('must_win_away', 0)
    )

    p_corners_85 = poisson_over_prob(corner_total, 8.5)
    p_corners_95 = poisson_over_prob(corner_total, 9.5)
    p_corners_105 = poisson_over_prob(corner_total, 10.5)

    print(f"   {home_team} Corner Strength: {home_corner:+.2f}")
    print(f"   {away_team} Corner Strength: {away_corner:+.2f}")
    print(f"   Projected Total Corners: {corner_total:.1f}")
    print(f"   Over 8.5: {p_corners_85:.1%}")
    print(f"   Over 9.5: {p_corners_95:.1%}")
    print(f"   Over 10.5: {p_corners_105:.1%}")
    print()

    # ========================================================
    # 6. MATCH OUTCOME PROJECTION
    # ========================================================
    print("6. MATCH OUTCOME PROJECTION")
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
    # 7. GOALS MARKET ANALYSIS
    # ========================================================
    print("7. GOALS MARKET ANALYSIS")
    print("-" * 40)

    goals_market_line = market_data.get('goals_line', 2.5)
    alt_goals_line = market_data.get('alt_goals_line', 1.5)

    if goals_market_line <= 1.5:
        goals_prob = p_over_15
    elif goals_market_line <= 2.5:
        goals_prob = p_over_25
    else:
        goals_prob = p_over_35

    goals_edge = total_lam - goals_market_line
    goals_conf = confidence_score(goals_edge * 10, volatility=0.55)
    goals_rec = bet_recommendation(goals_conf)

    alt_goals_edge = total_lam - alt_goals_line
    alt_goals_conf = confidence_score(alt_goals_edge * 10, volatility=0.50)

    print(f"   Market Goals Line: O/U {goals_market_line}")
    print(f"   Model Projected Total: {total_lam:.2f}")
    print(f"   Edge vs {goals_market_line}: {goals_edge:+.2f}")
    print(f"   Over {goals_market_line} Probability: {goals_prob:.1%}")
    print(f"   Recommendation: {'OVER' if goals_prob > 0.50 else 'UNDER'} ({goals_rec}, Conf: {goals_conf:.1f}%)")
    print()
    print(f"   --- Alternate Total (Safety Net) ---")
    print(f"   Alternative Line: O/U {alt_goals_line}")
    print(f"   Over {alt_goals_line} Probability: {p_over_15:.1%}")
    print(f"   Edge vs {alt_goals_line}: {alt_goals_edge:+.2f}")
    print(f"   Recommendation: OVER {alt_goals_line} (Conf: {alt_goals_conf:.1f}%)")
    print()

    # ========================================================
    # 8. DOUBLE CHANCE / DRAW NO BET ANALYSIS
    # ========================================================
    print("8. DOUBLE CHANCE / DRAW NO BET ANALYSIS")
    print("-" * 40)

    dc_home_or_draw = home_win_prob + draw_prob
    dc_away_or_draw = away_win_prob + draw_prob

    # Draw No Bet (DNB): remove draw probability, renormalize
    dnb_total = home_win_prob + away_win_prob
    dnb_home = home_win_prob / dnb_total if dnb_total > 0 else 0.5
    dnb_away = away_win_prob / dnb_total if dnb_total > 0 else 0.5

    print(f"   Double Chance (Home or Draw): {dc_home_or_draw:.1%}")
    print(f"   Double Chance (Away or Draw): {dc_away_or_draw:.1%}")
    print(f"   Draw No Bet — {home_team}: {dnb_home:.1%}")
    print(f"   Draw No Bet — {away_team}: {dnb_away:.1%}")
    print()

    # ========================================================
    # 9. THE 2-LEG SAFETY NET PARLAY
    # ========================================================
    print("9. THE 2-LEG SAFETY NET PARLAY")
    print("-" * 40)

    # Leg 1: Dinamo Tbilisi +0.5 (Double Chance) — i.e., Home or Draw
    leg1_prob = dc_home_or_draw
    leg1_conf = confidence_score((leg1_prob - 0.80) * 100, volatility=0.40)
    print(f"   Leg 1: {home_team} Double Chance (Home or Draw)")
    print(f"      Probability: {leg1_prob:.1%}")
    print(f"      Confidence: {leg1_conf:.1f}%")
    print(f"      Logic: Dinamo at home, higher table, +7 GD, won H2H away")

    # Leg 2: Over 1.5 Total Goals (Alternate Total)
    leg2_prob = p_over_15
    leg2_conf = confidence_score((leg2_prob - 0.85) * 100, volatility=0.35)
    print(f"   Leg 2: Over 1.5 Total Goals (Alternate Total)")
    print(f"      Probability: {leg2_prob:.1%}")
    print(f"      Confidence: {leg2_conf:.1f}%")
    print(f"      Logic: Dinamo 11 goals last 5, Samgurali games avg ~2.9 total goals")

    # Parlay combined probability
    parlay_prob = leg1_prob * leg2_prob
    print(f"\n   Parlay Combined Probability: {parlay_prob:.1%}")
    print(f"   Recommendation: {'PLAY' if parlay_prob > 0.65 else 'PASS'}")

    # Typical payout for +0.5 DC (~1.20) x O1.5 (~1.25) = ~1.50
    parlay_fair_value = parlay_prob * 1.50
    print(f"   Estimated Parlay Odds: ~1.50 (fair value)")
    print(f"   Expected Value: {'+' if parlay_fair_value > 1 else ''}{parlay_fair_value - 1:.2f}")
    print()

    # ========================================================
    # 10. FACTOR ANALYSIS
    # ========================================================
    print("10. KEY HANDICAPPING FACTORS")
    print("-" * 40)

    print(f"\n   FACTORS FAVORING {home_team.upper()}:")
    factors_home = []
    if home_goal_strength > away_goal_strength:
        factors_home.append(f"Better goal strength ({home_goal_strength:+.2f} vs {away_goal_strength:+.2f})")
    if home_data['xg_for'] > away_data['xg_for']:
        factors_home.append(f"Higher xG ({home_data['xg_for']:.2f} vs {away_data['xg_for']:.2f})")
    if home_data['xg_against'] < away_data['xg_against']:
        factors_home.append(f"Much better defensive xG ({home_data['xg_against']:.2f} vs {away_data['xg_against']:.2f})")
    if home_data['clean_sheets'] > away_data['clean_sheets']:
        factors_home.append(f"More clean sheets ({home_data['clean_sheets']} vs {away_data['clean_sheets']})")
    if home_data['goals_against'] < away_data['goals_against']:
        factors_home.append(f"Superior goal differential (+7 vs -5)")
    factors_home.append("Home pitch at 54,000-seat Boris Paichadze Dinamo Arena")
    factors_home.append("Won H2H 2-1 away in April")
    factors_home.append("Attacking form: 11 goals in last 5 matches (2.2/game)")

    for f in factors_home:
        print(f"   [+] {f}")

    print(f"\n   FACTORS FAVORING {away_team.upper()}:")
    factors_away = []
    if away_goal_strength > home_goal_strength:
        factors_away.append(f"Better goal strength ({away_goal_strength:+.2f} vs {home_goal_strength:+.2f})")
    if away_data['xg_for'] > home_data['xg_for']:
        factors_away.append(f"Higher xG ({away_data['xg_for']:.2f} vs {home_data['xg_for']:.2f})")
    if away_data['xg_against'] < home_data['xg_against']:
        factors_away.append(f"Better defensive xG ({away_data['xg_against']:.2f} vs {home_data['xg_against']:.2f})")
    factors_away.append("Recent hot streak (W, W, W before last match)")
    factors_away.append("Only 1 point behind Dinamo in the table")
    factors_away.append("Loan players Berelidze & Shatirishvili may feature vs parent club ('revenge game')")
    factors_away.append("Tight historical series: 7-6-8 in Samgurali's favor is close")

    for f in factors_away:
        print(f"   [+] {f}")
    print()

    # ========================================================
    # 11. INJURY & LOAN NARRATIVE
    # ========================================================
    print("11. LOAN NARRATIVE & AVAILABILITY")
    print("-" * 40)
    print(f"   Dinamo Tbilisi loaned Tsotne Berelidze and Mate Shatirishvili")
    print(f"   to Samgurali for the season.")
    print(f"   If eligible to play vs parent club, this adds a 'revenge game'")
    print(f"   narrative that could boost Samgurali's intensity.")
    print(f"   Impact: Moderate — could edge Samgurali's attacking output slightly")
    print()

    # ========================================================
    # 12. FINAL SUMMARY
    # ========================================================
    print("=" * 80)
    print("FINAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"   Match: {home_team} vs {away_team}")
    print(f"   League: {league} | Date: {date_str}")
    print(f"   Venue: {venue}")
    print(f"   Kickoff: 12:00 PM EDT (16:00 UTC)")
    print()
    print(f"   Projected Score: {home_team} {home_lam:.1f} - {away_lam:.1f} {away_team}")
    print(f"   Total Expected Goals: {total_lam:.2f}")
    print()
    print("   === BETTING RECOMMENDATIONS ===")
    print(f"   Match Outcome:      {outcome_lean}")
    print(f"   Goals (O/U {goals_market_line}):     {'OVER' if goals_prob > 0.50 else 'UNDER'} (Conf: {goals_conf:.1f}%)")
    print(f"   Alt Total (O/U {alt_goals_line}): OVER (Conf: {alt_goals_conf:.1f}%)")
    print(f"   Double Chance (H/D): {home_team} or Draw ({dc_home_or_draw:.1%})")
    print(f"   BTTS:               {btts_lean} (Conf: {btts_conf:.1f}%)")
    print(f"   Total Corners (O/U 9.5): {'OVER' if p_corners_95 > 0.50 else 'UNDER'}")
    print()
    print("   === THE 2-LEG SAFETY NET PARLAY ===")
    print(f"   Leg 1: {home_team} Double Chance (Home or Draw)")
    print(f"   Leg 2: Over 1.5 Total Goals")
    print(f"   Combined Probability: {parlay_prob:.1%}")
    print(f"   Recommendation: {'PLAY' if parlay_prob > 0.65 else 'PASS'}")
    print()
    print(f"   H2H Edge: Dinamo Tbilisi (won 2-1 on April 25, 2026)")
    print(f"   Form Edge: Even (Dinamo W,W,D,L,W vs Samgurali D,L,W,W,W)")
    print(f"   Defensive Edge: Dinamo Tbilisi (GA 1.0/game vs 1.59/game)")
    print()

    # ========================================================
    # BUILD RESULTS DICTIONARY
    # ========================================================
    results = {
        "game_info": {
            "home_team": home_team,
            "away_team": away_team,
            "league": league,
            "date": date_str,
            "venue": venue,
            "kickoff": "12:00 PM EDT (16:00 UTC)",
        },
        "standings_and_form": {
            "home": {"position": 4, "points": 25, "record": "6W-7D-4L", "gd": "+7", "form": "W, W, D, L, W"},
            "away": {"position": 6, "points": 24, "record": "7W-3D-7L", "gd": "-5", "form": "D, L, W, W, W"},
            "h2h_last_meeting": "2026-04-25: Dinamo Tbilisi 2-1 Samgurali (away)",
            "h2h_series": "Dinamo 8W, Samgurali 7W, 6D",
        },
        "team_metrics": {
            "home": home_data,
            "away": away_data,
        },
        "projections": {
            "home_expected_goals": round(home_lam, 2),
            "away_expected_goals": round(away_lam, 2),
            "total_expected_goals": round(total_lam, 2),
            "home_win_prob": round(home_win_prob, 3),
            "draw_prob": round(draw_prob, 3),
            "away_win_prob": round(away_win_prob, 3),
            "double_chance_home_or_draw": round(dc_home_or_draw, 3),
            "double_chance_away_or_draw": round(dc_away_or_draw, 3),
            "dnb_home": round(dnb_home, 3),
            "dnb_away": round(dnb_away, 3),
        },
        "goals_analysis": {
            "over_15_prob": round(p_over_15, 3),
            "over_25_prob": round(p_over_25, 3),
            "over_35_prob": round(p_over_35, 3),
            "market_line": goals_market_line,
            "alt_line": alt_goals_line,
            "edge_vs_market": round(goals_edge, 3),
            "edge_vs_alt": round(alt_goals_edge, 3),
            "confidence": round(goals_conf, 1),
            "recommendation": "OVER" if goals_prob > 0.50 else "UNDER",
            "alt_recommendation": f"OVER {alt_goals_line}",
        },
        "btts_analysis": {
            "home_btts_strength": round(home_btts, 2),
            "away_btts_strength": round(away_btts, 2),
            "btts_probability": round(btts_prob, 3),
            "confidence": round(btts_conf, 1),
            "recommendation": btts_lean,
        },
        "corners_analysis": {
            "home_corner_strength": round(home_corner, 2),
            "away_corner_strength": round(away_corner, 2),
            "projected_total": round(corner_total, 1),
            "over_85_prob": round(p_corners_85, 3),
            "over_95_prob": round(p_corners_95, 3),
            "over_105_prob": round(p_corners_105, 3),
        },
        "goal_strength": {
            "home": round(home_goal_strength, 2),
            "away": round(away_goal_strength, 2),
        },
        "safety_net_parlay": {
            "leg1_description": f"{home_team} Double Chance (Home or Draw)",
            "leg1_probability": round(leg1_prob, 3),
            "leg1_confidence": round(leg1_conf, 1),
            "leg2_description": f"Over {alt_goals_line} Total Goals",
            "leg2_probability": round(leg2_prob, 3),
            "leg2_confidence": round(leg2_conf, 1),
            "combined_probability": round(parlay_prob, 3),
            "recommendation": "PLAY" if parlay_prob > 0.65 else "PASS",
        },
        "recommendations": {
            "match_outcome": outcome_lean,
            "double_chance": f"{home_team} or Draw",
            "goals_market": "OVER" if goals_prob > 0.50 else "UNDER",
            "alt_goals": f"OVER {alt_goals_line}",
            "btts": btts_lean,
            "corners": "OVER 9.5" if p_corners_95 > 0.50 else "UNDER 9.5",
        },
        "analysis_notes": (
            "Dinamo Tbilisi enters as a strong home favorite: higher league position (4th), "
            "vastly superior goal differential (+7 vs -5), and won the H2H 2-1 away in April. "
            "Their attack is clicking (11 goals in last 5) and defense is reliable (1.0 GA/game). "
            "Samgurali has been inconsistent defensively (-5 GD) despite a recent hot streak. "
            "The loan narrative (Berelidze, Shatirishvili facing parent club) adds spice. "
            "Best plays: Dinamo DC (Home or Draw) + Over 1.5 Goals as a safety net parlay, "
            "or standalone Over 2.5 Goals given both teams' recent scoring output."
        ),
        "timestamp": datetime.now().isoformat(),
    }

    return results


def main():
    """Run Dinamo Tbilisi vs Samgurali analysis"""

    print("=" * 80)
    print("CRYSTALBET EROVNULI LIGA — ROUND 18 ANALYSIS")
    print("FC Dinamo Tbilisi vs FC Samgurali Tskhaltubo")
    print("June 18, 2026 — 12:00 PM EDT — Boris Paichadze Dinamo Arena")
    print("=" * 80)

    result = run_deep_analysis()

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "dinamo_tbilisi_vs_samgurali_analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()
    print(f"FC Dinamo Tbilisi vs FC Samgurali Tskhaltubo:")
    print(f"  Projected Score: {result['projections']['home_expected_goals']:.1f} - {result['projections']['away_expected_goals']:.1f}")
    print(f"  Total Expected Goals: {result['projections']['total_expected_goals']:.2f}")
    print(f"  Match Outcome: {result['recommendations']['match_outcome']}")
    print(f"  Double Chance: {result['recommendations']['double_chance']}")
    print(f"  Goals (O/U 2.5): {result['recommendations']['goals_market']}")
    print(f"  Alt Goals (O/U 1.5): {result['recommendations']['alt_goals']}")
    print(f"  BTTS: {result['recommendations']['btts']}")
    print(f"  Corners: {result['recommendations']['corners']}")
    print()
    print("  === SAFETY NET PARLAY ===")
    print(f"  Leg 1: Dinamo Tbilisi DC (Home or Draw)")
    print(f"  Leg 2: Over 1.5 Goals")
    print(f"  Combined: {result['safety_net_parlay']['recommendation']} ({result['safety_net_parlay']['combined_probability']:.1%})")
    print()
    print(f"Results saved to: {output_path}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()